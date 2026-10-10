import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from unittest.mock import Mock

import pytest

from bee_bot.errors import BeeBotError
from bee_bot.service import BeeBotService
from conftest import create, invitation, respond


@pytest.mark.parametrize("actor", ["unknown", "inactive"])
def test_untrusted_or_inactive_identity_cannot_read_or_mutate(env, actor):
    with pytest.raises(BeeBotError):
        env.service.get_my_assignments(actor)
    with pytest.raises(BeeBotError):
        create(env, actor=actor)
    with pytest.raises(BeeBotError):
        env.service.get_my_notifications(actor)
    assert env.service.list_my_requests("ops") == []


def test_assignment_ownership_and_ops_permissions(env):
    with pytest.raises(BeeBotError):
        create(env, actor="chi")
    request = create(env, kind="leave")
    with pytest.raises(BeeBotError):
        env.service.approve_leave_request("binh", request["request_id"], "approve")
    with pytest.raises(BeeBotError):
        env.service.nominate_replacement("binh", request["request_id"], "chi", "nominate")
    with pytest.raises(BeeBotError):
        env.service.nominate_replacement("ops", request["request_id"], "chi", "unapproved")
    with pytest.raises(BeeBotError):
        env.service.run_maintenance("an")


def test_guessed_request_issue_invitation_ids_do_not_grant_access(env):
    request = create(env)
    item = invitation(env, "binh", request)
    with pytest.raises(BeeBotError):
        env.service.get_request_status("chi", request["request_id"])
    assert env.service.list_my_requests("chi") == []
    with pytest.raises(BeeBotError):
        env.service.respond_to_invitation("chi", item["invitation_id"], True, True, "spoof")
    issue = env.service.create_issue("an", "H210", "Private report", env.clock.now.isoformat(), "issue")
    with pytest.raises(BeeBotError):
        env.service.get_issue_status("chi", issue["issue_id"])
    assert env.schedule.get_assignment("a1")["coach_id"] == "an"


def test_my_schedule_and_outbox_contain_only_authorized_actor_data(env):
    create(env)
    assert all(row["coach_id"] == "binh" for row in env.service.get_my_assignments("binh"))
    assert env.service.get_my_notifications("chi") == []
    assert env.service.get_my_notifications("binh")


def test_no_mutation_without_sender_intent_confirmation(env):
    for kind in ("replacement", "leave", "swap"):
        with pytest.raises(BeeBotError):
            create(env, kind=kind, event_id=f"unconfirmed-{kind}", sender_confirmed=False)
    assert env.service.list_my_requests("ops") == []


def test_event_replay_is_durable_and_does_not_duplicate_notifications_or_writes(env):
    request = create(env)
    before = len(env.service.get_my_notifications("binh"))
    replay = create(env)
    assert replay["request_id"] == request["request_id"]
    assert len(env.service.get_my_notifications("binh")) == before
    write = Mock(wraps=env.schedule.apply_updates)
    env.schedule.apply_updates = write
    final = respond(env, "binh", request)
    assert final["status"] == "completed"
    notification_counts = {a: len(env.service.get_my_notifications(a)) for a in ("an", "binh", "ops")}
    restarted = BeeBotService(env.db, env.schedule, clock=lambda: env.clock.now)
    item = invitation(env, "binh", request)
    replay = restarted.respond_to_invitation("binh", item["invitation_id"], True, True, "respond-1")
    assert replay["status"] == "completed"
    assert write.call_count == 1
    assert restarted.get_request_status("an", request["request_id"])["status"] == "completed"
    assert {a: len(restarted.get_my_notifications(a)) for a in notification_counts} == notification_counts


def test_pending_invitation_request_and_issue_survive_restart(env):
    request = create(env)
    item = invitation(env, "binh", request)
    issue = env.service.create_issue("an", "H210", "Broken projector", env.clock.now.isoformat(), "issue")
    env.service.close()
    env.service = BeeBotService(env.db, env.schedule, clock=lambda: env.clock.now)
    assert env.service.get_request_status("an", request["request_id"])["status"] == "waiting_confirmation"
    assert invitation(env, "binh", request)["invitation_id"] == item["invitation_id"]
    assert env.service.get_issue_status("an", issue["issue_id"])["status"] == "open"
    assert respond(env, "binh", request)["status"] == "completed"


def test_replayed_event_cannot_be_reused_by_different_actor_or_operation(env):
    request = create(env)
    with pytest.raises(BeeBotError):
        create(env, actor="chi", assignment_id="a3", event_id="create-1")
    with pytest.raises(BeeBotError):
        env.service.cancel_request("an", request["request_id"], "Cancel", "create-1")
    assert env.service.get_request_status("an", request["request_id"])["status"] == "waiting_confirmation"
    assert env.service.list_my_requests("chi") == []


def test_process_loss_after_external_write_recovers_from_durable_intent(env):
    request = create(env)
    original_write = env.schedule.apply_updates

    def write_then_lose_process(updates, expected):
        original_write(updates, expected)
        raise SystemExit("Simulated process loss after external write")

    env.schedule.apply_updates = write_then_lose_process
    with pytest.raises(SystemExit):
        respond(env, "binh", request)
    env.service.close()  # Discards the uncommitted post-intent transaction.
    env.service = BeeBotService(env.db, env.schedule, clock=lambda: env.clock.now)
    write = Mock(wraps=original_write)
    env.schedule.apply_updates = write
    assert env.service.get_request_status("ops", request["request_id"])["status"] == "updating"
    env.service.run_maintenance("ops")
    assert env.service.get_request_status("ops", request["request_id"])["status"] == "completed"
    assert env.schedule.get_assignment("a1")["coach_id"] == "binh"
    assert write.call_count == 0
    item = invitation(env, "binh", request)
    replay = env.service.respond_to_invitation("binh", item["invitation_id"], True, True, "respond-1")
    assert replay["status"] == "completed"
    assert write.call_count == 0


def test_open_request_locks_assignment_and_cancel_releases_it(env):
    first = create(env)
    with pytest.raises(BeeBotError):
        create(env, event_id="duplicate-position")
    with pytest.raises(BeeBotError):
        env.service.cancel_request("ops", first["request_id"], "", "no-reason")
    assert env.service.cancel_request("an", first["request_id"], "No longer needed", "cancel")["status"] == "cancelled"
    old = invitation(env, "binh", first)
    with pytest.raises(BeeBotError):
        env.service.respond_to_invitation("binh", old["invitation_id"], True, True, "stale")
    second = create(env, event_id="new-position")
    assert second["request_id"] != first["request_id"]


def test_completed_request_cannot_cancel_or_reverse_schedule(env):
    request = create(env)
    respond(env, "binh", request)
    with pytest.raises(BeeBotError):
        env.service.cancel_request("ops", request["request_id"], "Reverse", "cancel")
    assert env.schedule.get_assignment("a1")["coach_id"] == "binh"


def test_withdraw_approval_invalidates_invitations_without_reversing_schedule(env):
    request = create(env, kind="leave")
    env.service.approve_leave_request("ops", request["request_id"], "approve")
    item = invitation(env, "binh", request)
    with pytest.raises(BeeBotError):
        env.service.withdraw_leave_approval("ops", request["request_id"], "", "blank")
    assert env.service.withdraw_leave_approval("ops", request["request_id"], "Approved wrong shift", "withdraw")["status"] == "approval_withdrawn"
    with pytest.raises(BeeBotError):
        env.service.respond_to_invitation("binh", item["invitation_id"], True, True, "late")
    assert env.schedule.get_assignment("a1")["coach_id"] == "an"


@pytest.mark.parametrize("boundary", ["24h", "start"])
def test_invitation_rejected_exactly_at_deadline(env, boundary):
    if boundary == "start":
        start = env.clock.now + timedelta(hours=3)
        env.edit("a1", starts_at=start.isoformat(), ends_at=(start + timedelta(hours=4)).isoformat())
    request = create(env)
    deadline = env.clock.now + timedelta(hours=24 if boundary == "24h" else 3)
    env.clock.now = deadline
    with pytest.raises(BeeBotError):
        respond(env, "binh", request)
    assert env.schedule.get_assignment("a1")["coach_id"] == "an"


def test_invitation_accepted_one_microsecond_before_deadline(env):
    request = create(env)
    env.clock.now += timedelta(hours=24, microseconds=-1)
    assert respond(env, "binh", request)["status"] == "completed"


def test_swap_deadline_uses_earlier_of_two_shifts(env):
    earlier = env.clock.now + timedelta(hours=2)
    env.edit("a2", starts_at=earlier.isoformat(), ends_at=(earlier + timedelta(hours=4)).isoformat())
    request = create(env, kind="swap")
    env.clock.now = earlier
    with pytest.raises(BeeBotError):
        respond(env, "binh", request)
    assert env.schedule.get_assignment("a1")["coach_id"] == "an"
    assert env.schedule.get_assignment("a2")["coach_id"] == "binh"


def test_inactive_recipient_cannot_accept_existing_invitation(env):
    request = create(env)
    payload = json.loads(env.path.read_text())
    next(person for person in payload["people"] if person["person_id"] == "binh")["active"] = False
    env.path.write_text(json.dumps(payload))
    with pytest.raises(BeeBotError):
        respond(env, "binh", request)
    assert env.schedule.get_assignment("a1")["coach_id"] == "an"


@pytest.mark.parametrize("room,description,detected", [("", "Broken", "2026-10-10T08:00:00+07:00"),
    ("H210", "", "2026-10-10T08:00:00+07:00"), ("H210", "Broken", "2026-10-10T08:00:00")])
def test_incomplete_issue_or_unzoned_time_creates_no_record_or_notification(env, room, description, detected):
    with pytest.raises(BeeBotError):
        env.service.create_issue("an", room, description, detected, "bad-issue")
    assert env.service.get_my_notifications("ops") == []


@pytest.mark.parametrize("field,value", [("coach_id", "chi"), ("room", "H205"), ("class_name", "Moved class")])
def test_manual_ops_relevant_edits_before_write_stop_old_snapshot(env, field, value):
    request = create(env)
    env.edit("a1", **{field: value})
    try:
        result = respond(env, "binh", request)
        assert result["status"] != "completed"
    except BeeBotError:
        pass
    row = env.schedule.get_assignment("a1")
    assert row[field] == value
    assert row["coach_id"] == (value if field == "coach_id" else "an")
    assert env.service.get_my_notifications("ops")


def test_manual_j_edit_survives_successful_bot_update(env):
    request = create(env)
    env.edit("a1", j="Ops just edited J")
    assert respond(env, "binh", request)["status"] == "completed"
    assert env.schedule.get_assignment("a1")["j"] == "Ops just edited J"


def test_new_recipient_conflict_added_after_invitation_stops_update(env):
    request = create(env)
    source = env.schedule.get_assignment("a1")
    env.edit("a3", coach_id="binh", starts_at=source["starts_at"], ends_at=source["ends_at"])
    try:
        result = respond(env, "binh", request)
        assert result["status"] != "completed"
    except BeeBotError:
        pass
    assert env.schedule.get_assignment("a1")["coach_id"] == "an"


def test_two_concurrent_full_acceptances_choose_exactly_one(env):
    request = create(env, kind="leave")
    env.service.approve_leave_request("ops", request["request_id"], "approve")
    invitations = {actor: invitation(env, actor, request)["invitation_id"] for actor in ("binh", "chi")}
    barrier = Barrier(2)

    def attempt(actor):
        service = BeeBotService(env.db, env.schedule, clock=lambda: env.clock.now)
        barrier.wait(timeout=10)
        try:
            return service.respond_to_invitation(actor, invitations[actor], True, True, f"accept-{actor}")
        except BeeBotError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ("binh", "chi")))
    assert sum(result is not None and result["status"] == "completed" for result in results) == 1
    assert env.schedule.get_assignment("a1")["coach_id"] in {"binh", "chi"}
    assert env.service.get_request_status("ops", request["request_id"])["status"] == "completed"


def test_cross_request_reservation_prevents_coach_double_booking_after_uncertain_write(env):
    first = create(env)
    source = env.schedule.get_assignment("a1")
    env.edit("a3", starts_at=source["starts_at"], ends_at=source["ends_at"])
    second = create(env, actor="chi", assignment_id="a3", event_id="second")
    env.schedule.next_write_fault = "timeout_before"
    try:
        first_result = respond(env, "binh", first)
        assert first_result["status"] != "completed"
    except BeeBotError:
        pass
    assert env.schedule.get_assignment("a1")["coach_id"] == "an"
    try:
        second_result = respond(env, "binh", second, event_id="second-accept")
        assert second_result["status"] != "completed"
    except BeeBotError:
        pass
    assert env.schedule.get_assignment("a3")["coach_id"] == "chi"


def test_first_reserved_candidate_blocks_later_candidate_on_failed_write(env):
    request = create(env, kind="leave")
    env.service.approve_leave_request("ops", request["request_id"], "approve")
    env.schedule.next_write_fault = "failure"
    try:
        result = respond(env, "binh", request)
        assert result["status"] != "completed"
    except BeeBotError:
        pass
    try:
        later = respond(env, "chi", request, event_id="later")
        assert later["status"] != "completed"
    except BeeBotError:
        pass
    assert env.schedule.get_assignment("a1")["coach_id"] == "an"
    assert env.service.get_my_notifications("ops")


@pytest.mark.parametrize("fault", ["timeout_before", "timeout_after", "partial", "failure"])
def test_swap_write_fault_reconciles_all_cells_never_blindly_retries(env, fault):
    request = create(env, kind="swap")
    env.schedule.next_write_fault = fault
    write = Mock(wraps=env.schedule.apply_updates)
    env.schedule.apply_updates = write
    try:
        result = respond(env, "binh", request)
    except BeeBotError:
        result = env.service.get_request_status("ops", request["request_id"])
    if fault == "timeout_after":
        assert result["status"] == "completed"
    else:
        assert result["status"] != "completed"
    expected = {
        "timeout_before": ("an", "binh"), "timeout_after": ("binh", "an"),
        "partial": ("binh", "binh"), "failure": ("an", "binh"),
    }[fault]
    assert tuple(env.schedule.get_assignment(key)["coach_id"] for key in ("a1", "a2")) == expected
    restarted = BeeBotService(env.db, env.schedule, clock=lambda: env.clock.now)
    reconciled = restarted.reconcile_request("ops", request["request_id"])
    assert (reconciled["status"] == "completed") == (fault == "timeout_after")
    restarted.run_maintenance("ops")
    assert write.call_count == 1
    assert tuple(env.schedule.get_assignment(key)["coach_id"] for key in ("a1", "a2")) == expected
    assert env.schedule.get_assignment("a1")["j"] == "Chưa cập nhật"
    assert env.schedule.get_assignment("a2")["j"] == "Bận"


def test_manual_completion_of_partial_swap_can_be_reconciled_without_another_write(env):
    request = create(env, kind="swap")
    env.schedule.next_write_fault = "partial"
    try:
        respond(env, "binh", request)
    except BeeBotError:
        pass
    env.edit("a2", coach_id="an")
    write = Mock(wraps=env.schedule.apply_updates)
    env.schedule.apply_updates = write
    assert env.service.reconcile_request("ops", request["request_id"])["status"] == "completed"
    assert write.call_count == 0


def test_maintenance_reports_near_start_expiry_and_summary_only_once_per_slot(env):
    start = env.clock.now + timedelta(hours=2)
    env.edit("a1", starts_at=start.isoformat(), ends_at=(start + timedelta(hours=4)).isoformat())
    request = create(env, kind="leave")
    env.service.run_maintenance("ops")
    first_count = len(env.service.get_my_notifications("ops"))
    env.service.run_maintenance("ops")
    assert len(env.service.get_my_notifications("ops")) == first_count
    env.clock.now = start
    env.service.run_maintenance("ops")
    assert len(env.service.get_my_notifications("ops")) > first_count
    assert env.service.get_request_status("ops", request["request_id"])["status"] != "completed"
    assert env.schedule.get_assignment("a1")["coach_id"] == "an"
