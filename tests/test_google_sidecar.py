"""Mocked Google API tests for the `test_sidecar` anchor path.

No network, no credentials, no real workbook: every HTTP call is an httpx
MockTransport handler and every cell value is synthetic. The sidecar is the
trusted test-location map; these tests pin when it may be reused (value-only
edits of D/J) and when it must fail closed (structural drift, missing or
duplicate anchors), always without issuing a write.

The normalized grid is rebuilt locally from the mocked payload rather than
taken from the transport, so a change in the transport's normalization makes
the sidecar stop matching instead of silently redefining the fingerprint.
"""
import json

import httpx
import pytest

from bee_bot.errors import BeeBotError
from bee_bot.google_sheets_transport import (
    GoogleSheetsTransport, SHEETS_SCOPE, row_fingerprint, structure_fingerprint)
from bee_bot.sheets_copy_transport import COLUMNS, TransportRejected

SPREADSHEET = 'approved-test-copy'
TAB = 'Lịch thử'
GID = 1234
ANCHORS = ('anc-synthetic-1', 'anc-synthetic-2')
# Rows 4-5 are one merged class block (B/C and F/G), the shape the real tab uses.
MERGES = [{'start': 4, 'end': 5, 'columns': ['B', 'C']},
          {'start': 4, 'end': 5, 'columns': ['F', 'G']}]


def base_rows():
    """A1:J grid: title, day header, column header, two merged data rows."""
    return [
        ['LỊCH THỬ — DỮ LIỆU GIẢ LẬP', None, None, None, None, None, None, None, None, None],
        ['Thứ 2 - 12/10/2026', None, None, None, None, None, None, None, None, None],
        ['STT', 'Khóa', 'Session', 'Lab Coach', 'Key Coach', 'Phòng', 'Buổi', 'Sức chứa', 'Ghi chú', 'Trạng thái'],
        [1, 'Track 1', 'CS1', 'Coach One', 'Key One', 'H210', 'Sáng', 30, None, 'ghi chú vận hành 1'],
        [2, None, None, 'Coach Two', 'Key One', None, None, 30, None, 'ghi chú vận hành 2'],
    ]


def credentials():
    class Credentials:
        valid = True
        token = 'fake-test-token'
        scopes = [SHEETS_SCOPE]
        granted_scopes = [SHEETS_SCOPE]

        def has_scopes(self, scopes):
            return scopes == [SHEETS_SCOPE]

    return Credentials()


def put_receipt(request):
    """The receipt shape documented for spreadsheets.values.update."""
    target = json.loads(request.content)['range']
    return {'spreadsheetId': SPREADSHEET, 'updatedRange': target,
            'updatedRows': 1, 'updatedColumns': 1, 'updatedCells': 1}


def grid_response(rows, merges=MERGES, *, column_count=10):
    """Shape of the fields= GET this transport issues, with no extra data."""
    def cell(value):
        if value is None:
            return {}
        if isinstance(value, str) and value.startswith('='):
            return {'userEnteredValue': {'formulaValue': value},
                    'effectiveValue': {'stringValue': 'đã tính'}}
        key = 'numberValue' if isinstance(value, (int, float)) else 'stringValue'
        return {'userEnteredValue': {key: value}, 'effectiveValue': {key: value}}

    return {
        'spreadsheetId': SPREADSHEET,
        'sheets': [{
            'properties': {'sheetId': GID, 'title': TAB,
                           'gridProperties': {'rowCount': len(rows), 'columnCount': column_count}},
            'merges': [{'sheetId': GID, 'startRowIndex': m['start'] - 1, 'endRowIndex': m['end'],
                        'startColumnIndex': COLUMNS.index(m['columns'][0]),
                        'endColumnIndex': COLUMNS.index(m['columns'][-1]) + 1} for m in merges],
            'data': [{'startRow': 0, 'startColumn': 0,
                      'rowData': [{'values': [cell(v) for v in row]} for row in rows]}],
        }],
    }


def normalized(rows):
    """Independent expectation of the transport's normalized rows (A-J)."""
    out = []
    for index, row in enumerate(rows, 1):
        cells = {}
        for column, value in zip(COLUMNS, row):
            # A J formula is preserved as its expression; nothing else may be one.
            cells[column] = value
        out.append({'row': index, 'cells': cells})
    return out


def sidecar_payload(rows, merges=MERGES, anchor_rows=(4, 5), anchors=ANCHORS, **changes):
    normalised = normalized(rows)
    payload = {
        'spreadsheet_id': SPREADSHEET, 'tab': TAB, 'sheet_id': GID,
        'structure_fingerprint': structure_fingerprint(normalised, merges),
        'anchors': [{'row': row, 'anchor': anchor,
                     'fingerprint': row_fingerprint(
                         normalised[row - 1]['cells'] if 1 <= row <= len(normalised)
                         else dict.fromkeys(COLUMNS))}
                    for row, anchor in zip(anchor_rows, anchors)],
    }
    payload.update(changes)
    return payload


def write_sidecar(tmp_path, payload):
    path = tmp_path / 'anchors.json'
    path.write_text(json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload,
                    encoding='utf-8')
    return path


def config(sidecar_path, **changes):
    return {
        'spreadsheet_id': SPREADSHEET, 'tab': TAB, 'sheet_id': GID,
        'allowed_spreadsheet_ids': [SPREADSHEET], 'denied_source_ids': [],
        'owner_confirmed_copy': True, 'max_rows': 20, 'expected_anchor_count': 2,
        'anchor_mode': 'test_sidecar', 'anchor_sidecar_path': str(sidecar_path),
        'allowed_write_anchors': list(ANCHORS), 'write_enabled': True,
        **changes,
    }


def transport_for(tmp_path, served_rows, *, sidecar=None, merges=MERGES, served_merges=None, **overrides):
    """Transport whose sidecar describes `sidecar` rows but whose API serves `served_rows`."""
    methods = []

    def handler(request):
        methods.append(request.method)
        if request.method == 'GET':
            return httpx.Response(200, json=grid_response(served_rows, served_merges or merges))
        return httpx.Response(200, json=put_receipt(request))

    path = write_sidecar(tmp_path, sidecar if sidecar is not None else sidecar_payload(base_rows(), merges))
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GoogleSheetsTransport(config(path, **overrides), credentials=credentials(),
                                 http_client=client), methods


def test_matching_structure_permits_read(tmp_path):
    rows = base_rows()
    transport, methods = transport_for(tmp_path, rows)
    tab = transport.read_tab()
    assert [row['anchor'] for row in tab['rows']] == [None, None, None, *ANCHORS]
    assert tab['rows'][3]['cells'] == dict(zip(COLUMNS, rows[3]))
    assert tab['rows'][4]['cells']['B'] is None  # Merged-away cell stays blank.
    assert tab['merges'] == MERGES
    assert methods == ['GET']


def test_value_only_d_and_j_change_keeps_sidecar_valid(tmp_path):
    """D is the column the bot rewrites and J is ops-owned, so neither is bound."""
    rows = base_rows()
    rows[3][3], rows[4][3] = 'Coach Three', 'Coach Four'
    rows[3][9], rows[4][9] = 'vận hành đã sửa', '=HYPERLINK("#","ops")'
    transport, methods = transport_for(tmp_path, rows, sidecar=sidecar_payload(base_rows()))
    tab = transport.read_tab()
    assert [row['anchor'] for row in tab['rows'][3:]] == list(ANCHORS)
    assert [tab['rows'][i]['cells']['D'] for i in (3, 4)] == ['Coach Three', 'Coach Four']
    # The J formula is returned as its expression, never resolved or rewritten.
    assert tab['rows'][4]['cells']['J'] == '=HYPERLINK("#","ops")'
    transport.write_d(ANCHORS[1], 'Coach Five', SPREADSHEET, TAB)
    assert methods == ['GET', 'GET', 'PUT']


def test_write_targets_the_anchored_row_only(tmp_path):
    sent = []

    def handler(request):
        if request.method == 'GET':
            return httpx.Response(200, json=grid_response(base_rows()))
        sent.append((request.url.raw_path.split(b'?')[0], request.url.params['valueInputOption'],
                     json.loads(request.content)))
        return httpx.Response(200, json=put_receipt(request))

    path = write_sidecar(tmp_path, sidecar_payload(base_rows()))
    client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = GoogleSheetsTransport(config(path), credentials=credentials(), http_client=client)
    transport.write_d(ANCHORS[1], 'Coach Five', SPREADSHEET, TAB)
    target, option, body = sent[0]
    assert target.endswith(b'D5') and b'J' not in target.rsplit(b'%21', 1)[-1]
    assert option == 'RAW'
    assert body == {'range': f"'{TAB}'!D5", 'majorDimension': 'ROWS', 'values': [['Coach Five']]}


def structural_variants():
    """Grid edits that must invalidate a sidecar approved for the base layout."""
    appended = base_rows() + [[None] * 10]
    removed = base_rows()[:-1]
    reordered = base_rows()
    reordered[3], reordered[4] = reordered[4], reordered[3]
    moved_room = base_rows()
    moved_room[3][5] = 'H999'
    renamed_header = base_rows()
    renamed_header[2][2] = 'Ca học'  # Bound header cell (column C).
    swapped_columns = base_rows()
    swapped_columns[3][3], swapped_columns[3][5] = swapped_columns[3][5], swapped_columns[3][3]
    inserted_note = base_rows()
    inserted_note[0][1] = 'ghi chú mới'
    extra_track = base_rows()
    extra_track[4][1] = 'Track 9'  # Merged cell gained content: block changed.
    return {
        'appended_blank_row': (appended, MERGES),
        'removed_row': (removed, [{'start': 4, 'end': 4, 'columns': ['B', 'C']},
                                  {'start': 4, 'end': 4, 'columns': ['F', 'G']}]),
        'reordered_rows': (reordered, MERGES),
        'changed_room': (moved_room, MERGES),
        'renamed_bound_header': (renamed_header, MERGES),
        'coach_column_swapped_with_room': (swapped_columns, MERGES),
        'new_preamble_cell': (inserted_note, MERGES),
        'merged_cell_filled': (extra_track, MERGES),
        'merge_widened': (base_rows(), [{'start': 4, 'end': 5, 'columns': ['B', 'C']},
                                        {'start': 4, 'end': 5, 'columns': ['E', 'F', 'G']}]),
        'merge_dropped': (base_rows(), [{'start': 4, 'end': 5, 'columns': ['B', 'C']}]),
        'merge_shifted': (base_rows(), [{'start': 3, 'end': 4, 'columns': ['B', 'C']},
                                        {'start': 4, 'end': 5, 'columns': ['F', 'G']}]),
    }


@pytest.mark.parametrize('variant', sorted(structural_variants()))
def test_structural_change_fails_closed_without_write(tmp_path, variant):
    served_rows, served_merges = structural_variants()[variant]
    transport, methods = transport_for(tmp_path, served_rows, served_merges=served_merges,
                                       sidecar=sidecar_payload(base_rows()))
    with pytest.raises(BeeBotError) as error:
        transport.read_tab()
    assert error.value.code == 'SCHEDULE_SCOPE_INCOMPLETE'
    with pytest.raises((BeeBotError, TransportRejected)):
        transport.write_d(ANCHORS[0], 'Coach Five', SPREADSHEET, TAB)
    assert 'PUT' not in methods


def anchor_variants():
    """Sidecar maps that are incomplete, ambiguous or stale for the base layout."""
    rows = base_rows()
    stale = sidecar_payload(rows)
    stale['anchors'][0]['fingerprint'] = row_fingerprint({c: 'khác' for c in COLUMNS})
    return {
        'missing_anchor_for_data_row': sidecar_payload(rows, anchor_rows=(4,), anchors=ANCHORS[:1]),
        'no_anchors_at_all': sidecar_payload(rows, anchor_rows=(), anchors=()),
        'duplicate_anchor_value': sidecar_payload(rows, anchors=(ANCHORS[0], ANCHORS[0])),
        'duplicate_row_entry': sidecar_payload(rows, anchor_rows=(4, 4), anchors=ANCHORS),
        'anchor_on_header_row': sidecar_payload(rows, anchor_rows=(3, 4), anchors=ANCHORS),
        'anchor_row_out_of_range': sidecar_payload(rows, anchor_rows=(4, 99), anchors=ANCHORS),
        'blank_anchor_id': sidecar_payload(rows, anchors=(ANCHORS[0], '   ')),
        'stale_row_fingerprint': stale,
        'other_spreadsheet': sidecar_payload(rows, spreadsheet_id='some-other-copy'),
        'other_tab': sidecar_payload(rows, tab='Tab khác'),
        'other_gid': sidecar_payload(rows, sheet_id=GID + 1),
        'absent_structure_fingerprint': sidecar_payload(rows, structure_fingerprint=None),
        'malformed_json': '{not json',
        'anchors_not_a_list': sidecar_payload(rows, anchors={'row': 4}),
        # Two IDs for one row: without a row guard this silently keeps one and
        # still satisfies the approved anchor count.
        'two_ids_for_one_row': sidecar_payload(
            rows, anchor_rows=(4, 4, 5), anchors=(*ANCHORS, 'anc-synthetic-3')),
    }


@pytest.mark.parametrize('variant', sorted(anchor_variants()))
def test_missing_or_ambiguous_anchor_fails_closed_without_write(tmp_path, variant):
    transport, methods = transport_for(tmp_path, base_rows(), sidecar=anchor_variants()[variant])
    with pytest.raises(BeeBotError) as error:
        transport.read_tab()
    assert error.value.code == 'SCHEDULE_SCOPE_INCOMPLETE'
    with pytest.raises((BeeBotError, TransportRejected)):
        transport.write_d(ANCHORS[0], 'Coach Five', SPREADSHEET, TAB)
    assert 'PUT' not in methods


def test_absent_sidecar_file_fails_closed_without_write(tmp_path):
    methods = []

    def handler(request):
        methods.append(request.method)
        return httpx.Response(200, json=grid_response(base_rows()))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = GoogleSheetsTransport(config(tmp_path / 'absent.json'),
                                      credentials=credentials(), http_client=client)
    with pytest.raises(BeeBotError) as error:
        transport.read_tab()
    assert error.value.code == 'SCHEDULE_SCOPE_INCOMPLETE'
    assert 'PUT' not in methods


def test_relative_sidecar_path_rejected_before_any_http(tmp_path):
    with pytest.raises(BeeBotError) as error:
        GoogleSheetsTransport(config('anchors.json'), credentials=credentials(),
                              http_client=httpx.Client(transport=httpx.MockTransport(
                                  lambda request: pytest.fail('unexpected HTTP'))))
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'


def test_anchor_count_drift_fails_closed(tmp_path):
    """The owner-approved anchor count is independent of what the sidecar lists."""
    transport, methods = transport_for(tmp_path, base_rows(), expected_anchor_count=3)
    with pytest.raises(BeeBotError) as error:
        transport.read_tab()
    assert error.value.code == 'SCHEDULE_SCOPE_INCOMPLETE'
    assert 'PUT' not in methods


def test_unapproved_anchor_is_never_written_even_when_sidecar_matches(tmp_path):
    transport, methods = transport_for(tmp_path, base_rows(), allowed_write_anchors=[ANCHORS[0]])
    assert [row['anchor'] for row in transport.read_tab()['rows'][3:]] == list(ANCHORS)
    with pytest.raises(TransportRejected):
        transport.write_d(ANCHORS[1], 'Coach Five', SPREADSHEET, TAB)
    assert methods == ['GET']


def test_read_only_guard_blocks_write_but_allows_read(tmp_path):
    transport, methods = transport_for(tmp_path, base_rows(), write_enabled=False)
    assert len(transport.read_tab()['rows']) == len(base_rows())
    with pytest.raises(TransportRejected):
        transport.write_d(ANCHORS[0], 'Coach Five', SPREADSHEET, TAB)
    assert methods == ['GET']


def test_d_and_j_header_labels_are_not_bound(tmp_path):
    """Documented consequence of excluding D/J: their header text is unbound.

    Column meaning is positional, the adapter classifies header rows itself, and
    relabelling cannot move coach data: a swap into another column changes that
    column's bound value and is covered by `coach_column_swapped_with_room`.
    """
    relabelled = base_rows()
    relabelled[2][3], relabelled[2][9] = 'Coach phụ trách', 'Tình trạng'
    transport, methods = transport_for(tmp_path, relabelled, sidecar=sidecar_payload(base_rows()))
    assert [row['anchor'] for row in transport.read_tab()['rows'][3:]] == list(ANCHORS)
    assert methods == ['GET']


@pytest.mark.parametrize('merges', [
    pytest.param([{'start': 4, 'end': 5, 'columns': ['C', 'D']}], id='coach_cell_merged'),
    pytest.param([{'start': 4, 'end': 5, 'columns': ['A']}], id='index_cell_merged'),
])
def test_merged_coach_or_index_cells_block_scope_even_with_matching_sidecar(tmp_path, merges):
    """One D cell shared by two positions cannot be written per position.

    The sidecar is regenerated for this exact layout, so only the coverage
    guard can refuse it.
    """
    rows = base_rows()
    if 'D' in merges[0]['columns']:
        rows[4][3] = None  # Covered by the merge, so the grid reports it blank.
    else:
        rows[4][0] = None
    transport, methods = transport_for(tmp_path, rows, merges=merges,
                                       sidecar=sidecar_payload(rows, merges))
    with pytest.raises(BeeBotError) as error:
        transport.read_tab()
    assert error.value.code == 'SCHEDULE_SCOPE_INCOMPLETE'
    with pytest.raises((BeeBotError, TransportRejected)):
        transport.write_d(ANCHORS[0], 'Coach Five', SPREADSHEET, TAB)
    assert 'PUT' not in methods
