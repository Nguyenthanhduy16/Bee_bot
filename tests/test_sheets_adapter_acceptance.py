"""QA-SHEETS independent acceptance of the repaired frozen Core checkpoint.

Synthetic tab only; real BeeBotService on top; no network, SDK or credentials.
S1–S8 assert desired guards. LIMITATION tests explicitly demonstrate residual
no-CAS/ABA windows. The complete original 40-case source is archived verbatim
in docs/QA_REVIEW_2026-10-11.md before conversion.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from bee_bot.errors import BeeBotError
from bee_bot.service import BeeBotService
from bee_bot.sheets_adapter import SheetsScheduleAdapter, check_provenance
from bee_bot.sheets_copy_transport import SyntheticSheetTransport, synthetic_roster, write_synthetic_tab
from bee_bot.sheets_import import ZONE

NOW = datetime(2026, 10, 10, 8, tzinfo=ZONE)
DAY1 = (NOW + timedelta(days=3)).date()
DAY2 = DAY1 + timedelta(days=1)
ALLOWED = {'synthetic-bee-bot'}
CONTRACT_KEYS = {'assignment_id', 'shift_id', 'coach_id', 'starts_at', 'ends_at', 'room', 'site',
                 'class_name', 'j', 'revision'}
# Synthetic layout (1-based rows): 2 day-1 header, 4/5 merged Track 1 CS1 Sáng (An, Chi),
# 6 Binh Chiều, 7 day-2 header, 9 Chi Sáng, 10 Dung Sáng, 11 vacant Sáng.


@pytest.fixture
def env(tmp_path):
    sheet, db = tmp_path / 'tab.json', tmp_path / 'state.db'
    write_synthetic_tab(sheet, DAY1)
    state = SimpleNamespace(sheet=sheet, db=db, services=[])

    def open_service():
        state.transport = SyntheticSheetTransport(sheet)
        state.adapter = SheetsScheduleAdapter(state.transport, synthetic_roster(), ALLOWED)
        state.service = BeeBotService(db, state.adapter, clock=lambda: NOW)
        state.services.append(state.service)
        return state.service

    state.open = open_service
    open_service()
    state.ids = {a['source_locator']['row']: a['assignment_id'] for a in state.adapter.list_assignments()}
    yield state
    for service in state.services:
        service.close()


def by_row(env):
    return {a['source_locator']['row']: a for a in env.adapter.list_assignments()}


def cells(env):
    return [(r['anchor'], dict(r['cells'])) for r in env.transport.read_tab()['rows']]


def replacement(env, owner, row, recipient, event):
    service = env.service
    request = service.create_change_request(owner, 'replacement', env.ids[row], event + '-c',
                                            substitute_id=recipient, sender_confirmed=True)
    invite = next(i['invitation_id'] for i in service.get_my_invitations(recipient)
                  if i['request_id'] == request['id'])
    return request, lambda: service.respond_to_invitation(recipient, invite, True, True, event + '-r')


def swap(env, event='s'):
    service = env.service
    request = service.create_change_request('an', 'swap', env.ids[4], event + '-c', target_assignment_id=env.ids[10],
                                            sender_confirmed=True, sender_no_other_busy=True)
    invite = next(i['invitation_id'] for i in service.get_my_invitations('dung')
                  if i['request_id'] == request['id'])
    return request, lambda: service.respond_to_invitation('dung', invite, True, True, event + '-r')


def reconciliation_alerts(env, request):
    return [n for n in env.service.get_my_notifications('ops')
            if n['event'] == 'reconciliation_required' and n['request_id'] == request['id']]


def assert_locked_across_reconciliation(env, request, reserved, writes, reason):
    """Exercise the real persisted state through ops reads and an actual service reopen."""
    planned = env.service.get_request_status('ops', request['id'])['planned_updates']
    assert len(reconciliation_alerts(env, request)) == 1
    for _ in range(2):
        status = env.service.reconcile_request('ops', request['id'])
        assert (status['status'], status['reason'], status['reserved_for']) == (
            'reconciliation_required', reason, reserved)
    env.service.close()
    env.open()
    for _ in range(2):
        env.service.run_maintenance('ops')
        status = env.service.reconcile_request('ops', request['id'])
        assert (status['status'], status['reason'], status['reserved_for']) == (
            'reconciliation_required', reason, reserved)
        assert status['planned_updates'] == planned
    assert len(env.transport.write_log()) == writes
    assert len(reconciliation_alerts(env, request)) == 1
    identifier, coach = next(iter(planned.items()))
    with pytest.raises(BeeBotError) as error:
        env.service.create_change_request(coach, 'leave', identifier, 'reservation-check', sender_confirmed=True)
    assert error.value.code == 'DUPLICATE_REQUEST'


# -- service-compatible D/J --------------------------------------------------

def test_assignments_satisfy_schedule_contract_and_time_rules(env):
    rows = by_row(env)
    for assignment in rows.values():
        assert CONTRACT_KEYS <= set(assignment)
        assert isinstance(assignment['revision'], int)
        start, end = datetime.fromisoformat(assignment['starts_at']), datetime.fromisoformat(assignment['ends_at'])
        assert start.tzinfo is not None and start < end
    assert rows[4]['starts_at'] == datetime(DAY1.year, DAY1.month, DAY1.day, 9, tzinfo=ZONE).isoformat()
    assert rows[6]['ends_at'] == datetime(DAY1.year, DAY1.month, DAY1.day, 18, tzinfo=ZONE).isoformat()
    assert rows[9]['starts_at'].startswith(DAY2.isoformat())
    assert [rows[r]['coach_id'] for r in (4, 5, 6, 9, 10, 11)] == ['an', 'chi', 'binh', 'chi', 'dung', None]


def test_d_name_matching_is_normalized_and_write_uses_roster_spelling_keeping_j(env):
    env.transport.set_cell(9, 'D', '  synthetic   CHI ')
    assert by_row(env)[9]['coach_id'] == 'chi'
    env.ids = {a['source_locator']['row']: a['assignment_id'] for a in env.adapter.list_assignments()}
    before = cells(env)
    _, respond = replacement(env, 'chi', 9, 'binh', 'norm')
    assert respond()['status'] == 'completed'
    after = cells(env)
    changed = [(i, c) for i, (old, new) in enumerate(zip(before, after)) for c in 'ABCDEFGHIJ' if old[1].get(c) != new[1].get(c)]
    assert changed == [(8, 'D')] and after[8][1]['D'] == 'Synthetic Binh'


def test_j_value_change_never_changes_revision_or_blocks(env):
    original = by_row(env)[9]
    env.transport.set_cell(9, 'J', 'Bận')
    assert by_row(env)[9]['revision'] == original['revision']
    _, respond = replacement(env, 'chi', 9, 'binh', 'j')
    assert respond()['status'] == 'completed'
    assert env.transport.read_tab()['rows'][8]['cells']['J'] == 'Bận'


# -- complete / ambiguous scope ----------------------------------------------

@pytest.mark.parametrize('a_value', [None, 'x', 'STT'])
def test_S1_populated_row_with_invalid_stt_blocks_hidden_overlap(env, a_value):
    """Includes the populated STT header edge: it must never hide a recipient's shift."""
    env.transport.set_cell(11, 'A', a_value)
    env.transport.set_cell(11, 'D', 'Synthetic Binh')  # Binh really teaches day-2 Sáng here.
    coverage = env.adapter.coverage()
    assert coverage['writable'] is False
    assert {'row': 11, 'code': 'UNCLASSIFIED_ROW'} in coverage['diagnostics']
    assert 11 not in by_row(env)
    _, respond = replacement(env, 'chi', 9, 'binh', 'hidden')  # Also day-2 Sáng: a real double booking.
    result = respond()
    assert (result['status'], result['reason']) == ('write_failed', 'SCHEDULE_SCOPE_INCOMPLETE')
    assert env.transport.write_log() == []
    rows = env.transport.read_tab()['rows']
    assert rows[8]['cells']['D'] == 'Synthetic Chi'
    assert rows[10]['cells']['D'] == 'Synthetic Binh'


@pytest.mark.parametrize('a_value', ['3', ' 3 ', '3.0', 3.0])
def test_S1_integer_stt_strings_are_visible_and_block_overlap(env, a_value):
    env.transport.set_cell(11, 'A', a_value)
    env.transport.set_cell(11, 'D', 'Synthetic Binh')
    assert env.adapter.coverage()['writable'] is True
    assert by_row(env)[11]['coach_id'] == 'binh'
    _, respond = replacement(env, 'chi', 9, 'binh', 'string-stt')
    result = respond()
    assert (result['status'], result['reason']) == ('needs_ops', 'SCHEDULE_CONFLICT')
    assert env.transport.write_log() == []


def test_control_numeric_stt_row_blocks_the_same_double_booking(env):
    env.transport.set_cell(11, 'D', 'Synthetic Binh')
    _, respond = replacement(env, 'chi', 9, 'binh', 'visible')
    result = respond()
    assert (result['status'], result.get('reason')) == ('needs_ops', 'SCHEDULE_CONFLICT')
    assert env.transport.write_log() == []
    assert env.transport.read_tab()['rows'][8]['cells']['D'] == 'Synthetic Chi'


@pytest.mark.parametrize('header', ['T3 - {d:%d/%m/%Y}', '{d:%d/%m/%Y} (Thứ 3)', 'Thu 3 - {d:%d/%m/%Y}'])
def test_S2_unrecognised_date_header_blocks_instead_of_inheriting_day(env, header):
    original = env.adapter.get_assignment(env.ids[9])
    env.transport.set_cell(7, 'A', header.format(d=DAY2))
    coverage = env.adapter.coverage()
    assert coverage['writable'] is False
    assert {'row': 7, 'code': 'INVALID_DATE_HEADER'} in coverage['diagnostics']
    assert 9 not in by_row(env)
    with pytest.raises(BeeBotError) as error:
        env.adapter.apply_updates({env.ids[9]: 'binh'}, {env.ids[9]: original})
    assert error.value.code == 'SCHEDULE_SCOPE_INCOMPLETE'
    assert env.transport.write_log() == []


def test_rows_before_any_date_header_and_cross_block_merges_fail_closed(env):
    env.transport.set_cell(2, 'A', 'Lịch tuần')  # Day-1 header lost.
    assert {d['code'] for d in env.adapter.coverage()['diagnostics']} == {'INVALID_CANONICAL_ROW'}
    write_synthetic_tab(env.sheet, DAY1)
    data_merge = {'start': 6, 'end': 9, 'columns': ['B', 'C', 'F', 'G']}  # Spans the day-2 header.
    import json
    raw = json.loads(env.sheet.read_text(encoding='utf-8'))
    raw['merges'].append(data_merge)
    env.sheet.write_text(json.dumps(raw, ensure_ascii=False), encoding='utf-8')
    coverage = env.adapter.coverage()
    assert coverage['writable'] is False and {'row': 9, 'code': 'INVALID_CANONICAL_ROW'} in coverage['diagnostics']


# -- ID relocation -------------------------------------------------------------

def test_anchor_moved_to_other_class_row_stops_open_request(env):
    request, respond = replacement(env, 'chi', 9, 'binh', 'move')
    env.transport.set_anchor(9, 'anc-moved')
    env.transport.set_anchor(6, 'anc-004')  # The id now points at Binh's day-1 afternoon row.
    result = respond()
    assert result['status'] != 'completed'
    assert env.transport.write_log() == []


def test_row_insertion_above_target_keeps_id_and_writes_relocated_cell(env):
    target = env.ids[10]
    env.transport.insert_row(8, {'A': 'ghi chú'})
    assert by_row(env)[11]['assignment_id'] == target
    _, respond = replacement(env, 'dung', 10, 'binh', 'ins')
    assert respond()['status'] == 'completed'
    assert env.transport.write_log() == [{'anchor': 'anc-005', 'column': 'D', 'value': 'Synthetic Binh'}]


# -- malformed rows / tab --------------------------------------------------------

@pytest.mark.parametrize('daypart', ['Sang', 'Tối', None])
def test_unknown_daypart_blocks_scope(env, daypart):
    env.transport.set_cell(10, 'G', daypart)
    assert env.adapter.coverage()['writable'] is False


def test_numeric_or_multi_name_d_is_unknown_and_blocks(env):
    env.transport.set_cell(10, 'D', 'Synthetic Dung, Synthetic An')
    assert {d['code'] for d in env.adapter.coverage()['diagnostics']} == {'UNKNOWN_ROSTER_NAME'}
    env.transport.set_cell(10, 'D', 5)
    assert {d['code'] for d in env.adapter.coverage()['diagnostics']} == {'UNKNOWN_ROSTER_NAME'}


def test_S6_malformed_merge_raises_controlled_error(env):
    import json
    raw = json.loads(env.sheet.read_text(encoding='utf-8'))
    raw['merges'].append({'start': 9, 'end': 10})
    env.sheet.write_text(json.dumps(raw, ensure_ascii=False), encoding='utf-8')
    with pytest.raises(BeeBotError) as error:
        env.adapter.coverage()
    assert error.value.code == 'SCHEDULE_MALFORMED'
    assert env.transport.write_log() == []


# -- provenance / source denylist --------------------------------------------------

def test_copy_of_denied_source_is_accepted_but_source_itself_never(env):
    copy = {'kind': 'test_copy', 'spreadsheet_id': 'placeholder-copy', 'tab': 't', 'copy_of': 'placeholder-src'}
    assert check_provenance(copy, {'placeholder-copy'}, {'placeholder-src'})
    for provenance in ({**copy, 'spreadsheet_id': 'placeholder-src', 'copy_of': 'placeholder-x'},
                       {'kind': 'synthetic', 'spreadsheet_id': 'placeholder-src', 'tab': 't', 'contains_real_data': False}):
        with pytest.raises(BeeBotError):
            check_provenance(provenance, {'placeholder-src'}, {'placeholder-src'})


def test_S7_denylist_cannot_be_bypassed_with_whitespace(env):
    variant = {'kind': 'test_copy', 'spreadsheet_id': 'placeholder-src ', 'tab': 't', 'copy_of': 'placeholder-x'}
    with pytest.raises(BeeBotError) as error:
        check_provenance(variant, {'placeholder-src '}, {'placeholder-src'})
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'


def test_provenance_flip_before_acceptance_rejects_without_reservation_or_write(env):
    request, respond = replacement(env, 'chi', 9, 'binh', 'prov')
    env.transport.set_provenance({**env.transport.provenance(), 'contains_real_data': True})
    with pytest.raises(BeeBotError) as error:
        respond()
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'
    assert env.service.store.get('request', request['id'])['status'] == 'waiting_confirmation'
    assert env.transport.write_log() == []


def test_LIMITATION_provenance_policy_flip_inside_call_lands_but_stays_uncertain(env):
    """Gate lives in the adapter only: a flip after the per-write check still lands in the
    transport; the service correctly refuses to call it complete."""
    _, respond = replacement(env, 'chi', 9, 'binh', 'prov2')
    env.transport.script = [{'before': lambda t: t.set_provenance({**t.provenance(), 'contains_real_data': True})}]
    assert respond()['status'] == 'reconciliation_required'
    assert len(env.transport.write_log()) == 1


# -- mid-write drift -------------------------------------------------------------------

def test_S5_ops_edit_between_swap_writes_preserved_and_second_write_stops(env):
    _, respond = swap(env)
    env.transport.script = [{'after': lambda t: t.set_cell(t.row_of('anc-005'), 'D', 'Synthetic Chi')}, {}]
    assert respond()['status'] == 'reconciliation_required'
    assert env.transport.read_tab()['rows'][9]['cells']['D'] == 'Synthetic Chi'
    assert env.transport.write_log() == [{'anchor': 'anc-001', 'column': 'D', 'value': 'Synthetic Dung'}]


def test_class_drift_between_swap_writes_is_caught_by_service_reconcile(env):
    _, respond = swap(env)
    env.transport.script = [{'after': lambda t: t.set_cell(t.row_of('anc-005'), 'G', 'Chiều')}, {}]
    result = respond()
    assert result['status'] == 'reconciliation_required'
    assert len(env.transport.write_log()) == 1  # The new per-write check stops the second cell.


# -- partial / timeout / restart: never retried ---------------------------------------------

def test_timeout_after_on_second_swap_write_completes_by_read_only_reconcile(env):
    _, respond = swap(env)
    env.transport.script = [{}, {'fault': 'timeout_after'}]
    assert respond()['status'] == 'completed'
    assert len(env.transport.write_log()) == 2


@pytest.mark.parametrize('fault, writes', [('timeout_before', 1), ('reject', 1)])
def test_partial_swap_survives_repeated_restart_and_maintenance_without_write(env, fault, writes):
    request, respond = swap(env)
    env.transport.script = [{}, {'fault': fault}]
    assert respond()['status'] == 'reconciliation_required'
    for _ in range(3):
        service = env.open()
        service.run_maintenance('ops')
        assert service.get_request_status('ops', request['id'])['status'] == 'reconciliation_required'
    assert len(env.transport.write_log()) == writes


def test_clear_rejection_keeps_reservation_and_is_never_retried(env):
    request, respond = replacement(env, 'chi', 9, 'binh', 'rej')
    env.transport.script = [{'fault': 'reject'}]
    result = respond()
    assert (result['status'], result['reason']) == ('write_failed', 'WRITE_FAILED')
    service = env.open()
    service.run_maintenance('ops')
    status = service.get_request_status('ops', request['id'])
    assert status['status'] == 'write_failed' and status.get('reserved_for') == 'binh'
    assert env.transport.write_log() == []


# -- overlap and concurrency --------------------------------------------------------------

def test_adapter_rejects_overlapping_recipient_even_if_service_check_is_bypassed(env):
    original = env.adapter.get_assignment(env.ids[9])
    with pytest.raises(BeeBotError) as error:
        env.adapter.apply_updates({env.ids[9]: 'dung'}, {env.ids[9]: original})  # Dung has row 10, same slot.
    assert error.value.code == 'SCHEDULE_CONFLICT' and env.transport.write_log() == []


def test_swap_overlap_uses_resulting_schedule(env):
    # An (row 4, day-1 Sáng) and Dung (row 10, day-2 Sáng) swapping does not self-conflict.
    _, respond = swap(env)
    assert respond()['status'] == 'completed'


def test_two_service_instances_race_for_one_leave_position_single_write(env):
    service = env.service
    request = service.create_change_request('chi', 'leave', env.ids[9], 'leave-c', sender_confirmed=True)
    service.approve_leave_request('ops', request['id'], 'leave-a')
    other = BeeBotService(env.db, SheetsScheduleAdapter(SyntheticSheetTransport(env.sheet), synthetic_roster(), ALLOWED),
                          clock=lambda: NOW)
    env.services.append(other)
    invites = {i['recipient_id']: i['invitation_id'] for i in service.store.all('invitation')
               if i['request_id'] == request['id']}
    assert {'binh', 'an'} <= set(invites)
    first = service.respond_to_invitation('binh', invites['binh'], True, True, 'race-b')
    assert first['status'] == 'completed'
    with pytest.raises(BeeBotError):
        other.respond_to_invitation('an', invites['an'], True, True, 'race-a')
    assert len(env.transport.write_log()) == 1


# -- Lead questions: identity pinning and post-write verification scope -----------------

TWO_COPIES = ALLOWED | {'synthetic-other'}


def pinned_env(env):
    """Same synthetic tab, adapter allowlisting two synthetic workbooks."""
    env.transport = SyntheticSheetTransport(env.sheet)
    env.adapter = SheetsScheduleAdapter(env.transport, synthetic_roster(), TWO_COPIES)
    env.service = BeeBotService(env.db, env.adapter, clock=lambda: NOW)
    env.services.append(env.service)
    env.ids = {a['source_locator']['row']: a['assignment_id'] for a in env.adapter.list_assignments()}
    return env


@pytest.mark.parametrize('switch', [{'spreadsheet_id': 'synthetic-other'}, {'tab': 'Other tab'}])
def test_S3_pinned_identity_blocks_second_swap_write_after_switch(env, switch):
    pinned_env(env)
    _, respond = swap(env)
    env.transport.script = [{'after': lambda t: t.set_provenance({**t.provenance(), **switch})}, {}]
    assert respond()['status'] == 'reconciliation_required'
    assert len(env.transport.write_log()) == 1
    assert env.transport.read_tab()['rows'][9]['cells']['D'] == 'Synthetic Dung'


@pytest.mark.parametrize('switch', [{'spreadsheet_id': 'synthetic-other'}, {'tab': 'Other tab'}])
def test_identity_switch_before_write_is_caught_by_id_derivation(env, switch):
    pinned_env(env)
    request, respond = replacement(env, 'chi', 9, 'binh', 'pin')
    env.transport.set_provenance({**env.transport.provenance(), **switch})
    with pytest.raises(BeeBotError) as error:
        respond()
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'
    assert env.transport.write_log() == []


@pytest.mark.parametrize('column, value', [('F', 'H999'), ('G', 'Chiều')])
def test_confirmed_detail_change_after_write_before_readback(env, column, value):
    """Adapter and service both refuse completion when confirmed details change."""
    request, respond = replacement(env, 'chi', 9, 'binh', 'detail')
    env.transport.script = [{'after': lambda t: t.set_cell(9, column, value)}]
    assert respond()['status'] == 'reconciliation_required'
    env2 = env.adapter.get_assignment(env.ids[9])
    assert env2['coach_id'] == 'binh'
    assert len(env.transport.write_log()) == 1
    assert_locked_across_reconciliation(env, request, 'binh', 1, 'WRITE_NOT_VERIFIED')


def test_S4_adapter_readback_alone_rejects_detail_change(env):
    original = env.adapter.get_assignment(env.ids[9])
    env.transport.script = [{'after': lambda t: t.set_cell(9, 'F', 'H999')}]
    with pytest.raises(BeeBotError) as error:
        env.adapter.apply_updates({env.ids[9]: 'binh'}, {env.ids[9]: original})
    assert error.value.code == 'WRITE_UNCERTAIN'
    assert len(env.transport.write_log()) == 1


def test_S4_S8_overlap_in_write_window_remains_locked_through_reconcile(env):
    request, respond = replacement(env, 'chi', 9, 'binh', 'overlap')
    env.transport.script = [{'before': lambda t: t.set_cell(11, 'D', 'Synthetic Binh')}]
    result = respond()
    assert (result['status'], result['reason']) == ('reconciliation_required', 'APPLIED_SCHEDULE_CONFLICT')
    rows = env.transport.read_tab()['rows']
    assert rows[8]['cells']['D'] == rows[10]['cells']['D'] == 'Synthetic Binh'
    assert env.adapter.coverage()['writable'] is True  # No diagnostic either.
    assert_locked_across_reconciliation(env, request, 'binh', 1, 'APPLIED_SCHEDULE_CONFLICT')


def test_S8_scope_diagnostic_after_write_blocks_completion(env):
    request, respond = replacement(env, 'chi', 9, 'binh', 'scope')
    env.transport.script = [{'after': lambda t: t.set_cell(10, 'D', 'Unrostered Person')}]
    result = respond()
    assert (result['status'], result['reason']) == ('reconciliation_required', 'APPLIED_VERIFICATION_FAILED')
    assert env.adapter.coverage()['writable'] is False
    assert_locked_across_reconciliation(env, request, 'binh', 1, 'APPLIED_VERIFICATION_FAILED')


def test_S3_transport_binds_identity_inside_write_call(env):
    """A switch after the adapter gate cannot make the fake write a different tab."""
    _, respond = replacement(env, 'chi', 9, 'binh', 'bound')
    env.transport.script = [{'before': lambda t: t.set_provenance({**t.provenance(), 'tab': 'Other tab'})}]
    result = respond()
    assert (result['status'], result['reason']) == ('write_failed', 'WRITE_FAILED')
    assert env.transport.write_log() == []
    assert env.transport.read_tab()['rows'][8]['cells']['D'] == 'Synthetic Chi'


@pytest.mark.parametrize('damage', ['stt', 'missing_anchor', 'duplicate_anchor', 'unknown_header'])
def test_S8_postwrite_coverage_loss_never_completes_and_alerts_once(env, damage):
    request, respond = replacement(env, 'chi', 9, 'binh', 'coverage')

    def change(transport):
        if damage == 'stt':
            transport.set_cell(11, 'A', 'STT')
            transport.set_cell(11, 'D', 'Synthetic Binh')
        elif damage == 'missing_anchor':
            transport.set_anchor(11, None)
        elif damage == 'duplicate_anchor':
            transport.set_anchor(11, 'anc-005')
        else:
            transport.insert_row(9, {'A': f'T3 - {DAY2:%d/%m/%Y}'})

    env.transport.script = [{'after': change}]
    result = respond()
    assert result['status'] == 'reconciliation_required'
    assert env.adapter.coverage()['writable'] is False
    reason = 'WRITE_NOT_VERIFIED' if damage == 'unknown_header' else 'APPLIED_VERIFICATION_FAILED'
    # A lost target blocks even target reads; other coverage failures still allow its D read.
    if damage == 'unknown_header':
        for _ in range(2):
            assert env.service.reconcile_request('ops', request['id'])['status'] == 'reconciliation_required'
        env.service.close()
        env.open()
        env.service.run_maintenance('ops')
        status = env.service.reconcile_request('ops', request['id'])
        assert (status['status'], status['reason'], status['reserved_for']) == (
            'reconciliation_required', reason, 'binh')
        assert len(reconciliation_alerts(env, request)) == 1
        assert len(env.transport.write_log()) == 1
    else:
        assert_locked_across_reconciliation(env, request, 'binh', 1, reason)


@pytest.mark.parametrize('side', ['recipient', 'owner'])
def test_S8_swap_rechecks_both_coaches_after_second_write(env, side):
    request, respond = swap(env, 'two-sided')

    def add_conflict(transport):
        if side == 'recipient':  # Dung receives row 4, day-1 morning.
            transport.set_cell(6, 'G', 'Sáng')
            transport.set_cell(6, 'D', 'Synthetic Dung')
        else:  # An receives row 10, day-2 morning.
            transport.set_cell(11, 'D', 'Synthetic An')

    env.transport.script = [{}, {'after': add_conflict}]
    result = respond()
    assert (result['status'], result['reason']) == ('reconciliation_required', 'APPLIED_SCHEDULE_CONFLICT')
    assert by_row(env)[4]['coach_id'] == 'dung' and by_row(env)[10]['coach_id'] == 'an'
    assert_locked_across_reconciliation(env, request, 'dung', 2, 'APPLIED_SCHEDULE_CONFLICT')


@pytest.mark.parametrize('kind', ['replacement', 'leave'])
def test_S8_locked_cancel_and_withdraw_keep_reservation_and_do_not_rewrite(env, kind):
    if kind == 'replacement':
        request, respond = replacement(env, 'chi', 9, 'binh', 'locked')
    else:
        request = env.service.create_change_request('chi', 'leave', env.ids[9], 'locked-c', sender_confirmed=True)
        env.service.approve_leave_request('ops', request['id'], 'locked-a')
        invite = next(i['invitation_id'] for i in env.service.get_my_invitations('binh')
                      if i['request_id'] == request['id'])
        respond = lambda: env.service.respond_to_invitation('binh', invite, True, True, 'locked-r')
    env.transport.script = [{'after': lambda t: t.set_cell(11, 'D', 'Synthetic Binh')}]
    assert respond()['status'] == 'reconciliation_required'
    if kind == 'replacement':
        result = env.service.cancel_request('chi', request['id'], 'synthetic reason', 'locked-cancel')
    else:
        result = env.service.withdraw_leave_approval('ops', request['id'], 'synthetic reason', 'locked-withdraw')
    assert result['status'] == 'reconciliation_required'
    assert_locked_across_reconciliation(env, request, 'binh', 1, 'APPLIED_SCHEDULE_CONFLICT')


def test_S8_manual_resolution_completes_once_without_another_write(env):
    request, respond = replacement(env, 'chi', 9, 'binh', 'resolve')
    env.transport.script = [{'after': lambda t: t.set_cell(11, 'D', 'Synthetic Binh')}]
    assert respond()['status'] == 'reconciliation_required'
    assert_locked_across_reconciliation(env, request, 'binh', 1, 'APPLIED_SCHEDULE_CONFLICT')
    env.transport.set_cell(11, 'D', None)  # Manual ops repair, not a bot write/rollback.
    assert env.service.reconcile_request('ops', request['id'])['status'] == 'completed'
    for _ in range(2):
        env.service.run_maintenance('ops')
        assert env.service.reconcile_request('ops', request['id'])['status'] == 'completed'
    assert len(env.transport.write_log()) == 1
    for person in ('chi', 'binh', 'ops'):
        notifications = [n for n in env.service.get_my_notifications(person)
                         if n['event'] == 'request_completed' and n['request_id'] == request['id']]
        assert len(notifications) == 1


@pytest.mark.parametrize('copy_of', ['absent', None, '', 'placeholder-source'])
def test_owner_confirmed_copy_accepts_unknown_source_without_inventing_id(env, copy_of):
    provenance = {'kind': 'test_copy', 'spreadsheet_id': 'synthetic-bee-bot',
                  'tab': 'Lịch lab synthetic', 'sheet_id': 0, 'owner_confirmed_copy': True}
    if copy_of != 'absent':
        provenance['copy_of'] = copy_of
    before = dict(provenance)
    env.transport.set_provenance(provenance)
    env.adapter = SheetsScheduleAdapter(env.transport, synthetic_roster(), ALLOWED)
    env.service = BeeBotService(env.db, env.adapter, clock=lambda: NOW)
    env.services.append(env.service)
    assert env.adapter.provenance == before
    _, respond = replacement(env, 'chi', 9, 'binh', 'confirmed-copy')
    assert respond()['status'] == 'completed'
    assert env.transport.write_log() == [{'anchor': 'anc-004', 'column': 'D', 'value': 'Synthetic Binh'}]


@pytest.mark.parametrize('confirmed', [None, False, 'true', 1])
def test_unknown_source_requires_explicit_boolean_owner_confirmation(confirmed):
    with pytest.raises(BeeBotError) as error:
        check_provenance({'kind': 'test_copy', 'spreadsheet_id': 'copy', 'tab': 't',
                          'owner_confirmed_copy': confirmed}, {'copy'})
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'


@pytest.mark.parametrize('damage', [
    {'spreadsheet_id': 'source'}, {'spreadsheet_id': ' source '},
    {'copy_of': 'copy'}, {'copy_of': ' copy '},
])
def test_owner_confirmation_never_overrides_denylist_or_supplied_self_copy(damage):
    provenance = {'kind': 'test_copy', 'spreadsheet_id': 'copy', 'tab': 't',
                  'owner_confirmed_copy': True, **damage}
    with pytest.raises(BeeBotError) as error:
        check_provenance(provenance, {'copy', 'source', ' source '}, {' source '})
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'


@pytest.mark.parametrize('sheet_id', [True, False, -1, 0.0, '0', None])
def test_supplied_numeric_sheet_identity_must_be_nonnegative_integer(sheet_id):
    with pytest.raises(BeeBotError) as error:
        check_provenance({'kind': 'test_copy', 'spreadsheet_id': 'copy', 'tab': 't',
                          'owner_confirmed_copy': True, 'sheet_id': sheet_id}, {'copy'})
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'


@pytest.mark.parametrize('switch', [{'owner_confirmed_copy': False}, {'sheet_id': 1}])
def test_confirmation_and_numeric_sheet_identity_are_pinned_for_writes(env, switch):
    provenance = {'kind': 'test_copy', 'spreadsheet_id': 'synthetic-bee-bot', 'tab': 'Lịch lab synthetic',
                  'copy_of': 'placeholder-source', 'owner_confirmed_copy': True, 'sheet_id': 0}
    env.transport.set_provenance(provenance)
    adapter = SheetsScheduleAdapter(env.transport, synthetic_roster(), ALLOWED)
    original = adapter.get_assignment(env.ids[9])
    env.transport.set_provenance({**provenance, **switch})
    with pytest.raises(BeeBotError) as error:
        adapter.apply_updates({env.ids[9]: 'binh'}, {env.ids[9]: original})
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'
    assert env.transport.write_log() == []


def test_LIMITATION_no_cas_last_read_to_write_ops_edit_is_lost(env):
    """This remains a limitation even though the avoidable between-cell gap is closed."""
    _, respond = replacement(env, 'chi', 9, 'binh', 'no-cas')
    env.transport.script = [{'before': lambda t: t.set_cell(9, 'D', 'Synthetic Dung')}]
    assert respond()['status'] == 'completed'
    assert by_row(env)[9]['coach_id'] == 'binh'  # The intervening ops value was overwritten.
    assert env.adapter.coverage()['compare_and_set'] is False


def test_LIMITATION_aba_returns_identical_content_hash(env):
    before = env.adapter.get_assignment(env.ids[9])
    env.transport.set_cell(9, 'D', 'Synthetic Dung')
    assert env.adapter.get_assignment(env.ids[9])['revision'] != before['revision']
    env.transport.set_cell(9, 'D', 'Synthetic Chi')
    assert env.adapter.get_assignment(env.ids[9]) == before
