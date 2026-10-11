"""Offline Sheets adapter core: synthetic tab only, real BeeBotService on top."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from bee_bot.errors import BeeBotError
from bee_bot.service import BeeBotService
from bee_bot.sheets_adapter import SheetsScheduleAdapter, run_offline_demo
from bee_bot.sheets_copy_transport import (SyntheticSheetTransport, synthetic_roster,
                                           write_synthetic_tab)
from bee_bot.sheets_import import ZONE

NOW = datetime(2026, 10, 10, 8, tzinfo=ZONE)
ALLOWED = {'synthetic-bee-bot'}


@pytest.fixture
def env(tmp_path):
    sheet, db = tmp_path / 'tab.json', tmp_path / 'state.db'
    transport = write_synthetic_tab(sheet, (NOW + timedelta(days=3)).date())
    state = SimpleNamespace(transport=transport, sheet=sheet, db=db, services=[])

    def open_service():
        transport = SyntheticSheetTransport(sheet)  # fresh instance, as after a restart
        adapter = SheetsScheduleAdapter(transport, synthetic_roster(), ALLOWED)
        service = BeeBotService(db, adapter, clock=lambda: NOW)
        state.transport, state.adapter, state.service = transport, adapter, service
        state.services.append(service)
        return service

    state.open = open_service
    open_service()
    state.ids = {a['source_locator']['row']: a['assignment_id'] for a in state.adapter.list_assignments()}
    yield state
    for service in state.services:
        service.close()


def grid(transport, without=('D',)):
    return [(r['anchor'], {c: v for c, v in r['cells'].items() if c not in without})
            for r in transport.read_tab()['rows']]


def replace(env, owner='chi', row=9, recipient='binh', event='e'):
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


def d_of(env, anchor):
    return env.transport.read_tab()['rows'][env.transport.row_of(anchor) - 1]['cells']['D']


# -- parsing, D/J and trusted people ---------------------------------------

def test_parses_canonical_block_with_merges_and_vacant_slot(env):
    by_row = {a['source_locator']['row']: a for a in env.adapter.list_assignments()}
    assert set(by_row) == {4, 5, 6, 9, 10, 11}
    assert by_row[5]['room'] == 'H210' and by_row[5]['class_name'] == 'Track 1 / CS1'
    assert by_row[5]['shift_id'] == by_row[4]['shift_id'] != by_row[4]['assignment_id']
    assert by_row[6]['starts_at'].endswith('T14:00:00+07:00')
    assert by_row[11]['coach_id'] is None
    assert env.adapter.coverage()['writable'] is True


def test_replacement_writes_only_d_and_preserves_j(env):
    before = grid(env.transport)
    _, respond = replace(env)
    assert respond()['status'] == 'completed'
    assert grid(env.transport) == before
    assert d_of(env, 'anc-004') == 'Synthetic Binh'
    assert env.transport.write_log() == [{'anchor': 'anc-004', 'column': 'D', 'value': 'Synthetic Binh'}]


def test_j_edit_before_and_during_write_is_kept_and_does_not_block(env):
    _, respond = replace(env)
    row = env.transport.row_of('anc-004')
    env.transport.set_cell(row, 'J', 'Bận')  # before
    env.transport.script = [{'before': lambda t: t.set_cell(row, 'J', 'Ops J during')}]
    assert respond()['status'] == 'completed'
    assert env.transport.read_tab()['rows'][row - 1]['cells']['J'] == 'Ops J during'


def test_people_come_only_from_explicit_roster(env):
    assert {p['person_id'] for p in env.adapter.list_people()} == {'an', 'binh', 'chi', 'dung', 'ops'}
    assert all('sheet_names' not in p for p in env.adapter.list_people())
    roster = synthetic_roster() + [{'person_id': 'x', 'display_name': 'X', 'role': 'labcoach',
                                    'active': True, 'sheet_names': ['synthetic  AN']}]
    with pytest.raises(BeeBotError) as error:
        SheetsScheduleAdapter(env.transport, roster, ALLOWED)
    assert error.value.code == 'ROSTER_AMBIGUOUS'


@pytest.mark.parametrize('target', ['ops', 'ghost', 'inactive'])
def test_write_rejects_untrusted_targets(env, target):
    roster = synthetic_roster() + [{'person_id': 'inactive', 'display_name': 'I', 'role': 'labcoach',
                                    'active': False, 'sheet_names': ['Synthetic Inactive']}]
    adapter = SheetsScheduleAdapter(env.transport, roster, ALLOWED)
    original = adapter.get_assignment(env.ids[9])
    with pytest.raises(BeeBotError) as error:
        adapter.apply_updates({env.ids[9]: target}, {env.ids[9]: original})
    assert error.value.code == 'INVALID_SUBSTITUTE'
    assert env.transport.write_log() == []


# -- stable IDs and relocation ---------------------------------------------

def test_ids_survive_insert_move_stt_and_other_name_changes(env):
    before = {a['assignment_id']: a for a in env.adapter.list_assignments()}
    env.transport.insert_row(4, {'A': 'Ghi chú ops'})
    env.transport.move_row(env.transport.row_of('anc-005'), env.transport.row_of('anc-006'))  # reorder in block
    assert env.transport.row_of('anc-005') > env.transport.row_of('anc-006')
    env.transport.set_cell(env.transport.row_of('anc-006'), 'A', 99)
    env.transport.set_cell(env.transport.row_of('anc-003'), 'D', 'Synthetic Dung')
    after = {a['assignment_id']: a for a in env.adapter.list_assignments()}
    assert set(after) == set(before)
    changed = {i for i in before if before[i]['revision'] != after[i]['revision']}
    assert changed == {env.ids[6]}  # only the row whose D changed


def test_moved_row_keeps_date_block_scope_or_fails_closed(env):
    # Moving a row out of its day block changes its canonical date: the row is
    # read in its new context, never with its old coordinate's data.
    env.transport.move_row(env.transport.row_of('anc-005'), 2)
    assert env.adapter.coverage()['diagnostics'] == [{'code': 'INVALID_CANONICAL_ROW', 'row': 2}]
    assert env.ids[10] not in {a['assignment_id'] for a in env.adapter.list_assignments()}


def test_write_after_row_insertion_relocates_by_anchor(env):
    _, respond = replace(env)
    env.transport.script = [{'before': lambda t: t.insert_row(4, {'A': 'Ops inserted note'})}]
    assert respond()['status'] == 'completed'
    assert env.transport.row_of('anc-004') == 10  # moved down by the insertion
    assert d_of(env, 'anc-004') == 'Synthetic Binh'
    # The row now sitting at the old coordinate (9) is untouched.
    assert env.transport.read_tab()['rows'][8]['cells']['D'] == 'Lab Coach'  # header row, not overwritten
    assert [d_of(env, a) for a in ('anc-001', 'anc-002', 'anc-003', 'anc-005')] == [
        'Synthetic An', 'Synthetic Chi', 'Synthetic Binh', 'Synthetic Dung']


# -- fail-closed writable coverage -----------------------------------------

@pytest.mark.parametrize('damage, code', [
    (lambda t: t.set_anchor(t.row_of('anc-006'), None), 'MISSING_ANCHOR'),
    (lambda t: t.set_anchor(t.row_of('anc-006'), 'anc-005'), 'DUPLICATE_ANCHOR'),
    (lambda t: t.set_cell(t.row_of('anc-006'), 'F', None), 'INVALID_CANONICAL_ROW'),
    (lambda t: t.set_cell(t.row_of('anc-006'), 'D', 'Unrostered Person'), 'UNKNOWN_ROSTER_NAME'),
    (lambda t: t.set_cell(7, 'A', 'Thứ 3 - 32/13/2026'), 'INVALID_DATE_HEADER'),
])
def test_incomplete_scope_surfaces_diagnostics_and_blocks_all_writes(env, damage, code):
    original = env.adapter.get_assignment(env.ids[4])
    damage(env.transport)
    coverage = env.adapter.coverage()
    assert coverage['writable'] is False and code in {d['code'] for d in coverage['diagnostics']}
    assert all(set(d) == {'code', 'row'} for d in coverage['diagnostics'])  # no names
    with pytest.raises(BeeBotError) as error:
        env.adapter.apply_updates({env.ids[4]: 'binh'}, {env.ids[4]: original})
    assert error.value.code == 'SCHEDULE_SCOPE_INCOMPLETE'
    assert env.transport.write_log() == []


def test_service_records_write_failed_when_scope_incomplete(env):
    _, respond = replace(env)
    env.transport.set_cell(env.transport.row_of('anc-006'), 'D', 'Unrostered Person')
    result = respond()
    assert (result['status'], result['reason']) == ('write_failed', 'SCHEDULE_SCOPE_INCOMPLETE')
    assert env.transport.write_log() == []


# -- concurrent ops edits --------------------------------------------------

def test_ops_d_edit_before_write_stops_service(env):
    _, respond = replace(env)
    env.transport.set_cell(env.transport.row_of('anc-004'), 'D', 'Synthetic Dung')
    assert respond()['status'] == 'needs_ops'
    assert d_of(env, 'anc-004') == 'Synthetic Dung' and env.transport.write_log() == []


def test_adapter_fresh_read_rejects_stale_expected(env):
    original = env.adapter.get_assignment(env.ids[9])
    env.transport.set_cell(env.transport.row_of('anc-004'), 'F', 'H999')
    with pytest.raises(BeeBotError) as error:
        env.adapter.apply_updates({env.ids[9]: 'binh'}, {env.ids[9]: original})
    assert error.value.code == 'SCHEDULE_CHANGED' and env.transport.write_log() == []


def test_adapter_rechecks_recipient_overlap_on_fresh_read(env):
    original = env.adapter.get_assignment(env.ids[9])
    env.transport.set_cell(env.transport.row_of('anc-006'), 'D', 'Synthetic Binh')  # same day/morning
    with pytest.raises(BeeBotError) as error:
        env.adapter.apply_updates({env.ids[9]: 'binh'}, {env.ids[9]: original})
    assert error.value.code == 'SCHEDULE_CONFLICT' and env.transport.write_log() == []


def test_LIMITATION_no_compare_and_set_lost_update_between_read_and_write(env):
    """Not a safety success: Sheets offers no CAS, so this ops edit is silently lost."""
    _, respond = replace(env)
    row = env.transport.row_of('anc-004')
    env.transport.script = [{'before': lambda t: t.set_cell(row, 'D', 'Synthetic Dung')}]
    assert respond()['status'] == 'completed'
    assert d_of(env, 'anc-004') == 'Synthetic Binh'  # ops' 'Synthetic Dung' overwritten undetected
    assert env.adapter.coverage()['compare_and_set'] is False


def test_LIMITATION_revision_is_content_hash_aba_invisible(env):
    original = env.adapter.get_assignment(env.ids[9])
    row = env.transport.row_of('anc-004')
    env.transport.set_cell(row, 'D', 'Synthetic Dung')
    env.transport.set_cell(row, 'D', 'Synthetic Chi')  # A -> B -> A
    assert env.adapter.get_assignment(env.ids[9]) == original


def test_ops_d_edit_after_write_is_uncertain_and_never_rewritten(env):
    request, respond = replace(env)
    row = env.transport.row_of('anc-004')
    env.transport.script = [{'after': lambda t: t.set_cell(row, 'D', 'Synthetic Dung')}]
    result = respond()
    assert (result['status'], result['reserved_for']) == ('reconciliation_required', 'binh')
    env.service.run_maintenance('ops')
    env.service.reconcile_request('ops', request['id'])
    assert len(env.transport.write_log()) == 1 and d_of(env, 'anc-004') == 'Synthetic Dung'


# -- faults, partial swap, provenance, restart -----------------------------

@pytest.mark.parametrize('fault, landed, status', [
    ('timeout_before', False, 'reconciliation_required'),
    ('timeout_after', True, 'completed'),
    ('reject', False, 'write_failed'),
])
def test_single_write_faults(env, fault, landed, status):
    _, respond = replace(env)
    env.transport.script = [{'fault': fault}]
    result = respond()
    assert result['status'] == status and result['reserved_for'] == 'binh'
    assert len(env.transport.write_log()) == int(landed)
    assert d_of(env, 'anc-004') == ('Synthetic Binh' if landed else 'Synthetic Chi')


def test_swap_completes_and_preserves_j(env):
    before = grid(env.transport)
    _, respond = swap(env)
    assert respond()['status'] == 'completed'
    assert (d_of(env, 'anc-001'), d_of(env, 'anc-005')) == ('Synthetic Dung', 'Synthetic An')
    assert grid(env.transport) == before


@pytest.mark.parametrize('second', [{'fault': 'timeout_before'}, {'fault': 'reject'}])
def test_partial_swap_keeps_reservation_across_restart_then_reconciles(env, second):
    request, respond = swap(env)
    env.transport.script = [{}, second]
    result = respond()
    assert (result['status'], result['reserved_for']) == ('reconciliation_required', 'dung')
    env.service.close()
    service = env.open()  # restart: new adapter/transport/service objects on same files
    for _ in range(2):
        service.run_maintenance('ops')
        service.reconcile_request('ops', request['id'])
    assert service.get_request_status('ops', request['id'])['status'] == 'reconciliation_required'
    assert len(env.transport.write_log()) == 1  # never re-written, never rolled back
    assert (d_of(env, 'anc-001'), d_of(env, 'anc-005')) == ('Synthetic Dung', 'Synthetic Dung')
    env.transport.set_cell(env.transport.row_of('anc-005'), 'D', 'Synthetic An')  # ops fixes by hand
    assert service.reconcile_request('ops', request['id'])['status'] == 'completed'
    assert len(env.transport.write_log()) == 1


def test_provenance_change_mid_swap_blocks_second_write(env):
    request, respond = swap(env)
    flip = lambda t: t.set_provenance({**t.provenance(), 'kind': 'production'})
    env.transport.script = [{'after': flip}]
    assert respond()['status'] == 'reconciliation_required'
    assert len(env.transport.write_log()) == 1
    assert d_of(env, 'anc-005') == 'Synthetic Dung'


@pytest.mark.parametrize('provenance', [
    {},
    {'kind': 'production', 'spreadsheet_id': 'synthetic-bee-bot', 'tab': 't'},
    {'kind': 'synthetic', 'spreadsheet_id': 'synthetic-bee-bot', 'tab': 't'},  # real-data flag missing
    {'kind': 'synthetic', 'spreadsheet_id': 'other', 'tab': 't', 'contains_real_data': False},
    {'kind': 'test_copy', 'spreadsheet_id': 'synthetic-bee-bot', 'tab': 't', 'copy_of': 'synthetic-bee-bot'},
    {'kind': 'test_copy', 'spreadsheet_id': 'synthetic-bee-bot', 'tab': 't', 'copy_of': None},
])
def test_provenance_rejected_fails_closed(env, provenance):
    env.transport.set_provenance(provenance)
    with pytest.raises(BeeBotError) as error:
        SheetsScheduleAdapter(env.transport, synthetic_roster(), ALLOWED)
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'


def test_denied_source_id_wins_over_allowlist_even_as_test_copy(env):
    source = 'placeholder-source-id'  # synthetic placeholder; no real ID in Git
    env.transport.set_provenance({'kind': 'test_copy', 'spreadsheet_id': source, 'tab': 't',
                                  'copy_of': 'placeholder-original'})
    assert SheetsScheduleAdapter(env.transport, synthetic_roster(), {source}).provenance['spreadsheet_id'] == source
    with pytest.raises(BeeBotError) as error:
        SheetsScheduleAdapter(env.transport, synthetic_roster(), {source}, denied_source_ids={source})
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'


def test_denied_source_set_at_write_time_blocks_write(env):
    adapter = SheetsScheduleAdapter(env.transport, synthetic_roster(), ALLOWED,
                                    denied_source_ids={'placeholder-source-id'})
    original = adapter.get_assignment(env.ids[9])
    env.transport.set_provenance({**env.transport.provenance(), 'spreadsheet_id': 'placeholder-source-id'})
    with pytest.raises(BeeBotError) as error:
        adapter.apply_updates({env.ids[9]: 'binh'}, {env.ids[9]: original})
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED' and env.transport.write_log() == []


@pytest.mark.parametrize('name', ['schedule.xlsx', '.bee-bot/source/tab.json'])
def test_transport_refuses_source_exports_as_backing_file(tmp_path, name):
    with pytest.raises(BeeBotError) as error:
        SyntheticSheetTransport(tmp_path / name)
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'


def test_offline_end_to_end_demo(tmp_path):
    result = run_offline_demo(tmp_path / 'demo')
    assert result['replacement_status'] == 'completed'
    assert result['swap_status_after_partial'] == 'reconciliation_required'
    assert result['swap_status_after_restart_maintenance'] == 'reconciliation_required'
    assert result['bot_writes_after_restart'] == result['bot_writes_final'] == 2
    assert result['swap_status_after_ops_fix'] == 'completed'
    assert result['j_column'] == ['Rảnh', 'Chưa cập nhật', 'Bận', 'Rảnh', 'Rảnh', None]


# -- QA-SHEETS repair regressions (S1-S7) ------------------------------------

def codes(env):
    return {d['code'] for d in env.adapter.coverage()['diagnostics']}


@pytest.mark.parametrize('a_value', [None, 'x', '', 'ghi chú', 'STT'])
def test_S1_populated_row_without_stt_blocks_scope_and_service_write(env, a_value):
    env.transport.set_cell(11, 'A', a_value)
    env.transport.set_cell(11, 'D', 'Synthetic Binh')
    assert 'UNCLASSIFIED_ROW' in codes(env) and env.adapter.coverage()['writable'] is False
    _, respond = replace(env)  # chi day-2 Sáng (row 9) -> binh, who is hidden on row 11
    result = respond()
    assert (result['status'], result['reason']) == ('write_failed', 'SCHEDULE_SCOPE_INCOMPLETE')
    assert env.transport.write_log() == []


@pytest.mark.parametrize('stt', ['3', ' 3 ', '3.0', 3.0])
def test_S1_integer_valued_stt_strings_are_data_rows(env, stt):
    env.transport.set_cell(11, 'A', stt)
    env.transport.set_cell(11, 'D', 'Synthetic Binh')
    assert {a['source_locator']['row'] for a in env.adapter.list_assignments()} >= {11}
    _, respond = replace(env)
    result = respond()
    assert (result['status'], result.get('reason')) == ('needs_ops', 'SCHEDULE_CONFLICT')
    assert env.transport.write_log() == []


def test_S1_note_rows_title_and_column_headers_stay_allowed(env):
    env.transport.insert_row(1, {'A': 'Lịch Lab Coach K4 02/10–16/10/2026'})  # preamble with dates
    env.transport.insert_row(5, {'A': 'Ghi chú: phòng đổi tạm'})  # A-only note inside block
    assert env.adapter.coverage()['writable'] is True and len(env.adapter.list_assignments()) == 6


@pytest.mark.parametrize('header', ['T3 - {d:%d/%m/%Y}', '{d:%d/%m/%Y} (Thứ 3)', 'Thu 3 - {d:%d/%m/%Y}',
                                    'Thứ 3', '{d:%d-%m}', 'CN {d:%d/%m}'])
def test_S2_unrecognised_day_header_blocks_and_never_inherits_previous_day(env, header):
    day2 = (NOW + timedelta(days=4)).date()
    env.transport.set_cell(7, 'A', header.format(d=day2))
    assert {'INVALID_DATE_HEADER', 'INVALID_CANONICAL_ROW'} <= codes(env)
    assert {a['source_locator']['row'] for a in env.adapter.list_assignments()} == {4, 5, 6}


def test_S2_date_header_row_with_populated_cells_blocks(env):
    env.transport.set_cell(7, 'D', 'Synthetic Binh')
    assert 'INVALID_DATE_HEADER' in codes(env)


@pytest.mark.parametrize('switch', [{'spreadsheet_id': 'synthetic-other'}, {'tab': 'Other tab'}])
def test_S3_identity_pinned_mid_swap_blocks_second_write(env, switch):
    adapter = SheetsScheduleAdapter(env.transport, synthetic_roster(), ALLOWED | {'synthetic-other'})
    service = BeeBotService(env.db, adapter, clock=lambda: NOW)
    env.services.append(service)
    env.service, env.adapter = service, adapter
    _, respond = swap(env)
    env.transport.script = [{'after': lambda t: t.set_provenance({**t.provenance(), **switch})}, {}]
    assert respond()['status'] == 'reconciliation_required'
    assert len(env.transport.write_log()) == 1
    with pytest.raises(BeeBotError) as error:
        adapter.list_assignments()
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'


def test_S3_transport_write_is_bound_to_workbook_and_tab(env):
    """A switch inside the write call (after the adapter's last check) is refused by the binding."""
    _, respond = replace(env)
    env.transport.script = [{'before': lambda t: t.set_provenance({**t.provenance(), 'tab': 'Other tab'})}]
    result = respond()
    assert (result['status'], result['reason']) == ('write_failed', 'WRITE_FAILED')
    assert env.transport.write_log() == []


def test_S4_overlap_created_in_write_window_fails_adapter_readback(env):
    original = env.adapter.get_assignment(env.ids[9])
    env.transport.script = [{'before': lambda t: t.set_cell(11, 'D', 'Synthetic Binh')}]
    with pytest.raises(BeeBotError) as error:
        env.adapter.apply_updates({env.ids[9]: 'binh'}, {env.ids[9]: original})
    assert error.value.code == 'WRITE_UNCERTAIN' and len(env.transport.write_log()) == 1
    assert env.adapter.verify_applied({env.ids[9]: 'binh'}, {env.ids[9]: original}) is False


@pytest.mark.parametrize('column, value', [('F', 'H999'), ('G', 'Chiều')])
def test_S4_readback_validates_confirmed_details(env, column, value):
    original = env.adapter.get_assignment(env.ids[9])
    env.transport.script = [{'after': lambda t: t.set_cell(9, column, value)}]
    with pytest.raises(BeeBotError) as error:
        env.adapter.apply_updates({env.ids[9]: 'binh'}, {env.ids[9]: original})
    assert error.value.code == 'WRITE_UNCERTAIN'


def test_S8_service_reconcile_refuses_applied_overlap_across_restart(env):
    request, respond = replace(env)
    env.transport.script = [{'before': lambda t: t.set_cell(11, 'D', 'Synthetic Binh')}]
    result = respond()
    assert (result['status'], result['reason']) == ('reconciliation_required', 'APPLIED_SCHEDULE_CONFLICT')
    env.service.close()
    service = env.open()
    for _ in range(2):
        service.run_maintenance('ops')
        service.reconcile_request('ops', request['id'])
    status = service.get_request_status('ops', request['id'])
    assert (status['status'], status['reserved_for']) == ('reconciliation_required', 'binh')
    assert len(env.transport.write_log()) == 1
    env.transport.set_cell(11, 'D', None)  # ops resolves the double booking
    assert service.reconcile_request('ops', request['id'])['status'] == 'completed'
    assert len(env.transport.write_log()) == 1


def test_S8_adapter_verification_failure_blocks_completion(env):
    """Scope broken after the write: targets match, but verify_applied fails -> not completed."""
    request, respond = replace(env)
    env.transport.script = [{'after': lambda t: t.set_cell(10, 'D', 'Unrostered Person')}]
    result = respond()
    assert (result['status'], result['reason']) == ('reconciliation_required', 'APPLIED_VERIFICATION_FAILED')
    env.transport.set_cell(10, 'D', 'Synthetic Dung')
    assert env.service.reconcile_request('ops', request['id'])['status'] == 'completed'
    assert len(env.transport.write_log()) == 1


@pytest.mark.parametrize('damage', [
    lambda t: t.set_cell(11, 'A', 'unrecognised'),
    lambda t: (t.set_cell(11, 'A', 'STT'), t.set_cell(11, 'D', 'Synthetic Binh')),
    lambda t: t.set_anchor(10, None),
    lambda t: t.set_anchor(10, 'anc-006'),
    lambda t: t.set_cell(10, 'D', 'Unrostered Person'),
])
def test_S8_coverage_loss_keeps_reservation_and_one_alert_after_restart(env, damage):
    request, respond = replace(env)
    env.transport.script = [{'after': damage}]
    result = respond()
    assert (result['status'], result['reason'], result['reserved_for']) == (
        'reconciliation_required', 'APPLIED_VERIFICATION_FAILED', 'binh')
    env.service.close()
    service = env.open()
    for _ in range(2):
        service.run_maintenance('ops')
        service.reconcile_request('ops', request['id'])
    assert service.get_request_status('ops', request['id'])['status'] == 'reconciliation_required'
    assert len(env.transport.write_log()) == 1
    alerts = [n for n in service.get_my_notifications('ops')
              if n['event'] == 'reconciliation_required' and n['request_id'] == request['id']]
    assert len(alerts) == 1


@pytest.mark.parametrize('column, value', [('F', 'H999'), ('G', 'Chiều')])
def test_S8_confirmed_detail_drift_stays_locked_through_restart(env, column, value):
    request, respond = replace(env)
    env.transport.script = [{'after': lambda t: t.set_cell(9, column, value)}]
    assert respond()['status'] == 'reconciliation_required'
    env.service.close()
    service = env.open()
    service.run_maintenance('ops')
    status = service.reconcile_request('ops', request['id'])
    assert (status['status'], status['reason'], status['reserved_for']) == (
        'reconciliation_required', 'WRITE_NOT_VERIFIED', 'binh')
    assert len(env.transport.write_log()) == 1
    assert env.transport.read_tab()['rows'][8]['cells'][column] == value


def test_S8_pinned_tab_switch_after_write_never_completes_or_rewrites(env):
    request, respond = replace(env)
    env.transport.script = [{'after': lambda t: t.set_provenance({**t.provenance(), 'tab': 'Other tab'})}]
    assert respond()['status'] == 'reconciliation_required'
    env.service.run_maintenance('ops')
    assert env.service.reconcile_request('ops', request['id'])['status'] == 'reconciliation_required'
    env.service.close()
    service = env.open()
    service.run_maintenance('ops')
    status = service.reconcile_request('ops', request['id'])
    assert (status['status'], status['reserved_for']) == ('reconciliation_required', 'binh')
    assert len(env.transport.write_log()) == 1


def test_S1_header_with_a_roster_name_is_not_a_column_header(env):
    env.transport.set_cell(8, 'D', 'Synthetic Binh')
    assert 'UNCLASSIFIED_ROW' in codes(env)
    assert env.adapter.coverage()['writable'] is False


def test_S5_second_swap_target_reread_before_its_write(env):
    request, respond = swap(env)
    env.transport.script = [{'after': lambda t: t.set_cell(t.row_of('anc-005'), 'D', 'Synthetic Chi')}, {}]
    assert respond()['status'] == 'reconciliation_required'
    assert env.transport.write_log() == [{'anchor': 'anc-001', 'column': 'D', 'value': 'Synthetic Dung'}]
    assert d_of(env, 'anc-005') == 'Synthetic Chi'  # ops edit preserved; first write not rolled back
    assert d_of(env, 'anc-001') == 'Synthetic Dung'


def test_S5_scope_break_between_swap_writes_is_uncertain_not_rolled_back(env):
    _, respond = swap(env)
    env.transport.script = [{'after': lambda t: t.set_cell(11, 'D', 'Unrostered Person')}, {}]
    assert respond()['status'] == 'reconciliation_required'
    assert len(env.transport.write_log()) == 1


def _raw(env, mutate):
    import json
    data = json.loads(env.sheet.read_text(encoding='utf-8'))
    mutate(data)
    env.sheet.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


@pytest.mark.parametrize('mutate', [
    lambda d: d['merges'].append({'start': 9, 'end': 10}),
    lambda d: d['merges'].append({'start': 10, 'end': 9, 'columns': ['B']}),
    lambda d: d['merges'].append({'start': 9, 'end': 99, 'columns': ['B']}),
    lambda d: d['merges'].append({'start': '9', 'end': 10, 'columns': ['B']}),
    lambda d: d['merges'].append({'start': 9, 'end': 10, 'columns': ['Z']}),
    lambda d: d['rows'].append('not a row'),
    lambda d: d['rows'].append({'anchor': 5, 'cells': {}}),
    lambda d: d['rows'].append({'anchor': 'anc-x', 'cells': 'A'}),
])
def test_S6_malformed_merge_or_row_is_controlled_error_and_no_write(env, mutate):
    _, respond = replace(env)
    _raw(env, mutate)
    with pytest.raises(BeeBotError) as error:
        env.adapter.coverage()
    assert error.value.code == 'SCHEDULE_MALFORMED'
    with pytest.raises(BeeBotError) as error:
        respond()  # service's own pre-write read fails closed
    assert error.value.code == 'SCHEDULE_MALFORMED'
    assert env.transport.write_log() == []


def test_S6_merge_over_d_or_stt_blocks(env):
    _raw(env, lambda d: d['merges'].append({'start': 9, 'end': 10, 'columns': ['D']}))
    assert 'MERGED_KEY_CELL' in codes(env) and env.adapter.coverage()['writable'] is False


def test_S7_identifiers_are_normalised_and_denylist_still_wins(env):
    from bee_bot.sheets_adapter import check_provenance
    variant = {'kind': 'test_copy', 'spreadsheet_id': 'placeholder-src ', 'tab': 't', 'copy_of': 'placeholder-x'}
    with pytest.raises(BeeBotError):
        check_provenance(variant, {'placeholder-src '}, {'placeholder-src'})
    exact = {**variant, 'spreadsheet_id': 'placeholder-src'}
    with pytest.raises(BeeBotError):
        check_provenance(exact, {' placeholder-src'}, {'placeholder-src  '})
    assert check_provenance({**exact, 'spreadsheet_id': 'placeholder-copy'}, {' placeholder-copy '}, {'placeholder-src'})


@pytest.mark.parametrize('source', ['absent', None, '', 'placeholder-original'])
def test_owner_confirmed_copy_does_not_require_or_invent_source_id(env, source):
    provenance = {'kind': 'test_copy', 'spreadsheet_id': 'synthetic-bee-bot',
                  'tab': 'Lịch lab synthetic', 'owner_confirmed_copy': True, 'sheet_id': 0}
    if source != 'absent':
        provenance['copy_of'] = source
    env.transport.set_provenance(provenance)
    adapter = SheetsScheduleAdapter(env.transport, synthetic_roster(), ALLOWED)
    assert adapter.provenance == provenance  # unknown source stays unknown
    env.adapter = adapter
    env.service = BeeBotService(env.db, adapter, clock=lambda: NOW)
    env.services.append(env.service)
    _, respond = replace(env)
    assert respond()['status'] == 'completed'
    assert len(env.transport.write_log()) == 1


@pytest.mark.parametrize('confirmed', [False, None, 1, 'true'])
def test_owner_confirmation_is_explicit_boolean(confirmed):
    from bee_bot.sheets_adapter import check_provenance
    provenance = {'kind': 'test_copy', 'spreadsheet_id': 'placeholder-copy',
                  'tab': 'Synthetic', 'owner_confirmed_copy': confirmed}
    with pytest.raises(BeeBotError) as error:
        check_provenance(provenance, {'placeholder-copy'})
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'


@pytest.mark.parametrize('damage', [
    {'spreadsheet_id': 'placeholder-denied'},
    {'copy_of': 'placeholder-copy'},
    {'copy_of': ' placeholder-copy '},
])
def test_owner_confirmation_never_overrides_source_denylist_or_self_copy(damage):
    from bee_bot.sheets_adapter import check_provenance
    provenance = {'kind': 'test_copy', 'spreadsheet_id': 'placeholder-copy',
                  'tab': 'Synthetic', 'owner_confirmed_copy': True, **damage}
    with pytest.raises(BeeBotError) as error:
        check_provenance(provenance, {'placeholder-copy', 'placeholder-denied'}, {' placeholder-denied '})
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'


@pytest.mark.parametrize('sheet_id', [False, True, '0', -1, None, 0.0])
def test_numeric_sheet_identity_rejects_invalid_values(sheet_id):
    from bee_bot.sheets_adapter import check_provenance
    provenance = {'kind': 'test_copy', 'spreadsheet_id': 'placeholder-copy',
                  'tab': 'Synthetic', 'owner_confirmed_copy': True, 'sheet_id': sheet_id}
    with pytest.raises(BeeBotError):
        check_provenance(provenance, {'placeholder-copy'})


@pytest.mark.parametrize('switch', [{'owner_confirmed_copy': False}, {'sheet_id': 1}])
def test_copy_confirmation_and_numeric_sheet_identity_are_pinned(env, switch):
    env.transport.set_provenance({**env.transport.provenance(), 'kind': 'test_copy',
                                  'copy_of': 'placeholder-original', 'owner_confirmed_copy': True, 'sheet_id': 0})
    adapter = SheetsScheduleAdapter(env.transport, synthetic_roster(), ALLOWED)
    original = adapter.get_assignment(env.ids[9])
    env.transport.set_cell(9, 'D', 'Synthetic Binh')
    assert adapter.verify_applied({env.ids[9]: 'binh'}, {env.ids[9]: original}) is True
    env.transport.set_provenance({**env.transport.provenance(), **switch})
    assert adapter.verify_applied({env.ids[9]: 'binh'}, {env.ids[9]: original}) is False
    with pytest.raises(BeeBotError) as error:
        adapter.apply_updates({env.ids[9]: 'binh'}, {env.ids[9]: original})
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'
    assert env.transport.write_log() == []
