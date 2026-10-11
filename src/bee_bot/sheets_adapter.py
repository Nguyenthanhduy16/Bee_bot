"""Offline Sheets-shaped schedule adapter for BeeBotService (synthetic data only).

Implements list_people / list_assignments / get_assignment / apply_updates over a
narrow transport (see sheets_copy_transport). Guarantees and non-guarantees:

- D (Lab Coach) is authoritative; only D cells are ever written, J never.
- Assignment IDs come from the transport's row anchor, not row/STT/name.
- People are an explicit trusted roster; names in D never create identities.
- Every non-blank row is classified (title/preamble, day header, column header,
  note, data). Anything populated that is not a clean assignment, and every
  date-like text that is not a recognised day header, blocks writable scope.
- Workbook identity and trusted copy confirmation are pinned at construction
  and re-checked on every read and before every individual D write; the transport
  call is additionally bound to (spreadsheet_id, tab).
- Before EACH D write the tab is re-read and the remaining targets, scope and the
  resulting recipient overlaps are re-validated. Readback re-validates confirmed
  details, scope and overlaps. Earlier writes are never rolled back.
- There is NO compare-and-set: an edit landing between the last read and a
  write is overwritten undetected. Reads before/after narrow, not close, that
  window. `revision` is a content hash, so A->B->A edits are invisible.
- Uncertain outcomes raise WRITE_UNCERTAIN; nothing is retried or rolled back.
Not production-ready; real Sheets behaviour is unverified.
"""
from datetime import datetime, time
from hashlib import sha256
import json
import re

from .errors import BeeBotError
from .service import SIGNATURE, overlaps
from .sheets_copy_transport import COLUMNS, TransportRejected
from .sheets_import import ZONE, _date_header, clean, digest, normalized

MERGED = {'B', 'C', 'E', 'F', 'G', 'H'}
CONTENT = tuple('BCDEFGHIJ')
HEADER_FIELDS = {'A': 'stt', 'B': 'khóa', 'C': 'session', 'D': 'lab coach', 'F': 'phòng', 'G': 'buổi'}
TIMES = {'sáng': (9, 13), 'chiều': (14, 18)}
SCOPE_BLOCKING = {'MISSING_ANCHOR', 'DUPLICATE_ANCHOR', 'INVALID_CANONICAL_ROW', 'UNKNOWN_ROSTER_NAME',
                  'INVALID_DATE_HEADER', 'UNCLASSIFIED_ROW', 'MERGED_KEY_CELL'}
DATE_LIKE = re.compile(r'\d{1,2}\s*[/.\-]\s*\d{1,2}')
WEEKDAY_LIKE = re.compile(r'^(?:thứ|thu|chủ\s*nhật|chu\s*nhat|ngày|ngay|cn\b|t\s*[2-7]\b|mon|tue|wed|fri|sat|sun)',
                          re.IGNORECASE)
STT = re.compile(r'[1-9]\d*(?:\.0+)?')
UNCERTAIN_MESSAGE = 'Kết quả ghi chưa chắc chắn; cần đọc lại và đối chiếu mọi ca liên quan.'


def _ids(values):
    return frozenset(clean(v) for v in values if clean(v))


def check_provenance(provenance, allowed_spreadsheet_ids, denied_source_ids=frozenset()):
    """Fail closed unless the backing tab is synthetic or an allowlisted test copy.

    Owner confirmation must come from trusted configuration, never model input.
    It may authorize a copy whose original source ID is unknown; no source ID is
    invented. Legacy copy_of provenance remains supported for offline callers.
    IDs are normalised and a denied destination always overrides approval.
    """
    allowed, denied = _ids(allowed_spreadsheet_ids), _ids(denied_source_ids)
    provenance = provenance or {}
    kind, spreadsheet_id = provenance.get('kind'), provenance.get('spreadsheet_id')
    ok = (isinstance(spreadsheet_id, str) and bool(spreadsheet_id) and spreadsheet_id == clean(spreadsheet_id)
          and spreadsheet_id in allowed and spreadsheet_id not in denied and bool(provenance.get('tab')))
    if 'sheet_id' in provenance:
        sheet_id = provenance['sheet_id']
        ok = ok and isinstance(sheet_id, int) and not isinstance(sheet_id, bool) and sheet_id >= 0
    if kind == 'synthetic':
        ok = ok and provenance.get('contains_real_data') is False
    elif kind == 'test_copy':
        copy_of = clean(provenance.get('copy_of'))
        confirmed = provenance.get('owner_confirmed_copy') is True
        legacy_copy = bool(copy_of) and copy_of not in allowed
        ok = ok and copy_of != spreadsheet_id and (confirmed or legacy_copy)
    else:
        ok = False
    if not ok:
        raise BeeBotError('SHEETS_PROVENANCE_REJECTED',
                          'Nguồn lịch không phải bản giả lập/bản sao thử được phép; không ghi.')
    return provenance


def _stt(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value > 0 and float(value).is_integer()
    return isinstance(value, str) and STT.fullmatch(clean(value)) is not None


def _malformed():
    return BeeBotError('SCHEDULE_MALFORMED', 'Dữ liệu bảng lịch không đúng cấu trúc; không ghi.')


def _validated_tab(tab):
    """Controlled error for structurally malformed transport output."""
    if not isinstance(tab, dict) or not isinstance(tab.get('rows'), list) or not isinstance(tab.get('merges'), list):
        raise _malformed()
    rows = tab['rows']
    for index, record in enumerate(rows, 1):
        if (not isinstance(record, dict) or record.get('row') != index or not isinstance(record.get('cells'), dict)
                or not (record.get('anchor') is None or (isinstance(record['anchor'], str) and record['anchor']))):
            raise _malformed()
    for merge in tab['merges']:
        if (not isinstance(merge, dict) or not all(isinstance(merge.get(k), int) and not isinstance(merge.get(k), bool)
                                                   for k in ('start', 'end'))
                or not 1 <= merge['start'] <= merge['end'] <= len(rows)
                or not isinstance(merge.get('columns'), list) or not merge['columns']
                or not all(isinstance(column, str) and column in COLUMNS
                           for column in merge['columns'])):
            raise _malformed()
    return tab


class SheetsScheduleAdapter:
    def __init__(self, transport, people, allowed_spreadsheet_ids, denied_source_ids=()):
        self.transport = transport
        self.allowed = _ids(allowed_spreadsheet_ids)
        self.denied = _ids(denied_source_ids)
        self.provenance = check_provenance(transport.provenance(), self.allowed, self.denied)
        self._pin = self._identity(self.provenance)
        self._people, self._by_name, self._write_name = [], {}, {}
        for person in people:
            pid = person['person_id']
            if pid in self._write_name:
                raise BeeBotError('ROSTER_AMBIGUOUS', 'Danh sách người dùng có mã trùng.')
            names = [clean(n) for n in person.get('sheet_names', []) if clean(n)]
            for name in names:
                if normalized(name) in self._by_name:
                    raise BeeBotError('ROSTER_AMBIGUOUS', 'Hai người dùng trùng tên trên Sheets; cần mã phân biệt.')
                self._by_name[normalized(name)] = pid
            self._write_name[pid] = names[0] if names else None
            self._people.append({'person_id': pid, 'display_name': person['display_name'],
                                 'role': person['role'], 'active': bool(person.get('active'))})

    def close(self):
        close = getattr(self.transport, 'close', None)
        if close is not None:
            close()

    @staticmethod
    def _identity(provenance):
        return tuple(provenance.get(k) for k in (
            'kind', 'spreadsheet_id', 'tab', 'copy_of', 'owner_confirmed_copy', 'sheet_id'))

    # -- reading -----------------------------------------------------------
    def _check(self):
        provenance = check_provenance(self.transport.provenance(), self.allowed, self.denied)
        if self._identity(provenance) != self._pin:
            raise BeeBotError('SHEETS_PROVENANCE_REJECTED', 'Bảng lịch đã đổi workbook/tab so với lúc khởi tạo; không ghi.')
        return provenance

    def _snapshot(self):
        """Parse one fresh read. Returns (assignments by id, anchors by id, diagnostics)."""
        provenance = self._check()
        tab = _validated_tab(self.transport.read_tab())
        cells = {r['row']: r['cells'] for r in tab['rows']}
        anchors, diagnostics = {}, []
        for merge in tab['merges']:
            if {'A', 'D'} & set(merge['columns']) and merge['end'] > merge['start']:
                diagnostics.extend({'code': 'MERGED_KEY_CELL', 'row': row}
                                   for row in range(merge['start'], merge['end'] + 1))
            for column in set(merge['columns']) & MERGED:
                for row in range(merge['start'], merge['end'] + 1):
                    anchors[(row, column)] = merge['start']
        found, seen_header = [], False
        day, day_row = None, None
        for record in tab['rows']:
            row, raw = record['row'], record['cells']
            a = raw.get('A')
            populated = any(clean(raw.get(c)) for c in CONTENT)
            if not _stt(a):
                header = _date_header(a)
                text = clean(a)
                if header and not populated:
                    day, day_row, seen_header = header, row, True
                elif header or (text and (DATE_LIKE.search(text) or WEEKDAY_LIKE.match(text))):
                    # Unrecognised day header: never let the previous day carry over.
                    if seen_header or populated:
                        day, day_row = None, row
                        diagnostics.append({'code': 'INVALID_DATE_HEADER', 'row': row})
                elif populated and not (record['anchor'] is None and all(
                        normalized(raw.get(column)) == label for column, label in HEADER_FIELDS.items())):
                    diagnostics.append({'code': 'UNCLASSIFIED_ROW', 'row': row})
                continue

            def value(column):
                start = anchors.get((row, column))
                if start is not None:
                    return None if day_row and start <= day_row else cells[start].get(column)
                return raw.get(column)

            track, session, room = clean(value('B')), clean(value('C')), clean(value('F'))
            daypart = normalized(value('G'))
            if day is None or not (track and session and room) or daypart not in TIMES:
                diagnostics.append({'code': 'INVALID_CANONICAL_ROW', 'row': row})
                continue
            if not record['anchor']:
                diagnostics.append({'code': 'MISSING_ANCHOR', 'row': row})
                continue
            name = clean(raw.get('D'))
            coach_id = self._by_name.get(normalized(name)) if name else None
            if name and coach_id is None:
                # Never surface the raw name in diagnostics (PII stays in the sheet).
                diagnostics.append({'code': 'UNKNOWN_ROSTER_NAME', 'row': row})
                continue
            start_h, end_h = TIMES[daypart]
            class_key = (provenance['tab'], day.isoformat(), normalized(track), normalized(session),
                         normalized(room), daypart)
            revision_basis = [day.isoformat(), track, session, name, room, daypart]
            found.append((record['anchor'], {
                'assignment_id': digest('sheet_assignment_', provenance['spreadsheet_id'],
                                        provenance['tab'], record['anchor']),
                'shift_id': digest('sheet_shift_', provenance['spreadsheet_id'], *class_key),
                'coach_id': coach_id,
                'starts_at': datetime.combine(day, time(start_h), ZONE).isoformat(),
                'ends_at': datetime.combine(day, time(end_h), ZONE).isoformat(),
                'room': room, 'site': 'unverified', 'class_name': f'{track} / {session}',
                'track': track, 'session': session, 'daypart': clean(value('G')),
                'key_coach': clean(value('E')), 'j': raw.get('J'),
                # Content hash, not a version counter: J excluded; ABA is invisible.
                'revision': int(sha256(json.dumps(revision_basis, ensure_ascii=False).encode())
                                .hexdigest()[:15], 16),
                'source_locator': {'tab': provenance['tab'], 'row': row, 'assignment_cell': f'D{row}'},
                'provenance': {'kind': provenance['kind'], 'id_scope': 'synthetic_row_anchor'},
            }))
        counts = {}
        for anchor, _ in found:
            counts[anchor] = counts.get(anchor, 0) + 1
        assignments, anchor_of = {}, {}
        for anchor, assignment in found:
            if counts[anchor] > 1:
                diagnostics.append({'code': 'DUPLICATE_ANCHOR', 'row': assignment['source_locator']['row']})
                continue
            assignments[assignment['assignment_id']] = assignment
            anchor_of[assignment['assignment_id']] = anchor
        return assignments, anchor_of, diagnostics

    def coverage(self):
        """Explicit writable coverage for this single tab; diagnostics carry rows, not names."""
        assignments, _, diagnostics = self._snapshot()
        return {'scope': 'single_tab', 'tab': self.provenance['tab'],
                'assignments': len(assignments), 'diagnostics': diagnostics,
                'writable': not any(d['code'] in SCOPE_BLOCKING for d in diagnostics),
                'compare_and_set': False, 'production_ready': False}

    def list_people(self):
        return [dict(person) for person in self._people]

    def list_assignments(self):
        return list(self._snapshot()[0].values())

    def get_assignment(self, assignment_id):
        assignment = self._snapshot()[0].get(assignment_id)
        if assignment is None:
            raise BeeBotError('ASSIGNMENT_NOT_FOUND', 'Không tìm thấy ca được yêu cầu.')
        return assignment

    # -- writing -----------------------------------------------------------
    def _validate(self, snapshot, updates, expected, written):
        """Raise unless scope is clean, every target still matches its confirmed details
        (written targets must already show the recipient) and no recipient overlaps."""
        assignments, _, diagnostics = snapshot
        if any(d['code'] in SCOPE_BLOCKING for d in diagnostics):
            raise BeeBotError('SCHEDULE_SCOPE_INCOMPLETE',
                              'Bảng lịch có dòng chưa xác định được; không ghi khi phạm vi chưa đầy đủ.')
        people = {p['person_id']: p for p in self._people}
        for assignment_id, coach_id in updates.items():
            current, original = assignments.get(assignment_id), expected.get(assignment_id)
            done = assignment_id in written
            fields = [k for k in SIGNATURE if not done or k not in {'coach_id', 'revision'}]
            if current is None or original is None or any(current.get(k) != original.get(k) for k in fields) \
                    or (done and current.get('coach_id') != coach_id):
                raise BeeBotError('SCHEDULE_CHANGED', 'Lịch đã thay đổi; dừng cập nhật để đối chiếu lại.')
            person = people.get(coach_id)
            if not person or not person['active'] or person['role'] != 'labcoach' or not self._write_name[coach_id]:
                raise BeeBotError('INVALID_SUBSTITUTE', 'Người nhận ca không phải labcoach đang hoạt động.')
        resulting = [{**a, 'coach_id': updates.get(i, a['coach_id'])} for i, a in assignments.items()]
        for assignment_id, coach_id in updates.items():
            desired = assignments[assignment_id]
            if any(other['assignment_id'] != assignment_id and other['coach_id'] == coach_id
                   and overlaps(desired, other) for other in resulting):
                raise BeeBotError('SCHEDULE_CONFLICT', 'Người nhận đã có ca trùng giờ trên bảng này.')

    def verify_applied(self, updates, expected):
        """Read-only check for reconciliation: True only if all planned D values are present,
        confirmed details unchanged, scope clean and no recipient overlap. Never writes."""
        try:
            self._validate(self._snapshot(), updates, expected, set(updates))
            return True
        except Exception:
            return False

    def apply_updates(self, updates, expected):
        written = []
        for assignment_id, coach_id in updates.items():
            try:
                # Fresh read + full re-validation (scope, identity, remaining targets, overlaps)
                # before EACH individual D write; earlier writes must still hold.
                snapshot = self._snapshot()
                self._validate(snapshot, updates, expected, set(written))
                anchor = snapshot[1][assignment_id]
                self._check()
                self.transport.write_d(anchor, self._write_name[coach_id],
                                       self._pin[1], self._pin[2])
            except (BeeBotError, TransportRejected) as exc:
                if written:
                    raise BeeBotError('WRITE_UNCERTAIN', 'Chỉ ghi được một phần; cần đối chiếu mọi ca liên quan.') from exc
                code = exc.code if isinstance(exc, BeeBotError) else 'WRITE_FAILED'
                raise BeeBotError(code, 'Ghi lịch bị từ chối; dữ liệu chưa được thay đổi.') from exc
            except Exception as exc:
                raise BeeBotError('WRITE_UNCERTAIN', UNCERTAIN_MESSAGE) from exc
            written.append(assignment_id)
        if not self.verify_applied(updates, expected):
            raise BeeBotError('WRITE_UNCERTAIN', 'Đọc lại sau ghi không khớp hoặc phát sinh trùng lịch; cần đối chiếu.')


def run_offline_demo(state_dir, first_day=None):
    """Synthetic end-to-end BeeBotService run: replacement, partial swap, reopen, reconcile."""
    from datetime import timedelta
    from pathlib import Path
    from .service import BeeBotService
    from .sheets_copy_transport import SyntheticSheetTransport, synthetic_roster, write_synthetic_tab

    state = Path(state_dir)
    now = datetime(2026, 10, 10, 8, tzinfo=ZONE)
    first_day = first_day or (now + timedelta(days=3)).date()
    sheet, db = state / 'synthetic_tab.json', state / 'state.db'
    transport = write_synthetic_tab(sheet, first_day)
    allowed = {'synthetic-bee-bot'}

    def open_service():
        adapter = SheetsScheduleAdapter(SyntheticSheetTransport(sheet), synthetic_roster(), allowed)
        return adapter, BeeBotService(db, adapter, clock=lambda: now)

    def invitation(service, actor, request_id):
        return next(i['invitation_id'] for i in service.get_my_invitations(actor) if i['request_id'] == request_id)

    adapter, service = open_service()
    ids = {a['source_locator']['row']: a['assignment_id'] for a in adapter.list_assignments()}
    # Replacement: Chi's day-2 morning (row 9) to Binh.
    replacement = service.create_change_request('chi', 'replacement', ids[9], 'demo-1',
                                                substitute_id='binh', sender_confirmed=True)
    replacement = service.respond_to_invitation('binh', invitation(service, 'binh', replacement['id']),
                                                True, True, 'demo-2')
    # Swap An (row 4) with Dung (row 10); second D write times out before applying.
    swap = service.create_change_request('an', 'swap', ids[4], 'demo-3', target_assignment_id=ids[10],
                                         sender_confirmed=True, sender_no_other_busy=True)
    adapter.transport.script = [{}, {'fault': 'timeout_before'}]
    swap = service.respond_to_invitation('dung', invitation(service, 'dung', swap['id']), True, True, 'demo-4')
    partial_status = swap['status']
    service.close()

    adapter, service = open_service()  # Reopen: new process-equivalent objects, same files.
    maintenance = service.run_maintenance('ops')
    after_restart = service.get_request_status('ops', swap['id'])['status']
    writes_after_restart = len(transport.write_log())
    # Ops fixes the missing cell by hand on the synthetic copy, then reconciles.
    transport.set_cell(transport.row_of('anc-005'), 'D', 'Synthetic An')
    reconciled = service.reconcile_request('ops', swap['id'])
    service.close()
    return {'replacement_status': replacement['status'], 'swap_status_after_partial': partial_status,
            'swap_status_after_restart_maintenance': after_restart,
            'maintenance_reconciled': maintenance['reconciled_requests'],
            'bot_writes_after_restart': writes_after_restart,
            'bot_writes_final': len(transport.write_log()),
            'swap_status_after_ops_fix': reconciled['status'],
            'j_column': [r['cells']['J'] for r in transport.read_tab()['rows'] if r['anchor']],
            'simulated': True, 'compare_and_set': False}


def main(argv=None):
    import argparse
    import sys
    parser = argparse.ArgumentParser(description='Synthetic offline Sheets adapter demo (no network).')
    parser.add_argument('state_dir', help='Empty directory for the synthetic tab and SQLite state')
    args = parser.parse_args(argv)
    json.dump(run_offline_demo(args.state_dir), sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == '__main__':
    main()
