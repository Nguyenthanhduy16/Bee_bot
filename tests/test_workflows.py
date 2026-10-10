import json
from datetime import timedelta

import pytest

from bee_bot.errors import BeeBotError
from conftest import create, invitation, respond


def test_replacement_requires_direct_full_confirmation_preserves_j(env):
    request = create(env)
    assert env.schedule.get_assignment("a1")["coach_id"] == "an"
    partial = respond(env, "binh", request, no_other_busy=False)
    assert partial["status"] != "completed"
    assert env.schedule.get_assignment("a1")["coach_id"] == "an"
    final = respond(env, "binh", request, event_id="full")
    assert final["status"] == "completed"
    assert env.schedule.get_assignment("a1")["coach_id"] == "binh"
    assert env.schedule.get_assignment("a1")["j"] == "Chưa cập nhật"
    assert env.schedule.get_assignment("a2")["coach_id"] == "binh"
    for actor in ("an", "binh", "ops"):
        assert env.service.get_my_notifications(actor)


def test_leave_has_no_broadcast_before_approval_then_substitute_same_id(env):
    request = create(env, kind="leave")
    assert request["status"] == "waiting_ops_approval"
    assert all(not env.service.get_my_invitations(person) for person in ("binh", "chi", "dung"))
    previous_alerts = len(env.service.get_my_notifications("ops"))
    changed = env.service.add_substitute("an", request["request_id"], "binh", "add")
    assert changed["request_id"] == request["request_id"]
    assert changed["status"] == "waiting_confirmation"
    assert len(env.service.get_my_notifications("ops")) > previous_alerts
    assert respond(env, "binh", changed)["status"] == "completed"
    assert env.schedule.get_assignment("a1")["coach_id"] == "binh"
    with pytest.raises(BeeBotError):
        env.service.approve_leave_request("ops", request["request_id"], "late-approval")
    assert not env.service.get_my_invitations("chi")


def test_approved_leave_invites_multiple_one_decline_does_not_stop_search(env):
    request = create(env, kind="leave")
    approved = env.service.approve_leave_request("ops", request["request_id"], "approve")
    assert approved["status"] == "searching"
    assert invitation(env, "binh", request)
    assert invitation(env, "chi", request)
    declined = respond(env, "binh", request, accept=False)
    assert declined["status"] != "cancelled"
    assert respond(env, "chi", request, event_id="chi-full")["status"] == "completed"
    assert env.schedule.get_assignment("a1")["coach_id"] == "chi"


def test_partial_confirmation_does_not_hold_position(env):
    request = create(env, kind="leave")
    env.service.approve_leave_request("ops", request["request_id"], "approve")
    respond(env, "binh", request, no_other_busy=False)
    assert respond(env, "chi", request, event_id="chi-full")["status"] == "completed"
    assert env.schedule.get_assignment("a1")["coach_id"] == "chi"


def test_leave_without_eligible_candidates_alerts_ops_and_does_not_rebroadcast(env):
    source = env.schedule.get_assignment("a1")
    for assignment_id in ("a2", "a3", "a4"):
        env.edit(assignment_id, starts_at=source["starts_at"], ends_at=source["ends_at"])
    request = create(env, kind="leave")
    result = env.service.approve_leave_request("ops", request["request_id"], "approve")
    assert result["status"] == "needs_ops"
    assert all(not env.service.get_my_invitations(actor) for actor in ("binh", "chi", "dung"))
    assert any(item["event"] == "no_candidates" for item in env.service.get_my_notifications("ops"))
    env.service.run_maintenance("ops")
    assert all(not env.service.get_my_invitations(actor) for actor in ("binh", "chi", "dung"))
    assert env.schedule.get_assignment("a1")["coach_id"] == "an"


def test_all_declines_leave_request_for_ops_without_new_round(env):
    request = create(env, kind="leave")
    env.service.approve_leave_request("ops", request["request_id"], "approve")
    for actor in ("binh", "chi", "dung"):
        respond(env, actor, request, event_id=f"decline-{actor}", accept=False)
    assert env.service.get_request_status("ops", request["request_id"])["status"] == "needs_ops"
    counts = {actor: len(env.service.get_my_invitations(actor)) for actor in ("binh", "chi", "dung")}
    env.service.run_maintenance("ops")
    assert {actor: len(env.service.get_my_invitations(actor)) for actor in counts} == counts
    assert env.schedule.get_assignment("a1")["coach_id"] == "an"


def test_swap_two_assignments_one_request_and_j_preserved(env):
    request = create(env, kind="swap")
    assert respond(env, "binh", request)["status"] == "completed"
    assert env.schedule.get_assignment("a1")["coach_id"] == "binh"
    assert env.schedule.get_assignment("a2")["coach_id"] == "an"
    assert env.schedule.get_assignment("a1")["j"] == "Chưa cập nhật"
    assert env.schedule.get_assignment("a2")["j"] == "Bận"
    assert len(env.service.list_my_requests("an")) == 1


def test_swap_removes_donated_assignment_before_conflict_check(env):
    source = env.schedule.get_assignment("a1")
    env.edit("a2", starts_at=source["starts_at"], ends_at=source["ends_at"])
    request = create(env, kind="swap")
    assert respond(env, "binh", request)["status"] == "completed"
    assert env.schedule.get_assignment("a1")["coach_id"] == "binh"
    assert env.schedule.get_assignment("a2")["coach_id"] == "an"


def test_swap_sender_missing_no_other_busy_cannot_create(env):
    with pytest.raises(BeeBotError):
        create(env, kind="swap", sender_no_other_busy=False)
    assert env.service.list_my_requests("an") == []


def test_swap_checks_sender_received_schedule_too(env):
    target = env.schedule.get_assignment("a2")
    env.edit("a3", coach_id="an", starts_at=target["starts_at"], ends_at=target["ends_at"])
    request = create(env, kind="swap")
    assert respond(env, "binh", request)["status"] != "completed"
    assert env.schedule.get_assignment("a1")["coach_id"] == "an"
    assert env.schedule.get_assignment("a2")["coach_id"] == "binh"


def test_ops_nomination_requires_direct_recipient_response_and_invalidates_old_invite(env):
    request = create(env)
    old = invitation(env, "binh", request)
    env.service.nominate_replacement("ops", request["request_id"], "chi", "nominate")
    assert env.schedule.get_assignment("a1")["coach_id"] == "an"
    with pytest.raises(BeeBotError):
        env.service.respond_to_invitation("binh", old["invitation_id"], True, True, "stale")
    assert respond(env, "chi", request)["status"] == "completed"


def test_issue_mutation_replay_creates_one_issue_and_one_notification_set(env):
    original = env.service.create_issue("an", "H210", "Projector does not start", env.clock.now.isoformat(), "issue")
    notification_count = len(env.service.get_my_notifications("ops"))
    again = env.service.create_issue("an", "H210", "Projector does not start", env.clock.now.isoformat(), "issue")
    assert again["issue_id"] == original["issue_id"]
    assert len(env.service.get_my_notifications("ops")) == notification_count


def test_overlapping_programme_assignment_blocks_recipient_even_when_j_busy(env):
    source = env.schedule.get_assignment("a1")
    env.edit("a2", starts_at=source["starts_at"], ends_at=source["ends_at"], j="Bận")
    try:
        request = create(env)
        try:
            result = respond(env, "binh", request)
            assert result["status"] != "completed"
        except BeeBotError:
            pass
    except BeeBotError:
        pass
    assert env.schedule.get_assignment("a1")["coach_id"] == "an"


def test_touching_shift_boundaries_are_not_overlap(env):
    first = env.schedule.get_assignment("a1")
    from datetime import datetime
    end = datetime.fromisoformat(first["ends_at"])
    env.edit("a2", starts_at=end.isoformat(), ends_at=(end + timedelta(hours=4)).isoformat())
    request = create(env)
    assert respond(env, "binh", request)["status"] == "completed"


def test_issue_without_photo_resolution_requires_result_and_tracks_actor_time(env):
    issue = env.service.create_issue("an", "H210", "Projector does not start", env.clock.now.isoformat(), "issue")
    assert issue["status"] == "open"
    processing = env.service.update_issue("ops", issue["issue_id"], "processing", "processing")
    assert processing["status"] != "resolved"
    with pytest.raises(BeeBotError):
        env.service.update_issue("ops", issue["issue_id"], "resolved", "bad-resolution")
    resolved = env.service.update_issue("ops", issue["issue_id"], "resolved", "resolution", result="Replaced power cable")
    assert resolved["status"] == "resolved"
    assert "Replaced power cable" in json.dumps(resolved)
    assert "ops" in json.dumps(resolved)
    assert "2026-10-10" in json.dumps(resolved)
    assert env.service.get_issue_status("an", issue["issue_id"])["status"] == "resolved"


def test_issues_are_not_auto_merged_and_recurrence_links_previous(env):
    first = env.service.create_issue("an", "H210", "Projector failed", env.clock.now.isoformat(), "first")
    second = env.service.create_issue("an", "H210", "Air conditioner failed", env.clock.now.isoformat(), "second")
    again = env.service.create_issue("an", "H210", "Projector failed again", env.clock.now.isoformat(), "again", related_issue_id=first["issue_id"])
    assert len({first["issue_id"], second["issue_id"], again["issue_id"]}) == 3
    assert first["issue_id"] in json.dumps(again)


def test_owner_can_cancel_issue_before_processing_only(env):
    first = env.service.create_issue("an", "H210", "Reported by mistake", env.clock.now.isoformat(), "first")
    assert env.service.update_issue("an", first["issue_id"], "cancelled", "cancel-first", result="Reported wrong room")["status"] == "cancelled"
    second = env.service.create_issue("an", "H210", "Needs inspection", env.clock.now.isoformat(), "second")
    env.service.update_issue("ops", second["issue_id"], "processing", "processing")
    with pytest.raises(BeeBotError):
        env.service.update_issue("an", second["issue_id"], "cancelled", "cancel-second")
    with pytest.raises(BeeBotError):
        env.service.update_issue("ops", second["issue_id"], "cancelled", "ops-no-reason")
    assert env.service.update_issue("ops", second["issue_id"], "cancelled", "ops-cancel", result="Duplicate checked manually")["status"] == "cancelled"
