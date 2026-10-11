"""Network-free proof of the Google transport boundary, including real adapter use."""
from copy import deepcopy
import base64
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import socket
from types import SimpleNamespace
import traceback
from urllib.parse import unquote
from urllib.parse import parse_qs

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import pytest

from bee_bot.errors import BeeBotError
from bee_bot.google_sheets_transport import (
    API_ROOT, REPO_ROOT, GoogleSheetsTransport, SHEETS_SCOPE, row_fingerprint, structure_fingerprint,
)
from bee_bot.sheets_adapter import SheetsScheduleAdapter
from bee_bot.sheets_copy_transport import COLUMNS, TransportRejected, TransportTimeout, synthetic_roster


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Tests must use mocks, not network sockets')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)


class Credentials:
    scopes = [SHEETS_SCOPE]
    granted_scopes = None
    token = 'synthetic-secret-token'

    def __init__(self, valid=True):
        self.valid = valid
        self.refreshes = 0
        self.fail_refresh = False
        self.events = []

    def has_scopes(self, scopes):
        return set(scopes) <= set(self.scopes)

    def refresh(self, request):
        self.refreshes += 1
        self.events.append('refresh')
        if self.fail_refresh:
            raise RuntimeError('synthetic-secret-token private-copy Secret Name https://private.example/')
        self.valid = True
        self.token = 'synthetic-refreshed-token'


def cell(value):
    if value is None:
        return {}
    kind = 'boolValue' if isinstance(value, bool) else 'numberValue' if isinstance(value, (int, float)) else 'stringValue'
    return {'userEnteredValue': {kind: value}, 'effectiveValue': {kind: value}}


def fixture_payload(tab="Synthetic O'Brien", gid=42, sid='private-copy'):
    raw = [
        ['LỊCH LAB COACH — SYNTHETIC'],
        ['Thứ 2 - 12/10/2026'],
        ['STT', 'Khóa', 'Session', 'Lab Coach', 'Key Coach', 'Phòng', 'Buổi', 'Sức chứa', 'Ghi chú', 'Trạng thái'],
        [1, 'Track 1', 'CS1', 'Synthetic An', 'Key', 'H210', 'Sáng', 30, True, 'Unchanged J'],
        [2, None, None, 'Synthetic Chi', None, None, None, None, None, 'Second J'],
        [3, 'Track 2', 'CS2', 'Synthetic Binh', 'Key', 'H205', 'Chiều', 25, None, 'Third J'],
        [], [],
    ]
    metadata = [{'metadataId': 101 + i, 'metadataKey': 'approved-id', 'metadataValue': anchor,
                 'visibility': 'DOCUMENT', 'location': {'dimensionRange': {
                     'sheetId': gid, 'dimension': 'ROWS', 'startIndex': 3 + i, 'endIndex': 4 + i}}}
                for i, anchor in enumerate(['opaque-a', 'opaque-b', 'opaque-c'])]
    merges = [{'sheetId': gid, 'startRowIndex': 3, 'endRowIndex': 5,
               'startColumnIndex': col, 'endColumnIndex': col + 1} for col in (1, 2, 4, 5, 6, 7)]
    return {'spreadsheetId': sid, 'developerMetadata': metadata,
            'sheets': [{'properties': {'sheetId': gid, 'title': tab,
                                      'gridProperties': {'rowCount': len(raw), 'columnCount': 15}},
                        'merges': merges, 'data': [{'rowData': [{'values': [cell(v) for v in row]} for row in raw]}]}]}


@pytest.fixture
def api():
    state = SimpleNamespace(payload=fixture_payload(), requests=[], fault=None, after_get=None, receipt=None)
    config = {'spreadsheet_id': 'private-copy', 'tab': "Synthetic O'Brien", 'sheet_id': 42,
              'owner_confirmed_copy': True, 'allowed_spreadsheet_ids': ['private-copy'],
              'denied_source_ids': ['protected-source'], 'expected_anchor_count': 3,
              'anchor_mode': 'metadata', 'metadata_key': 'approved-id',
              'write_enabled': True, 'allowed_write_anchors': ['opaque-a', 'opaque-b', 'opaque-c'],
              'max_rows': 50, 'timeout_seconds': 2}
    creds = Credentials()

    def handler(request):
        state.requests.append(request)
        creds.events.append(request.method)
        assert request.url.host == 'sheets.googleapis.com'
        assert request.headers['Authorization'] == 'Bearer ' + creds.token
        if request.method == 'GET':
            if state.fault and state.fault[0] == 'GET':
                fault = state.fault[1]
                if isinstance(fault, Exception):
                    raise fault
                return httpx.Response(fault, json={'error': 'synthetic-secret-token Secret Name private-copy'})
            result = deepcopy(state.payload)
            if state.after_get:
                state.after_get()
            return httpx.Response(200, json=result)
        assert request.method == 'PUT'
        body = json.loads(request.content)
        target = unquote(request.url.path).split('/values/')[1]
        assert target == body['range']
        assert target.startswith("'Synthetic O''Brien'!D")
        assert dict(request.url.params) == {'valueInputOption': 'RAW'}
        assert body['majorDimension'] == 'ROWS' and len(body['values']) == len(body['values'][0]) == 1
        row = int(target.rsplit('D', 1)[1])
        if state.fault and state.fault[0] == 'PUT':
            fault = state.fault[1]
            if fault == 'apply_then_timeout':
                state.payload['sheets'][0]['data'][0]['rowData'][row - 1]['values'][3] = cell(body['values'][0][0])
                raise httpx.ReadTimeout('synthetic-secret-token private-copy Secret Name', request=request)
            if isinstance(fault, Exception):
                raise fault
            return httpx.Response(fault, json={'error': 'synthetic-secret-token private-copy Secret Name'})
        state.payload['sheets'][0]['data'][0]['rowData'][row - 1]['values'][3] = cell(body['values'][0][0])
        receipt = state.receipt if state.receipt is not None else {
            'spreadsheetId': 'private-copy', 'updatedRange': target,
            'updatedRows': 1, 'updatedColumns': 1, 'updatedCells': 1}
        return httpx.Response(200, json=receipt)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    state.config, state.creds, state.client = config, creds, client
    state.transport = GoogleSheetsTransport(config, credentials=creds, http_client=client)
    yield state
    client.close()


def values(api, row):
    return api.payload['sheets'][0]['data'][0]['rowData'][row - 1]['values']


def assert_code(code, operation):
    with pytest.raises(BeeBotError) as caught:
        operation()
    assert caught.value.code == code
    return caught.value


def test_read_pinned_grid_preserves_types_blanks_merges_and_existing_anchors(api):
    tab = api.transport.read_tab()
    assert len(api.requests) == 1 and api.requests[0].method == 'GET'
    assert api.requests[0].url.path == '/v4/spreadsheets/private-copy'
    params = dict(api.requests[0].url.params)
    assert params['ranges'] == "'Synthetic O''Brien'!A1:J51"
    assert 'effectiveValue' in params['fields'] and 'userEnteredValue' in params['fields']
    assert 'developerMetadata' in params['fields'] and 'merges' in params['fields']
    assert [r['row'] for r in tab['rows']] == list(range(1, 9))
    assert [r['anchor'] for r in tab['rows']] == [None, None, None, 'opaque-a', 'opaque-b', 'opaque-c', None, None]
    assert tab['rows'][3]['cells']['A'] == 1 and type(tab['rows'][3]['cells']['A']) is int
    assert tab['rows'][3]['cells']['I'] is True
    assert tab['rows'][4]['cells']['B'] is None  # Adapter, not transport, fills merges.
    assert tab['rows'][6]['cells'] == dict.fromkeys(COLUMNS)
    assert tab['merges'] == [{'start': 4, 'end': 5, 'columns': [c]} for c in ('B', 'C', 'E', 'F', 'G', 'H')]
    assert set(tab) == {'rows', 'merges'}


def test_real_adapter_mapping_and_d_only_raw_write_preserve_entire_rest_of_workbook(api):
    adapter = SheetsScheduleAdapter(api.transport, synthetic_roster(), ['private-copy'], ['protected-source'])
    coverage = adapter.coverage()
    assert coverage['writable'] and coverage['assignments'] == 3
    assignments = {a['source_locator']['row']: a for a in adapter.list_assignments()}
    assert assignments[5]['class_name'] == assignments[4]['class_name'] == 'Track 1 / CS1'
    assert assignments[4]['starts_at'] == '2026-10-12T09:00:00+07:00'
    assert assignments[6]['starts_at'] == '2026-10-12T14:00:00+07:00'
    before = deepcopy(api.payload)
    aid = assignments[4]['assignment_id']
    adapter.apply_updates({aid: 'binh'}, {aid: assignments[4]})
    before['sheets'][0]['data'][0]['rowData'][3]['values'][3] = cell('Synthetic Binh')
    assert api.payload == before
    writes = [r for r in api.requests if r.method == 'PUT']
    assert len(writes) == 1
    assert json.loads(writes[0].content) == {'range': "'Synthetic O''Brien'!D4", 'majorDimension': 'ROWS',
                                           'values': [['Synthetic Binh']]}
    assert adapter.get_assignment(aid)['coach_id'] == 'binh'


def test_literal_formula_like_value_is_raw_not_evaluated_and_j_unchanged(api):
    before_j = deepcopy(values(api, 4)[9])
    api.transport.write_d('opaque-a', '=SYNTHETIC_LITERAL()', 'private-copy', "Synthetic O'Brien")
    assert values(api, 4)[3]['effectiveValue']['stringValue'] == '=SYNTHETIC_LITERAL()'
    assert values(api, 4)[9] == before_j


@pytest.mark.parametrize('column', range(9))
def test_canonical_formulas_block_without_write(api, column):
    values(api, 4)[column] = {'userEnteredValue': {'formulaValue': '=1+1'}, 'effectiveValue': {'numberValue': 2}}
    assert_code('SCHEDULE_SCOPE_INCOMPLETE', lambda: api.transport.write_d('opaque-a', 'Synthetic Binh',
                                                                        'private-copy', "Synthetic O'Brien"))
    assert not any(r.method == 'PUT' for r in api.requests)


def test_j_formula_is_literal_readonly(api):
    values(api, 4)[9] = {'userEnteredValue': {'formulaValue': '=1+1'}, 'effectiveValue': {'numberValue': 2}}
    assert api.transport.read_tab()['rows'][3]['cells']['J'] == '=1+1'
    api.transport.write_d('opaque-a', 'Synthetic Binh', 'private-copy', "Synthetic O'Brien")
    assert values(api, 4)[9]['userEnteredValue'] == {'formulaValue': '=1+1'}


@pytest.mark.parametrize('effective', [{'errorValue': {'message': 'Secret Name'}}, {'numberValue': True},
                                      {'stringValue': 2}, {'boolValue': 1}, {'stringValue': 'x', 'numberValue': 1}])
def test_invalid_typed_cells_are_sanitized(api, effective):
    values(api, 4)[1] = {'effectiveValue': effective}
    exc = assert_code('SCHEDULE_MALFORMED', api.transport.read_tab)
    assert 'Secret Name' not in str(exc)


@pytest.mark.parametrize('a', [None, 'x', '3'])
def test_populated_rows_need_anchors_even_with_blank_or_text_stt(api, a):
    values(api, 6)[0] = cell(a)
    api.payload['developerMetadata'].pop()
    assert_code('SCHEDULE_SCOPE_INCOMPLETE', api.transport.read_tab)


def test_integer_text_stt_is_kept_as_text_and_adapter_accepts(api):
    values(api, 4)[0] = cell('1')
    assert api.transport.read_tab()['rows'][3]['cells']['A'] == '1'
    adapter = SheetsScheduleAdapter(api.transport, synthetic_roster(), ['private-copy'])
    assert adapter.coverage()['writable']


@pytest.mark.parametrize('mutation', ['missing', 'duplicate_value', 'duplicate_row', 'multirow', 'column', 'wrong_gid', 'wrong_key'])
def test_missing_or_ambiguous_metadata_fails_closed(api, mutation):
    items = api.payload['developerMetadata']
    if mutation == 'missing':
        items.pop()
    elif mutation == 'duplicate_value':
        items[1]['metadataValue'] = items[0]['metadataValue']
    elif mutation == 'duplicate_row':
        items[1]['location'] = deepcopy(items[0]['location'])
    elif mutation == 'multirow':
        items[0]['location']['dimensionRange']['endIndex'] += 1
    elif mutation == 'column':
        items[0]['location']['dimensionRange']['dimension'] = 'COLUMNS'
    elif mutation == 'wrong_gid':
        items[0]['location']['dimensionRange']['sheetId'] = 43
    else:
        items[0]['metadataKey'] = 'untrusted'
    assert_code('SCHEDULE_SCOPE_INCOMPLETE', api.transport.read_tab)


def test_same_metadata_in_top_and_sheet_is_deduplicated_but_conflict_rejected(api):
    api.payload['sheets'][0]['developerMetadata'] = deepcopy(api.payload['developerMetadata'])
    assert len([r for r in api.transport.read_tab()['rows'] if r['anchor']]) == 3
    api.payload['sheets'][0]['developerMetadata'][0]['metadataValue'] = 'conflicting-id'
    assert_code('SCHEDULE_MALFORMED', api.transport.read_tab)


def test_existing_metadata_moves_with_inserted_row_no_stt_derived_identity(api):
    before = SheetsScheduleAdapter(api.transport, synthetic_roster(), ['private-copy']).list_assignments()
    by_anchor = {a['source_locator']['row']: a['assignment_id'] for a in before}
    sheet = api.payload['sheets'][0]
    sheet['data'][0]['rowData'].insert(0, {'values': []})
    sheet['properties']['gridProperties']['rowCount'] += 1
    for item in api.payload['developerMetadata']:
        item['location']['dimensionRange']['startIndex'] += 1
        item['location']['dimensionRange']['endIndex'] += 1
    for merge in sheet['merges']:
        merge['startRowIndex'] += 1
        merge['endRowIndex'] += 1
    adapter = SheetsScheduleAdapter(api.transport, synthetic_roster(), ['private-copy'])
    after = adapter.list_assignments()
    assert {a['source_locator']['row'] - 1: a['assignment_id'] for a in after} == by_anchor
    api.transport.write_d('opaque-a', 'Synthetic Binh', 'private-copy', "Synthetic O'Brien")
    assert json.loads(api.requests[-1].content)['range'] == "'Synthetic O''Brien'!D5"


@pytest.mark.parametrize('bad_merge', [
    {'endRowIndex': 5},
    {'startRowIndex': 3, 'endRowIndex': 50, 'startColumnIndex': 1, 'endColumnIndex': 2},
    {'startRowIndex': True, 'endRowIndex': 5, 'startColumnIndex': 1, 'endColumnIndex': 2},
])
def test_malformed_merges_raise_structured_errors(api, bad_merge):
    api.payload['sheets'][0]['merges'] = [bad_merge]
    assert_code('SCHEDULE_MALFORMED', api.transport.read_tab)


@pytest.mark.parametrize('columns', [(3, 4), (2, 5), (0, 1)])
def test_merged_assignment_or_stt_cells_block_put(api, columns):
    api.payload['sheets'][0]['merges'].append({'startRowIndex': 3, 'endRowIndex': 5,
                                            'startColumnIndex': columns[0], 'endColumnIndex': columns[1]})
    assert_code('SCHEDULE_SCOPE_INCOMPLETE', lambda: api.transport.write_d('opaque-a', 'Synthetic Binh',
                                                                        'private-copy', "Synthetic O'Brien"))
    assert not any(r.method == 'PUT' for r in api.requests)


@pytest.mark.parametrize('change', [
    {'owner_confirmed_copy': False}, {'allowed_spreadsheet_ids': []},
    {'denied_source_ids': [' private-copy ']}, {'spreadsheet_id': ' private-copy '},
    {'sheet_id': True}, {'tab': ''}, {'expected_anchor_count': 0},
    {'anchor_mode': 'invent_ids'}, {'copy_of': 'private-copy'},
    {'allowed_spreadsheet_ids': 'private-copy'}, {'timeout_seconds': float('nan')},
])
def test_config_copy_allow_deny_and_pin_guards_before_dispatch(api, change):
    cfg = {**api.config, **change}
    assert_code('SHEETS_PROVENANCE_REJECTED', lambda: GoogleSheetsTransport(cfg, api.creds, api.client))
    assert api.requests == []


def test_copied_config_and_provenance_cannot_repoint_transport(api):
    api.config.update(spreadsheet_id='other-copy', tab='other', sheet_id=43,
                      allowed_write_anchors=['opaque-other'], write_enabled=False)
    p = api.transport.provenance()
    p.update(spreadsheet_id='other-copy', tab='other')
    assert api.transport.provenance() == {'kind': 'test_copy', 'spreadsheet_id': 'private-copy',
        'tab': "Synthetic O'Brien", 'sheet_id': 42, 'copy_of': None, 'owner_confirmed_copy': True,
        'contains_real_data': True}
    api.transport.write_d('opaque-a', 'Synthetic Binh', 'private-copy', "Synthetic O'Brien")
    assert len([r for r in api.requests if r.method == 'PUT']) == 1


@pytest.mark.parametrize('change', ['id', 'gid', 'title', 'duplicate_title', 'duplicate_gid'])
def test_response_identity_change_blocks_reads_and_writes(api, change):
    p = api.payload
    sheet = p['sheets'][0]
    if change == 'id':
        p['spreadsheetId'] = 'other-copy'
    elif change == 'gid':
        sheet['properties']['sheetId'] = 43
    elif change == 'title':
        sheet['properties']['title'] = 'Other'
    elif change == 'duplicate_title':
        other = deepcopy(sheet)
        other['properties']['sheetId'] = 43
        p['sheets'].append(other)
    else:
        other = deepcopy(sheet)
        other['properties']['title'] = 'Other'
        p['sheets'].append(other)
    assert_code('SHEETS_PROVENANCE_REJECTED', lambda: api.transport.write_d('opaque-a', 'Synthetic Binh',
                                                                          'private-copy', "Synthetic O'Brien"))
    assert not any(r.method == 'PUT' for r in api.requests)


@pytest.mark.parametrize('args', [
    ('opaque-a', 'Synthetic Binh', 'other-copy', "Synthetic O'Brien"),
    ('opaque-a', 'Synthetic Binh', 'private-copy', 'Other tab'),
    ('D4', 'Synthetic Binh', 'private-copy', "Synthetic O'Brien"),
    ('opaque-a', [['Synthetic Binh']], 'private-copy', "Synthetic O'Brien"),
    ('opaque-a', '', 'private-copy', "Synthetic O'Brien"),
])
def test_no_arbitrary_range_value_or_destination_calls(api, args):
    with pytest.raises(TransportRejected):
        api.transport.write_d(*args)
    assert api.requests == []


def test_write_disabled_by_default_and_per_anchor_authorization(api):
    cfg = dict(api.config)
    cfg.pop('write_enabled')
    transport = GoogleSheetsTransport(cfg, api.creds, api.client)
    with pytest.raises(TransportRejected):
        transport.write_d('opaque-a', 'Synthetic Binh', 'private-copy', "Synthetic O'Brien")
    cfg.update(write_enabled=True, allowed_write_anchors=['opaque-b'])
    transport = GoogleSheetsTransport(cfg, api.creds, api.client)
    with pytest.raises(TransportRejected):
        transport.write_d('opaque-a', 'Synthetic Binh', 'private-copy', "Synthetic O'Brien")
    assert api.requests == []


@pytest.mark.parametrize('size', [51, 0, True])
def test_incomplete_or_oversized_grid_coverage_blocks(api, size):
    api.payload['sheets'][0]['properties']['gridProperties']['rowCount'] = size
    assert_code('SCHEDULE_SCOPE_INCOMPLETE', api.transport.read_tab)


def make_sidecar(api, tmp_path):
    tab = api.transport.read_tab()
    sidecar = {'spreadsheet_id': 'private-copy', 'tab': "Synthetic O'Brien", 'sheet_id': 42,
               'structure_fingerprint': structure_fingerprint(tab['rows'], tab['merges']),
               'anchors': [{'row': r['row'], 'anchor': r['anchor'], 'fingerprint': row_fingerprint(r['cells'])}
                           for r in tab['rows'] if r['anchor']]}
    path = tmp_path / 'private-sidecar.json'
    path.write_text(json.dumps(sidecar), encoding='utf-8')
    cfg = {**api.config, 'anchor_mode': 'test_sidecar', 'anchor_sidecar_path': str(path)}
    cfg.pop('metadata_key')
    api.payload['developerMetadata'] = []
    return GoogleSheetsTransport(cfg, api.creds, api.client), path, sidecar


def test_test_sidecar_accepts_d_j_changes_and_never_writes_identity(api, tmp_path):
    transport, _, _ = make_sidecar(api, tmp_path)
    values(api, 4)[3] = cell('Synthetic Chi')
    values(api, 4)[9] = cell('Ops J edit')
    assert transport.read_tab()['rows'][3]['anchor'] == 'opaque-a'
    transport.write_d('opaque-a', 'Synthetic Binh', 'private-copy', "Synthetic O'Brien")
    assert values(api, 4)[9]['effectiveValue'] == {'stringValue': 'Ops J edit'}
    assert set(r.method for r in api.requests) == {'GET', 'PUT'}
    assert api.payload['developerMetadata'] == []


@pytest.mark.parametrize('change', ['header', 'class', 'insert', 'merge', 'identity', 'row_hash', 'structure_hash', 'duplicate', 'missing_file'])
def test_sidecar_fingerprints_pins_and_ambiguity_fail_closed(api, tmp_path, change):
    transport, path, sidecar = make_sidecar(api, tmp_path)
    if change == 'header':
        values(api, 2)[0] = cell('Thứ 3 - 13/10/2026')
    elif change == 'class':
        values(api, 4)[1] = cell('Another Track')
    elif change == 'insert':
        api.payload['sheets'][0]['properties']['gridProperties']['rowCount'] += 1
        api.payload['sheets'][0]['data'][0]['rowData'].insert(0, {'values': []})
    elif change == 'merge':
        api.payload['sheets'][0]['merges'].pop()
    elif change == 'identity':
        sidecar['spreadsheet_id'] = 'other-copy'
    elif change == 'row_hash':
        sidecar['anchors'][0]['fingerprint'] = 'bad'
    elif change == 'structure_hash':
        sidecar['structure_fingerprint'] = 'bad'
    elif change == 'duplicate':
        sidecar['anchors'][1]['anchor'] = sidecar['anchors'][0]['anchor']
    else:
        path.unlink()
    if change != 'missing_file':
        path.write_text(json.dumps(sidecar), encoding='utf-8')
    assert_code('SCHEDULE_SCOPE_INCOMPLETE', lambda: transport.write_d('opaque-a', 'Synthetic Binh',
                                                                     'private-copy', "Synthetic O'Brien"))
    assert not any(r.method == 'PUT' for r in api.requests)


@pytest.mark.parametrize('path', [None, '', 'relative.json', '/synthetic-missing-directory/token.json'])
def test_missing_or_unspecified_auth_never_uses_profile_or_dispatches(api, path):
    assert_code('SHEETS_AUTH_REQUIRED', lambda: GoogleSheetsTransport(
        {**api.config, 'credential_path': path}, http_client=api.client))
    assert api.requests == []


def private_credential(path, payload, mode=0o600):
    """Write a credential the way the setup guide requires: owner-only, outside the repo."""
    path = Path(path)
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding='utf-8')
    path.chmod(mode)
    return path


def authorized_user_payload(scopes):
    return {'token': 'synthetic-saved-token', 'refresh_token': 'synthetic-refresh-token',
            'client_id': 'synthetic-client', 'client_secret': 'synthetic-client-secret',
            'expiry': '2099-01-01T00:00:00Z', 'scopes': scopes}


@pytest.mark.parametrize('stored_scopes', [[SHEETS_SCOPE], SHEETS_SCOPE])
def test_existing_hermes_token_format_without_type_is_reused_without_file_edits(api, tmp_path, stored_scopes):
    path = private_credential(tmp_path / 'google_token.json', authorized_user_payload(stored_scopes))
    original = path.read_bytes()
    transport = GoogleSheetsTransport({**api.config, 'credential_path': str(path)}, http_client=api.client)
    creds = transport._credentials
    assert set(creds.scopes) == {SHEETS_SCOPE} and creds.valid
    # File-format construction is real google-auth; mock only the HTTP credential used by this fixture.
    api.creds.token = creds.token
    transport.read_tab()
    assert path.read_bytes() == original


def test_legacy_scope_key_is_supported(api, tmp_path):
    payload = authorized_user_payload([SHEETS_SCOPE])
    payload['scope'] = payload.pop('scopes')[0]
    path = private_credential(tmp_path / 'token.json', payload)
    transport = GoogleSheetsTransport({**api.config, 'credential_path': str(path)}, http_client=api.client)
    assert set(transport._credentials.scopes) == {SHEETS_SCOPE}


@pytest.mark.parametrize('scopes', [[], None, ['https://www.googleapis.com/auth/spreadsheets.readonly'],
                                   ['https://www.googleapis.com/auth/drive'], ['gmail'], 42])
def test_missing_readonly_or_unrelated_token_scopes_fail_closed(api, tmp_path, scopes):
    path = private_credential(tmp_path / 'token.json', authorized_user_payload(scopes))
    assert_code('SHEETS_AUTH_SCOPE', lambda: GoogleSheetsTransport(
        {**api.config, 'credential_path': str(path)}, http_client=api.client))
    assert api.requests == []


BROAD_HERMES_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/contacts.readonly',
    SHEETS_SCOPE, 'https://www.googleapis.com/auth/documents',
]


@pytest.mark.parametrize('scopes', [
    pytest.param(BROAD_HERMES_SCOPES, id='shared_hermes_workspace_token'),
    pytest.param([SHEETS_SCOPE, 'https://www.googleapis.com/auth/drive'], id='sheets_plus_drive'),
    pytest.param(' '.join([SHEETS_SCOPE, 'https://www.googleapis.com/auth/drive']), id='space_separated_broad'),
])
def test_broad_grant_fails_closed_before_any_google_call(api, tmp_path, scopes, monkeypatch):
    """A Sheets-only grant is required; a broad token is not narrowed at refresh."""
    def forbidden(*args, **kwargs):
        raise AssertionError('no credential construction or refresh may happen')

    monkeypatch.setattr(
        'bee_bot.google_sheets_transport.user_credentials.Credentials.from_authorized_user_info', forbidden)
    path = private_credential(tmp_path / 'token.json', authorized_user_payload(scopes))
    original = path.read_bytes()
    assert_code('SHEETS_AUTH_SCOPE', lambda: GoogleSheetsTransport(
        {**api.config, 'credential_path': str(path)}, http_client=api.client))
    assert api.requests == []
    assert path.read_bytes() == original  # The private token file is never rewritten.


def test_service_account_declaring_broad_scopes_fails_closed(api, tmp_path, monkeypatch):
    monkeypatch.setattr(
        'bee_bot.google_sheets_transport.service_account.Credentials.from_service_account_info',
        lambda payload, scopes: pytest.fail('must not build broad service-account credentials'))
    path = private_credential(tmp_path / 'service-account.json', {
        'type': 'service_account', 'token_uri': 'https://oauth2.googleapis.com/token',
        'private_key': 'synthetic-key-placeholder', 'scopes': [SHEETS_SCOPE, 'https://www.googleapis.com/auth/drive']})
    assert_code('SHEETS_AUTH_SCOPE', lambda: GoogleSheetsTransport(
        {**api.config, 'credential_path': str(path)}, http_client=api.client))
    assert api.requests == []


def test_sheets_only_credential_outside_repo_with_owner_only_mode_is_accepted(api, tmp_path):
    path = private_credential(tmp_path / 'google_token.json', authorized_user_payload([SHEETS_SCOPE]))
    assert REPO_ROOT not in path.parents  # pytest tmp_path is outside the checkout.
    transport = GoogleSheetsTransport({**api.config, 'credential_path': str(path)}, http_client=api.client)
    assert set(transport._credentials.scopes) == {SHEETS_SCOPE}
    api.creds.token = transport._credentials.token
    transport.read_tab()
    assert [r.method for r in api.requests] == ['GET']


@pytest.mark.parametrize('mode', [0o644, 0o640, 0o604, 0o666, 0o660])
def test_group_or_world_readable_credential_is_rejected(api, tmp_path, mode):
    path = private_credential(tmp_path / 'token.json', authorized_user_payload([SHEETS_SCOPE]), mode)
    assert_code('SHEETS_AUTH_INSECURE', lambda: GoogleSheetsTransport(
        {**api.config, 'credential_path': str(path)}, http_client=api.client))
    assert api.requests == []


def test_credential_inside_repository_is_rejected(api, tmp_path):
    """A credential in the checkout could be committed, so it is never read."""
    inside = REPO_ROOT / '.bee-bot' / 'test-auth-harden-token.json'
    inside.parent.mkdir(parents=True, exist_ok=True)
    try:
        private_credential(inside, authorized_user_payload([SHEETS_SCOPE]))
        assert_code('SHEETS_AUTH_LOCATION', lambda: GoogleSheetsTransport(
            {**api.config, 'credential_path': str(inside)}, http_client=api.client))
        # A path that walks back into the repository is resolved, not trusted.
        detour = str(tmp_path / '..' / os.path.relpath(inside, tmp_path.parent))
        assert_code('SHEETS_AUTH_LOCATION', lambda: GoogleSheetsTransport(
            {**api.config, 'credential_path': detour}, http_client=api.client))
    finally:
        inside.unlink(missing_ok=True)
    assert api.requests == []


@pytest.mark.parametrize('direction', ['link_into_repo', 'link_in_repo'])
def test_symlinked_credential_is_rejected(api, tmp_path, direction):
    real = private_credential(tmp_path / 'real-token.json', authorized_user_payload([SHEETS_SCOPE]))
    if direction == 'link_into_repo':
        target = REPO_ROOT / '.bee-bot' / 'test-auth-harden-target.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        private_credential(target, authorized_user_payload([SHEETS_SCOPE]))
        link = tmp_path / 'link.json'
    else:
        target, link = real, REPO_ROOT / '.bee-bot' / 'test-auth-harden-link.json'
        link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)
    try:
        assert_code('SHEETS_AUTH_LOCATION', lambda: GoogleSheetsTransport(
            {**api.config, 'credential_path': str(link)}, http_client=api.client))
    finally:
        link.unlink(missing_ok=True)
        if direction == 'link_into_repo':
            target.unlink(missing_ok=True)
    assert api.requests == []


def test_symlinked_parent_directory_into_repository_is_rejected(api, tmp_path):
    """The final component is a real file, so only full resolution catches this."""
    inside = REPO_ROOT / '.bee-bot'
    inside.mkdir(parents=True, exist_ok=True)
    target = private_credential(inside / 'test-auth-harden-parent.json',
                                authorized_user_payload([SHEETS_SCOPE]))
    link_dir = tmp_path / 'linked-dir'
    link_dir.symlink_to(inside, target_is_directory=True)
    try:
        assert_code('SHEETS_AUTH_LOCATION', lambda: GoogleSheetsTransport(
            {**api.config, 'credential_path': str(link_dir / target.name)}, http_client=api.client))
    finally:
        target.unlink(missing_ok=True)
    assert api.requests == []


def test_symlink_outside_repository_is_also_rejected(api, tmp_path):
    """A link is not the credential: its own mode and target can change later."""
    real = private_credential(tmp_path / 'real-token.json', authorized_user_payload([SHEETS_SCOPE]))
    link = tmp_path / 'elsewhere-link.json'
    link.symlink_to(real)
    assert_code('SHEETS_AUTH_LOCATION', lambda: GoogleSheetsTransport(
        {**api.config, 'credential_path': str(link)}, http_client=api.client))
    assert api.requests == []


def test_directory_as_credential_path_is_rejected(api, tmp_path):
    assert_code('SHEETS_AUTH_LOCATION', lambda: GoogleSheetsTransport(
        {**api.config, 'credential_path': str(tmp_path)}, http_client=api.client))
    assert api.requests == []


def test_rejected_credential_location_errors_leak_no_path_or_content(api, tmp_path):
    path = private_credential(tmp_path / 'secret-name-token.json',
                              authorized_user_payload(BROAD_HERMES_SCOPES), 0o644)
    exc = assert_code('SHEETS_AUTH_INSECURE', lambda: GoogleSheetsTransport(
        {**api.config, 'credential_path': str(path)}, http_client=api.client))
    rendered = ''.join(traceback.format_exception(exc))
    for private in (str(path), path.name, 'synthetic-refresh-token', 'synthetic-client-secret',
                    'secret-name-token', str(tmp_path)):
        assert private not in rendered


def test_service_account_loaded_with_sheets_only_and_no_delegation(api, tmp_path, monkeypatch):
    path = private_credential(tmp_path / 'service-account.json',
                              {'type': 'service_account', 'token_uri': 'https://oauth2.googleapis.com/token',
                               'private_key': 'synthetic-key-placeholder'})
    seen = []

    def load(payload, scopes):
        seen.append((payload['type'], scopes))
        return api.creds

    monkeypatch.setattr('bee_bot.google_sheets_transport.service_account.Credentials.from_service_account_info', load)
    transport = GoogleSheetsTransport({**api.config, 'credential_path': str(path)}, http_client=api.client)
    transport.read_tab()
    assert seen == [('service_account', [SHEETS_SCOPE])]


@pytest.mark.parametrize('payload', ['not json Secret Name synthetic-secret-token',
                                   json.dumps({'type': 'service_account', 'token_uri': 'https://private.example/'}),
                                   json.dumps({'type': 'authorized_user', 'scopes': [SHEETS_SCOPE]})])
def test_invalid_credential_data_sanitized(api, tmp_path, payload):
    path = private_credential(tmp_path / 'private-copy-token.json', payload)
    exc = assert_code('SHEETS_AUTH_FAILED', lambda: GoogleSheetsTransport(
        {**api.config, 'credential_path': str(path)}, http_client=api.client))
    rendered = ''.join(traceback.format_exception(exc))
    for private in ('Secret Name', 'synthetic-secret-token', 'private.example', str(path)):
        assert private not in rendered


@pytest.mark.parametrize('scopes,granted', [([], None), ([SHEETS_SCOPE, 'drive'], None),
                                          ([SHEETS_SCOPE], ['readonly']), ([SHEETS_SCOPE], [SHEETS_SCOPE, 'drive'])])
def test_injected_credentials_are_checked_for_sheets_only(api, scopes, granted):
    api.creds.scopes, api.creds.granted_scopes = scopes, granted
    assert_code('SHEETS_AUTH_SCOPE', lambda: GoogleSheetsTransport(api.config, api.creds, api.client))
    assert api.requests == []


def test_refresh_before_each_dispatch_and_before_put(api):
    api.creds.valid = False
    api.transport.read_tab()
    assert api.creds.events == ['refresh', 'GET']
    api.creds.events.clear()
    api.after_get = lambda: setattr(api.creds, 'valid', False)
    api.transport.write_d('opaque-a', 'Synthetic Binh', 'private-copy', "Synthetic O'Brien")
    assert api.creds.events == ['GET', 'refresh', 'PUT']
    assert api.creds.refreshes == 2


def test_refresh_failure_before_put_has_no_write_and_no_retry(api):
    def expire():
        api.creds.valid = False
        api.creds.fail_refresh = True
    api.after_get = expire
    exc = assert_code('SHEETS_AUTH_FAILED', lambda: api.transport.write_d('opaque-a', 'Synthetic Binh',
                                                                        'private-copy', "Synthetic O'Brien"))
    assert api.creds.refreshes == 1
    assert not any(r.method == 'PUT' for r in api.requests)
    assert 'synthetic-secret-token' not in ''.join(traceback.format_exception(exc))


@pytest.mark.parametrize('status,code', [(429, 'SHEETS_RATE_LIMITED'), (503, 'SCHEDULE_UNAVAILABLE'),
                                       (403, 'SHEETS_PERMISSION_DENIED'), (401, 'SHEETS_AUTH_FAILED'),
                                       (302, 'SCHEDULE_UNAVAILABLE')])
def test_read_http_errors_surface_without_retry_or_private_details(api, status, code):
    api.fault = ('GET', status)
    exc = assert_code(code, api.transport.read_tab)
    assert len(api.requests) == 1
    assert 'private-copy' not in str(exc) and 'Secret Name' not in str(exc)


def test_read_timeout_blocks_write_without_retry(api):
    api.fault = ('GET', httpx.ReadTimeout('Secret Name synthetic-secret-token'))
    assert_code('SCHEDULE_UNAVAILABLE', lambda: api.transport.write_d('opaque-a', 'Synthetic Binh',
                                                                    'private-copy', "Synthetic O'Brien"))
    assert [r.method for r in api.requests] == ['GET']


@pytest.mark.parametrize('status', [429, 500, 502, 503, 504, 302])
def test_write_quota_5xx_or_redirect_is_uncertain_never_retried(api, status):
    api.fault = ('PUT', status)
    with pytest.raises(TransportTimeout) as caught:
        api.transport.write_d('opaque-a', 'Synthetic Binh', 'private-copy', "Synthetic O'Brien")
    assert [r.method for r in api.requests] == ['GET', 'PUT']
    assert values(api, 4)[3] == cell('Synthetic An')
    assert 'private-copy' not in str(caught.value) and 'Secret Name' not in str(caught.value)


@pytest.mark.parametrize('status', [400, 401, 403, 404])
def test_clear_write_refusal_never_retried(api, status):
    api.fault = ('PUT', status)
    with pytest.raises(TransportRejected):
        api.transport.write_d('opaque-a', 'Synthetic Binh', 'private-copy', "Synthetic O'Brien")
    assert [r.method for r in api.requests] == ['GET', 'PUT']


@pytest.mark.parametrize('applied', [False, True])
def test_write_timeout_before_or_after_apply_requires_readonly_reconcile(api, applied):
    api.fault = ('PUT', 'apply_then_timeout' if applied else httpx.ConnectTimeout('private-copy Secret Name'))
    with pytest.raises(TransportTimeout):
        api.transport.write_d('opaque-a', 'Synthetic Binh', 'private-copy', "Synthetic O'Brien")
    assert [r.method for r in api.requests] == ['GET', 'PUT']
    api.fault = None
    actual = api.transport.read_tab()['rows'][3]['cells']['D']
    assert actual == ('Synthetic Binh' if applied else 'Synthetic An')
    assert len([r for r in api.requests if r.method == 'PUT']) == 1


@pytest.mark.parametrize('receipt', [{}, {'spreadsheetId': 'other-copy', 'updatedCells': 1},
                                    {'spreadsheetId': 'private-copy', 'updatedCells': 2}])
def test_malformed_success_receipt_remains_uncertain_after_landing(api, receipt):
    api.receipt = receipt
    with pytest.raises(TransportTimeout):
        api.transport.write_d('opaque-a', 'Synthetic Binh', 'private-copy', "Synthetic O'Brien")
    assert values(api, 4)[3] == cell('Synthetic Binh')
    assert len([r for r in api.requests if r.method == 'PUT']) == 1


def test_http_logs_and_exception_tracebacks_contain_no_ids_names_tokens_or_urls(api, caplog):
    caplog.set_level(logging.DEBUG)
    api.transport.read_tab()
    api.fault = ('PUT', httpx.ReadTimeout('synthetic-secret-token private-copy Secret Name https://private.example/'))
    write_args = ('opaque-a', 'Secret Name', 'private-copy', api.config['tab'])
    with pytest.raises(TransportTimeout) as caught:
        api.transport.write_d(*write_args)
    rendered = caplog.text + ''.join(traceback.format_exception(caught.value))
    for private in ('synthetic-secret-token', 'private-copy', 'Secret Name', 'private.example', 'Synthetic O', API_ROOT):
        assert private not in rendered
    # Outside private I/O, other callers' ordinary logging still works.
    logging.getLogger('httpx').info('ordinary-public-diagnostic')
    assert 'ordinary-public-diagnostic' in caplog.text


def test_injected_http_client_lifetime_is_caller_owned(api):
    api.transport.close()
    assert not api.client.is_closed
    api.transport.read_tab()


@pytest.mark.parametrize('change', [
    {'updatedRange': "'Synthetic O''Brien'!J4"},
    {'updatedRange': "'Synthetic O''Brien'!D5"},
    {'updatedRange': "'Another tab'!D4"},
    {'updatedCells': True}, {'updatedColumns': 2}, {'updatedRows': 0},
])
def test_receipt_must_confirm_exact_cell_and_typed_single_cell_counts(api, change):
    api.receipt = {'spreadsheetId': 'private-copy', 'updatedRange': "'Synthetic O''Brien'!D4",
                   'updatedCells': 1, 'updatedColumns': 1, 'updatedRows': 1, **change}
    with pytest.raises(TransportTimeout):
        api.transport.write_d('opaque-a', 'Synthetic Binh', 'private-copy', api.config['tab'])
    assert len([r for r in api.requests if r.method == 'PUT']) == 1


@pytest.mark.parametrize('method', ['GET', 'PUT'])
def test_invalid_json_success_is_sanitized_and_not_retried(api, method):
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == method:
            return httpx.Response(200, text='private-copy Secret Name synthetic-secret-token')
        return httpx.Response(200, json=api.payload)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transport = GoogleSheetsTransport(api.config, api.creds, client)
        if method == 'GET':
            exc = assert_code('SCHEDULE_MALFORMED', transport.read_tab)
            assert len(requests) == 1
        else:
            with pytest.raises(TransportTimeout) as caught:
                transport.write_d('opaque-a', 'Synthetic Binh', 'private-copy', api.config['tab'])
            exc = caught.value
            assert [r.method for r in requests] == ['GET', 'PUT']
        assert 'synthetic-secret-token' not in str(exc)


def test_adapter_uncertain_timeout_readback_and_reopen_never_rewrite(api):
    adapter = SheetsScheduleAdapter(api.transport, synthetic_roster(), ['private-copy'])
    assignment = next(a for a in adapter.list_assignments() if a['source_locator']['row'] == 4)
    updates = {assignment['assignment_id']: 'binh'}
    expected = {assignment['assignment_id']: assignment}
    api.fault = ('PUT', 'apply_then_timeout')
    assert_code('WRITE_UNCERTAIN', lambda: adapter.apply_updates(updates, expected))
    api.fault = None
    transport = GoogleSheetsTransport(api.config, api.creds, api.client)
    reopened = SheetsScheduleAdapter(transport, synthetic_roster(), ['private-copy'])
    assert reopened.verify_applied(updates, expected)
    assert len([r for r in api.requests if r.method == 'PUT']) == 1


@pytest.mark.parametrize('a', [None, 'text', 0, -1, True, 1.5])
def test_invalid_stt_on_anchored_row_is_incomplete_even_if_other_cells_are_present(api, a):
    values(api, 4)[0] = cell(a)
    assert_code('SCHEDULE_SCOPE_INCOMPLETE', api.transport.read_tab)


def test_real_google_auth_refresh_is_mocked_at_token_http_boundary(api, tmp_path, monkeypatch):
    payload = authorized_user_payload([SHEETS_SCOPE])
    payload['expiry'] = '2000-01-01T00:00:00Z'
    path = private_credential(tmp_path / 'expired.json', payload)
    original = path.read_bytes()
    calls, closed = [], []

    class TokenRequest:
        session = SimpleNamespace(close=lambda: closed.append(True))

        def __call__(self, url, method='GET', body=None, headers=None, **kwargs):
            calls.append((url, method, parse_qs(body.decode())))
            api.creds.token = 'synthetic-real-refresh-token'
            return SimpleNamespace(status=200, headers={}, data=json.dumps({
                'access_token': api.creds.token, 'expires_in': 3600, 'token_type': 'Bearer',
                'scope': SHEETS_SCOPE}).encode())

    monkeypatch.setattr('bee_bot.google_sheets_transport.Request', TokenRequest)
    transport = GoogleSheetsTransport({**api.config, 'credential_path': str(path)}, http_client=api.client)
    transport.read_tab()
    assert len(calls) == 1 and calls[0][:2] == ('https://oauth2.googleapis.com/token', 'POST')
    assert calls[0][2]['scope'] == [SHEETS_SCOPE]
    assert calls[0][2]['grant_type'] == ['refresh_token']
    assert closed == [True] and path.read_bytes() == original
    assert len(api.requests) == 1


def test_scopes_changed_by_refresh_block_dispatch(api):
    api.creds.valid = False

    def refresh(request):
        api.creds.valid = True
        api.creds.granted_scopes = [SHEETS_SCOPE, 'drive']

    api.creds.refresh = refresh
    assert_code('SHEETS_AUTH_SCOPE', api.transport.read_tab)
    assert api.requests == []


def test_default_http_transport_has_zero_retries_and_owned_client_is_closed(api, monkeypatch):
    built = []
    owned = SimpleNamespace(close=lambda: built.append('closed'))
    monkeypatch.setattr('bee_bot.google_sheets_transport.httpx.HTTPTransport',
                        lambda **kwargs: built.append(kwargs) or 'mock-transport')
    monkeypatch.setattr('bee_bot.google_sheets_transport.httpx.Client',
                        lambda **kwargs: built.append(kwargs) or owned)
    transport = GoogleSheetsTransport(api.config, api.creds)
    transport.close()
    assert built == [{'retries': 0}, {'transport': 'mock-transport', 'follow_redirects': False}, 'closed']


def test_real_service_account_signs_sheets_only_grant_with_mock_token_exchange(api, tmp_path, monkeypatch):
    # Generate a disposable test key, unrelated to any Google account. Nothing
    # is copied from runtime credentials or persisted in the repository.
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
    path = tmp_path / 'disposable-synthetic-account.json'
    path.write_text(json.dumps({'type': 'service_account', 'token_uri': 'https://oauth2.googleapis.com/token',
        'private_key': key, 'private_key_id': 'synthetic-key', 'client_email': 'synthetic@invalid.example',
        'client_id': 'synthetic-client'}))
    path.chmod(0o600)
    claims = []

    class TokenRequest:
        session = SimpleNamespace(close=lambda: None)

        def __call__(self, url, method='GET', body=None, **kwargs):
            assert url == 'https://oauth2.googleapis.com/token' and method == 'POST'
            form = parse_qs(body.decode())
            assert form['grant_type'] == ['urn:ietf:params:oauth:grant-type:jwt-bearer']
            claim = form['assertion'][0].split('.')[1]
            claims.append(json.loads(base64.urlsafe_b64decode(claim + '=' * (-len(claim) % 4))))
            api.creds.token = 'synthetic-service-token'
            return SimpleNamespace(status=200, headers={}, data=json.dumps({
                'access_token': api.creds.token, 'expires_in': 3600, 'token_type': 'Bearer'}).encode())

    monkeypatch.setattr('bee_bot.google_sheets_transport.Request', TokenRequest)
    try:
        transport = GoogleSheetsTransport({**api.config, 'credential_path': str(path)}, http_client=api.client)
        transport.read_tab()
        assert len(claims) == 1 and claims[0]['scope'] == SHEETS_SCOPE
        assert claims[0]['iss'] == 'synthetic@invalid.example' and 'sub' not in claims[0]
        assert [r.method for r in api.requests] == ['GET']
    finally:
        path.unlink()
