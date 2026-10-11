"""S8: service reconciliation must not complete an applied-but-invalid result (JsonSchedule path)."""
import pytest

from bee_bot.errors import BeeBotError
from bee_bot.service import BeeBotService
from conftest import create, respond


def ops_edit_during_write(env, monkeypatch, **edits):
    """Land the write, then let ops change other rows before the service reconciles."""
    original = env.schedule.apply_updates

    def apply(updates, expected):
        original(updates, expected)
        for assignment_id, fields in edits.items():
            env.edit(assignment_id, **fields)
    monkeypatch.setattr(env.schedule, 'apply_updates', apply)


def slot_of(env, assignment_id):
    a = env.schedule.get_assignment(assignment_id)
    return {'starts_at': a['starts_at'], 'ends_at': a['ends_at']}


def ops_alerts(env, request):
    return [n for n in env.service.get_my_notifications('ops')
            if n['event'] == 'reconciliation_required' and n['request_id'] == request['id']]


def test_replacement_recipient_overlap_after_write_stays_reconciliation_required(env, monkeypatch):
    request = create(env)  # a1 an -> binh
    ops_edit_during_write(env, monkeypatch, a4={'coach_id': 'binh', **slot_of(env, 'a1')})
    result = respond(env, 'binh', request)
    assert (result['status'], result['reason']) == ('reconciliation_required', 'APPLIED_SCHEDULE_CONFLICT')
    assert result['reserved_for'] == 'binh'
    assert env.schedule.get_assignment('a1')['revision'] == 2  # exactly one write
    for _ in range(2):
        env.service.run_maintenance('ops')
        assert env.service.reconcile_request('ops', request['id'])['status'] == 'reconciliation_required'
    restarted = BeeBotService(env.db, env.schedule, clock=lambda: env.clock.now)
    try:
        restarted.run_maintenance('ops')
        status = restarted.get_request_status('ops', request['id'])
        assert (status['status'], status['reason']) == ('reconciliation_required', 'APPLIED_SCHEDULE_CONFLICT')
    finally:
        restarted.close()
    assert env.schedule.get_assignment('a1')['revision'] == 2  # never rewritten or rolled back
    assert env.schedule.get_assignment('a1')['coach_id'] == 'binh'
    assert len(ops_alerts(env, request)) == 1  # alerted once, not on every pass
    with pytest.raises(BeeBotError) as error:  # slot stays held
        create(env, actor='binh', kind='leave', event_id='dup-1')
    assert error.value.code == 'DUPLICATE_REQUEST'


def test_conflict_resolved_by_ops_then_reconcile_completes(env, monkeypatch):
    request = create(env)
    ops_edit_during_write(env, monkeypatch, a4={'coach_id': 'binh', **slot_of(env, 'a1')})
    respond(env, 'binh', request)
    env.edit('a4', coach_id='dung')  # ops resolves the double booking by hand
    assert env.service.reconcile_request('ops', request['id'])['status'] == 'completed'
    assert env.schedule.get_assignment('a1')['revision'] == 2


@pytest.mark.parametrize('side, coach, slot', [('recipient', 'binh', 'a1'), ('owner', 'an', 'a2')])
def test_swap_checks_both_planned_coaches(env, monkeypatch, side, coach, slot):
    request = create(env, kind='swap')  # a1 an <-> a2 binh
    ops_edit_during_write(env, monkeypatch, a4={'coach_id': coach, **slot_of(env, slot)})
    result = respond(env, 'binh', request)
    assert (result['status'], result['reason']) == ('reconciliation_required', 'APPLIED_SCHEDULE_CONFLICT')
    assert [env.schedule.get_assignment(a)['revision'] for a in ('a1', 'a2')] == [2, 2]


def test_unrelated_change_does_not_block_completion(env, monkeypatch):
    request = create(env)
    ops_edit_during_write(env, monkeypatch, a4={'coach_id': 'chi'})  # day 5, no overlap
    assert respond(env, 'binh', request)['status'] == 'completed'


def test_target_mismatch_keeps_original_reason(env):
    request = create(env)
    env.schedule.next_write_fault = 'timeout_before'
    result = respond(env, 'binh', request)
    assert (result['status'], result['reason']) == ('reconciliation_required', 'WRITE_NOT_VERIFIED')


def test_schedule_read_failure_during_guard_is_not_completion(env, monkeypatch):
    request = create(env)
    written = {'done': False}
    apply, listing = env.schedule.apply_updates, env.schedule.list_assignments

    def apply_then_mark(updates, expected):
        apply(updates, expected)
        written['done'] = True

    def flaky():
        if written['done']:
            raise BeeBotError('SCHEDULE_UNAVAILABLE', 'synthetic')
        return listing()
    monkeypatch.setattr(env.schedule, 'apply_updates', apply_then_mark)
    # Keep target reads available independently; JsonSchedule.get_assignment
    # normally uses list_assignments too, failing before the guard is reached.
    monkeypatch.setattr(env.schedule, 'get_assignment',
                        lambda identifier: next(a for a in listing() if a['assignment_id'] == identifier))
    monkeypatch.setattr(env.schedule, 'list_assignments', flaky)
    result = respond(env, 'binh', request)
    assert (result['status'], result['reason']) == ('reconciliation_required', 'APPLIED_VERIFICATION_FAILED')
    assert env.schedule.get_assignment('a1')['revision'] == 2


@pytest.mark.parametrize('outcome', [False, None, 'true', 'raise'])
def test_adapter_verification_requires_explicit_success(env, monkeypatch, outcome):
    request = create(env)
    calls = []

    def verify(updates, expected):
        calls.append((updates, expected))
        if outcome == 'raise':
            raise BeeBotError('SHEETS_PROVENANCE_REJECTED', 'synthetic')
        return outcome

    monkeypatch.setattr(env.schedule, 'verify_applied', verify, raising=False)
    result = respond(env, 'binh', request)
    assert (result['status'], result['reason'], result['reserved_for']) == (
        'reconciliation_required', 'APPLIED_VERIFICATION_FAILED', 'binh')
    assert calls == [({'a1': 'binh'}, request['snapshots'])]
    for _ in range(2):
        env.service.run_maintenance('ops')
        env.service.reconcile_request('ops', request['id'])
    assert len(ops_alerts(env, request)) == 1
    assert env.schedule.get_assignment('a1')['revision'] == 2


@pytest.mark.parametrize('drift', ['room', 'coach', 'missing', 'duplicate'])
def test_target_drift_between_target_and_full_schedule_reads_blocks_completion(env, monkeypatch, drift):
    request = create(env)
    listing = env.schedule.list_assignments
    original_apply = env.schedule.apply_updates
    written = False

    def apply(updates, expected):
        nonlocal written
        original_apply(updates, expected)
        written = True

    def changed_listing():
        rows = listing()
        if written:
            target = next(a for a in rows if a['assignment_id'] == 'a1')
            if drift == 'room':
                target['room'] = 'H999'
            elif drift == 'coach':
                target['coach_id'] = 'chi'
            elif drift == 'missing':
                rows.remove(target)
            else:
                rows.append(dict(target))
        return rows

    monkeypatch.setattr(env.schedule, 'apply_updates', apply)
    monkeypatch.setattr(env.schedule, 'get_assignment',
                        lambda identifier: next(a for a in listing() if a['assignment_id'] == identifier))
    monkeypatch.setattr(env.schedule, 'list_assignments', changed_listing)
    result = respond(env, 'binh', request)
    assert (result['status'], result['reason']) == ('reconciliation_required', 'APPLIED_VERIFICATION_FAILED')
    assert env.schedule.get_assignment('a1')['revision'] == 2


@pytest.mark.parametrize('kind', ['replacement', 'leave'])
def test_locked_cancel_and_withdraw_reconcile_without_releasing_or_writing(env, monkeypatch, kind):
    request = create(env, kind=kind)
    if kind == 'leave':
        request = env.service.approve_leave_request('ops', request['id'], 'approve-1')
    ops_edit_during_write(env, monkeypatch, a4={'coach_id': 'binh', **slot_of(env, 'a1')})
    respond(env, 'binh', request)
    if kind == 'leave':
        result = env.service.withdraw_leave_approval('ops', request['id'], 'synthetic reason', 'withdraw-1')
    else:
        result = env.service.cancel_request('an', request['id'], 'synthetic reason', 'cancel-1')
    assert result['status'] == 'reconciliation_required'
    status = env.service.get_request_status('ops', request['id'])
    assert (status['status'], status['reason'], status['reserved_for']) == (
        'reconciliation_required', 'APPLIED_SCHEDULE_CONFLICT', 'binh')
    assert env.schedule.get_assignment('a1')['revision'] == 2
    assert len(ops_alerts(env, request)) == 1


def test_uncertain_write_with_applied_overlap_keeps_reservation(env, monkeypatch):
    request = create(env)
    apply = env.schedule.apply_updates

    def uncertain(updates, expected):
        apply(updates, expected)
        env.edit('a4', coach_id='binh', **slot_of(env, 'a1'))
        raise BeeBotError('WRITE_UNCERTAIN', 'synthetic timeout after write')

    monkeypatch.setattr(env.schedule, 'apply_updates', uncertain)
    result = respond(env, 'binh', request)
    assert (result['status'], result['reason'], result['write_error']) == (
        'reconciliation_required', 'APPLIED_SCHEDULE_CONFLICT', 'WRITE_UNCERTAIN')
    assert result['reserved_for'] == 'binh' and env.schedule.get_assignment('a1')['revision'] == 2
