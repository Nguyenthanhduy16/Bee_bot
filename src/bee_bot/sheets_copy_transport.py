"""Synthetic, offline Sheets-shaped transport for the Sheets adapter.

The boundary is deliberately narrow: read one tab (cells A-J, merges, row
anchors) and write ONE column-D cell addressed by a row anchor inside an explicit
(spreadsheet_id, tab), the way a REST URL and quoted range bind a real call.
Cell values are unformatted (numbers stay numbers); integer-valued STT strings
are accepted by the adapter, any other non-data populated row blocks writes. There is no
precondition on writes because real Google Sheets value writes have none; this
fake must not hand the adapter a compare-and-set guarantee Sheets cannot give.

Row anchors are a *synthetic* transport identity that moves with its row in
this fake. Whether real Sheets developer metadata or a hidden ID column behaves
the same way is an unverified pilot alternative, not a property claimed here.
No network, SDK or credentials are used. Source exports are never a backing
file: only a JSON synthetic copy is accepted.
"""
from copy import deepcopy
from datetime import date, timedelta
import json
import os
from pathlib import Path
import tempfile

from .errors import BeeBotError

COLUMNS = tuple('ABCDEFGHIJ')
FORBIDDEN_BACKING_DIR = ('.bee-bot', 'source')


class TransportTimeout(Exception):
    """The call outcome is unknown; the write may or may not have landed."""


class TransportRejected(Exception):
    """The call was clearly refused before any change was applied."""


class SyntheticSheetTransport:
    """JSON-persisted single-tab fake. Ops edits are test helpers, not adapter API.

    `script` is a per-write-call list of dicts with optional keys `before`
    (callable(transport)), `fault` ('timeout_before' | 'timeout_after' |
    'reject') and `after` (callable(transport)). It is in-memory only.
    """

    def __init__(self, path):
        self.path = Path(path)
        resolved = self.path.resolve()
        if resolved.suffix != '.json' or any(
                resolved.parts[i:i + 2] == FORBIDDEN_BACKING_DIR for i in range(len(resolved.parts))):
            raise BeeBotError('SHEETS_PROVENANCE_REJECTED',
                              'Chỉ dùng bản sao lịch giả lập dạng JSON; không dùng bản xuất nguồn.')
        self.script = []

    # -- persistence -------------------------------------------------------
    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data.get('rows'), list) or not isinstance(data.get('merges'), list):
                raise ValueError('invalid synthetic tab')
            return data
        except (OSError, ValueError, AttributeError) as exc:
            raise BeeBotError('SCHEDULE_UNAVAILABLE', 'Không đọc được bảng lịch giả lập.') from exc

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=self.path.parent, delete=False) as handle:
                temporary = handle.name
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    # -- adapter boundary --------------------------------------------------
    def provenance(self):
        return deepcopy(self._load().get('provenance') or {})

    def read_tab(self):
        data = self._load()
        try:
            rows = [{'row': index + 1, 'anchor': row.get('anchor'),
                     'cells': {c: row['cells'].get(c) for c in COLUMNS}}
                    for index, row in enumerate(data['rows'])]
        except (AttributeError, KeyError, TypeError) as exc:
            raise BeeBotError('SCHEDULE_MALFORMED', 'Dữ liệu bảng lịch không đúng cấu trúc; không ghi.') from exc
        return {'rows': rows, 'merges': deepcopy(data['merges'])}

    def write_d(self, anchor, value, spreadsheet_id, tab):
        """Write D for `anchor` in exactly (spreadsheet_id, tab), like a REST URL + quoted range."""
        step = self.script.pop(0) if self.script else {}
        if step.get('before'):
            step['before'](self)
        fault = step.get('fault')
        if fault == 'reject':
            raise TransportRejected('synthetic rejection')
        if fault == 'timeout_before':
            raise TransportTimeout('synthetic timeout before apply')
        data = self._load()
        provenance = data.get('provenance') or {}
        if (provenance.get('spreadsheet_id'), provenance.get('tab')) != (spreadsheet_id, tab):
            raise TransportRejected('bound workbook/tab not found')
        matches = [row for row in data['rows'] if anchor is not None and row.get('anchor') == anchor]
        if len(matches) != 1:
            raise TransportRejected('anchor not unique')
        matches[0]['cells']['D'] = value
        data.setdefault('write_log', []).append({'anchor': anchor, 'column': 'D', 'value': value})
        self._save(data)
        if step.get('after'):
            step['after'](self)
        if fault == 'timeout_after':
            raise TransportTimeout('synthetic timeout after apply')

    # -- test/ops helpers (simulate people editing the sheet directly) -----
    def write_log(self):
        return self._load().get('write_log', [])

    def row_of(self, anchor):
        rows = [r['row'] for r in self.read_tab()['rows'] if r['anchor'] == anchor]
        if len(rows) != 1:
            raise KeyError(anchor)
        return rows[0]

    def set_cell(self, row, column, value):
        data = self._load()
        data['rows'][row - 1]['cells'][column] = value
        self._save(data)

    def set_anchor(self, row, anchor):
        data = self._load()
        data['rows'][row - 1]['anchor'] = anchor
        self._save(data)

    def set_provenance(self, provenance):
        data = self._load()
        data['provenance'] = provenance
        self._save(data)

    def insert_row(self, row, cells=None, anchor=None):
        """Insert before `row`; merges shift or expand like a spreadsheet would."""
        data = self._load()
        data['rows'].insert(row - 1, {'anchor': anchor, 'cells': dict(cells or {})})
        for merge in data['merges']:
            if merge['start'] >= row:
                merge['start'] += 1
                merge['end'] += 1
            elif merge['end'] >= row:
                merge['end'] += 1
        self._save(data)

    def move_row(self, source, destination):
        """Move an unmerged row so it ends up at `destination` (fake limitation)."""
        data = self._load()
        if any(m['start'] <= source <= m['end'] for m in data['merges']):
            raise ValueError('synthetic fake only moves unmerged rows')
        moved = data['rows'].pop(source - 1)
        for merge in data['merges']:
            if merge['start'] > source:
                merge['start'] -= 1
                merge['end'] -= 1
        if any(m['start'] < destination <= m['end'] for m in data['merges']):
            raise ValueError('synthetic fake cannot move a row into a merge')
        data['rows'].insert(destination - 1, moved)
        for merge in data['merges']:
            if merge['start'] >= destination:
                merge['start'] += 1
                merge['end'] += 1
        self._save(data)


def synthetic_roster():
    """Explicit trusted people for the synthetic tab; never derived from D."""
    names = {'an': 'Synthetic An', 'binh': 'Synthetic Binh', 'chi': 'Synthetic Chi',
             'dung': 'Synthetic Dung', 'ops': 'Synthetic Ops'}
    return [{'person_id': key, 'display_name': name, 'role': 'ops' if key == 'ops' else 'labcoach',
             'active': True, 'sheet_names': [name]} for key, name in names.items()]


def write_synthetic_tab(path, first_day, spreadsheet_id='synthetic-bee-bot', tab='Lịch lab synthetic'):
    """Create a small synthetic tab shaped like the observed layout (A-J)."""
    first_day = first_day if isinstance(first_day, date) else date.fromisoformat(first_day)
    second_day = first_day + timedelta(days=1)

    def row(stt, b, c, d, f, g, j, anchor):
        return {'anchor': anchor, 'cells': {'A': stt, 'B': b, 'C': c, 'D': d, 'E': 'Synthetic Key',
                                            'F': f, 'G': g, 'H': 30, 'I': None, 'J': j}}

    header = {'anchor': None, 'cells': {'A': 'STT', 'B': 'Khóa', 'C': 'Session', 'D': 'Lab Coach',
                                         'E': 'Key Coach', 'F': 'Phòng', 'G': 'Buổi', 'H': 'Sức chứa',
                                         'I': 'Ghi chú', 'J': 'Trạng thái'}}
    rows = [
        {'anchor': None, 'cells': {'A': 'LỊCH LAB COACH — DỮ LIỆU GIẢ LẬP'}},
        {'anchor': None, 'cells': {'A': f'Thứ 2 - {first_day:%d/%m/%Y}'}},
        header,
        row(1, 'Track 1', 'CS1', 'Synthetic An', 'H210', 'Sáng', 'Rảnh', 'anc-001'),
        # Rows 5 shares a merged B/C/F/G block with row 4 (second position, same class).
        row(2, None, None, 'Synthetic Chi', None, None, 'Chưa cập nhật', 'anc-002'),
        row(3, 'Track 2', 'CS2', 'Synthetic Binh', 'H205', 'Chiều', 'Bận', 'anc-003'),
        {'anchor': None, 'cells': {'A': f'Thứ 3 - {second_day:%d/%m/%Y}'}},
        header,
        row(1, 'Track 1', 'CS3', 'Synthetic Chi', 'H210', 'Sáng', 'Rảnh', 'anc-004'),
        row(2, 'Track 3', 'CS4', 'Synthetic Dung', 'H301', 'Sáng', 'Rảnh', 'anc-005'),
        row(3, 'Track 3', 'CS4', None, 'H301', 'Sáng', None, 'anc-006'),
    ]
    data = {'provenance': {'kind': 'synthetic', 'spreadsheet_id': spreadsheet_id, 'tab': tab,
                           'copy_of': None, 'contains_real_data': False},
            'rows': rows,
            'merges': [{'start': 4, 'end': 5, 'columns': ['B', 'C', 'F', 'G']}],
            'write_log': []}
    transport = SyntheticSheetTransport(path)
    transport._save(data)
    return transport
