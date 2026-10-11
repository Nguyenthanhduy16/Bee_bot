#!/usr/bin/env python3
"""Bounded, admin-only Google Sheets REST probe: one D cell on the owner-authorized test copy.

Not wired to the bot or the default schedule. Modes:
  (default) preflight  - validate private config + credential presence; NO network.
  --read-only          - one bounded GET (valueRenderOption=FORMULA) + preconditions; no write.
  --execute            - GET, PUT one D cell (valueInputOption=RAW), GET readback; optional
                         guarded restore of the original D, then GET to confirm.
The access token is read only from BEE_BOT_SHEETS_ACCESS_TOKEN and never logged or saved.
Public output is redacted: no token, request URLs, spreadsheet ID, tab name or cell values.
Raw before/after reads are private evidence (0600). Google Sheets has no compare-and-set:
an edit between the last GET and the PUT can be overwritten undetected; this probe does
not and cannot prevent that. A single-cell probe verifies neither stable anchors nor roster.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote

import httpx

TOKEN_ENV = 'BEE_BOT_SHEETS_ACCESS_TOKEN'
API = 'https://sheets.googleapis.com/v4/spreadsheets'
CONFIRMATION = 'owner_confirmed_test_copy'
DEFAULT_RANGE = 'A1:T1000'
MAX_ROWS = 5000
PLACEHOLDER_HINTS = ('placeholder', 'changeme', 'replace', 'your', 'token', 'xxx', '<', '>', '...')


class ProbeStop(Exception):
    def __init__(self, state, code):
        super().__init__(code)
        self.state, self.code = state, code


def column_index(letters):
    value = 0
    for char in letters:
        value = value * 26 + ord(char) - 64
    return value - 1


def column_letters(index):
    letters = ''
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def cell_ref(ref):
    match = re.fullmatch(r'([A-Z]{1,2})([1-9]\d{0,4})', ref or '')
    if not match:
        raise ProbeStop('precondition_failed', 'INVALID_CELL_REF')
    return match[1], int(match[2])


def token_state(token):
    token = (token or '').strip()
    if not token:
        return 'missing'
    if len(token) < 20 or any(hint in token.lower() for hint in PLACEHOLDER_HINTS) or token.startswith('$'):
        return 'placeholder'
    return 'present'


def load_config(path):
    """Validate the private config; every failure is a clean pre-network stop."""
    try:
        sheets = json.loads(Path(path).read_text(encoding='utf-8'))['sheets']
        probe = sheets['test_probe']
    except (OSError, ValueError, KeyError, TypeError):
        raise ProbeStop('precondition_failed', 'CONFIG_UNREADABLE')
    spreadsheet_id = sheets.get('candidate_copy_id')
    if not isinstance(spreadsheet_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{20,}', spreadsheet_id):
        raise ProbeStop('precondition_failed', 'COPY_ID_INVALID')
    if spreadsheet_id in set(sheets.get('known_source_ids') or []):
        raise ProbeStop('precondition_failed', 'SOURCE_ID_DENIED')  # denylist always wins
    if sheets.get('verification_status') != CONFIRMATION:
        raise ProbeStop('precondition_failed', 'OWNER_CONFIRMATION_MISSING')
    tab = probe.get('tab')
    if not tab or tab not in (sheets.get('allowed_tabs') or []):
        raise ProbeStop('precondition_failed', 'TAB_NOT_ALLOWED')
    column, row = cell_ref(probe.get('cell'))
    if column != 'D' or probe['cell'] not in (sheets.get('allowed_cells') or []):
        raise ProbeStop('precondition_failed', 'CELL_NOT_ALLOWED')
    if probe.get('guard_cell') != f'J{row}':
        raise ProbeStop('precondition_failed', 'GUARD_NOT_SAME_ROW_J')
    for field in ('expected_d', 'expected_j', 'test_value'):
        if not isinstance(probe.get(field), str):
            raise ProbeStop('precondition_failed', 'EXPECTED_SNAPSHOT_MISSING')
    if not probe['expected_d'].strip() or not probe['test_value'].strip():
        raise ProbeStop('precondition_failed', 'EXPECTED_SNAPSHOT_MISSING')
    if probe['test_value'] == probe['expected_d'] or probe['test_value'].startswith('='):
        raise ProbeStop('precondition_failed', 'TEST_VALUE_INVALID')
    if not isinstance(probe.get('restore_original'), bool):
        raise ProbeStop('precondition_failed', 'RESTORE_FLAG_INVALID')
    bounded = re.fullmatch(r'A1:([A-Z]{1,2})([1-9]\d{0,4})', probe.get('read_range', DEFAULT_RANGE))
    if not bounded or column_index(bounded[1]) < column_index('J') or not row <= int(bounded[2]) <= MAX_ROWS:
        raise ProbeStop('precondition_failed', 'READ_RANGE_INVALID')
    evidence = Path(probe.get('evidence_dir') or '').resolve()
    parts = evidence.parts
    if not probe.get('evidence_dir') or '.bee-bot' not in parts or any(
            parts[i:i + 2] == ('.bee-bot', 'source') for i in range(len(parts))):
        raise ProbeStop('precondition_failed', 'EVIDENCE_DIR_NOT_PRIVATE')
    return {'spreadsheet_id': spreadsheet_id, 'tab': tab, 'row': row, 'cell': probe['cell'],
            'guard': probe['guard_cell'], 'expected_d': probe['expected_d'],
            'expected_j': probe['expected_j'], 'test_value': probe['test_value'],
            'restore': probe['restore_original'], 'write_enabled': sheets.get('write_enabled') is True,
            'read_range': probe.get('read_range', DEFAULT_RANGE), 'evidence_dir': evidence,
            'context': {k: probe.get(k) for k in ('date', 'starts_at', 'ends_at')}}


def a1(tab, cells):
    return "'" + tab.replace("'", "''") + "'!" + cells


class Probe:
    def __init__(self, config, client, token, stamp):
        self.config, self.client, self.stamp = config, client, stamp
        self._headers = {'Authorization': 'Bearer ' + token}
        self.http = []  # [(method, status|exception class)] only
        self.evidence = []

    def _url(self, cells):
        return f"{API}/{self.config['spreadsheet_id']}/values/{quote(a1(self.config['tab'], cells), safe='')}"

    def private(self, name, payload):
        directory = self.config['evidence_dir']
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = directory / f'probe-{self.stamp}-{name}.json'
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        self.evidence.append(path.name)

    def get_grid(self, label):
        try:
            response = self.client.get(self._url(self.config['read_range']), headers=self._headers,
                                       params={'valueRenderOption': 'FORMULA', 'majorDimension': 'ROWS'})
        except httpx.HTTPError as exc:
            self.http.append(('GET', type(exc).__name__))
            raise ProbeStop('read_failed' if label == 'before' else 'write_uncertain', 'GET_TRANSPORT_ERROR')
        self.http.append(('GET', response.status_code))
        if response.status_code != 200:
            raise ProbeStop('read_failed' if label == 'before' else 'write_uncertain', f'GET_HTTP_{response.status_code}')
        try:
            values = response.json().get('values', [])
        except ValueError:
            raise ProbeStop('read_failed' if label == 'before' else 'write_uncertain', 'GET_BODY_INVALID')
        self.private(label, {'range': self.config['read_range'], 'value_render_option': 'FORMULA',
                             'values': values})
        return {(r, c): v for r, row in enumerate(values, 1) for c, v in enumerate(row)
                if v not in ('', None)}

    def put_d(self, value):
        """Single unconditional cell write. A non-4xx failure leaves the outcome uncertain."""
        cells = self.config['cell']
        body = {'range': a1(self.config['tab'], cells), 'majorDimension': 'ROWS', 'values': [[value]]}
        try:
            response = self.client.put(self._url(cells), headers=self._headers, json=body,
                                       params={'valueInputOption': 'RAW'})
        except httpx.HTTPError as exc:
            self.http.append(('PUT', type(exc).__name__))
            raise ProbeStop('write_uncertain', 'PUT_TRANSPORT_ERROR')
        self.http.append(('PUT', response.status_code))
        if 400 <= response.status_code < 500:
            raise ProbeStop('write_rejected', f'PUT_HTTP_{response.status_code}')
        if response.status_code != 200:
            raise ProbeStop('write_uncertain', f'PUT_HTTP_{response.status_code}')
        try:
            updated = response.json().get('updatedCells')
        except ValueError:
            updated = None
        if updated != 1:
            raise ProbeStop('write_uncertain', 'PUT_UPDATED_CELLS_NOT_ONE')


def diff(before, after):
    return {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}


def run(config_path, mode='preflight', client=None, environ=None, stamp=None):
    environ = os.environ if environ is None else environ
    stamp = stamp or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    summary = {'mode': mode, 'state': None, 'code': None, 'http': [], 'requests': {'GET': 0, 'PUT': 0},
               'changed_cells': [], 'guard_unchanged': None, 'evidence_files': [],
               'compare_and_set': False, 'anchors_or_roster_verified': False}
    probe = None
    try:
        config = load_config(config_path)
        summary['context'] = config['context']
        credential = token_state(environ.get(TOKEN_ENV))
        summary['credential'] = credential
        if mode == 'execute' and not config['write_enabled']:
            raise ProbeStop('precondition_failed', 'WRITE_DISABLED')
        if credential != 'present':
            raise ProbeStop('missing_credential', 'TOKEN_' + credential.upper())
        if mode == 'preflight':
            summary.update(state='preflight_ok', code='NO_NETWORK_USED')
            return summary
        row, d_col, j_col = config['row'], column_index('D'), column_index('J')
        target, guard = (row, d_col), (row, j_col)
        probe = Probe(config, client, environ[TOKEN_ENV].strip(), stamp)
        before = probe.get_grid('before')
        current_d, current_j = before.get(target, ''), before.get(guard, '')
        if any(isinstance(v, str) and v.startswith('=') for v in (current_d, current_j)):
            raise ProbeStop('precondition_failed', 'FORMULA_TARGET')
        if current_d != config['expected_d'] or current_j != config['expected_j']:
            raise ProbeStop('precondition_failed', 'EXPECTED_SNAPSHOT_MISMATCH')
        if mode == 'read_only':
            summary.update(state='read_ok', code='PRECONDITIONS_MATCH')
            return summary
        # No compare-and-set exists: an edit after this GET and before the PUT is not detectable.
        probe.put_d(config['test_value'])
        after = probe.get_grid('after-write')
        changes = diff(before, after)
        summary['guard_unchanged'] = after.get(guard, '') == current_j
        probe.private('scoped-changes', {'cells': [{'row': r, 'col': c, 'before': before.get((r, c)),
                                                    'after': after.get((r, c))} for r, c in sorted(changes)]})
        summary['changed_cells'] = sorted(column_letters(c) + str(r) for r, c in changes)
        if changes - {target}:
            raise ProbeStop('unexpected_concurrent_diff', 'OTHER_CELLS_CHANGED')
        if after.get(target) != config['test_value']:
            raise ProbeStop('write_uncertain', 'READBACK_MISMATCH')
        if not config['restore']:
            summary.update(state='verified', code='ONE_D_CELL_WRITTEN_J_UNCHANGED')
            return summary
        try:  # Restore only after a verified, isolated test write; never retried.
            probe.put_d(current_d)
            restored = probe.get_grid('after-restore')
        except ProbeStop as stop:
            raise ProbeStop('restore_uncertain' if stop.state == 'write_uncertain' else 'restore_rejected', stop.code)
        if diff(before, restored):
            raise ProbeStop('restore_unverified', 'RANGE_NOT_EQUAL_TO_BEFORE')
        summary.update(state='restored', code='ORIGINAL_RANGE_CONFIRMED')
        return summary
    except ProbeStop as stop:
        summary.update(state=stop.state, code=stop.code)
        return summary
    finally:
        if probe:
            summary['http'] = [f'{method}:{status}' for method, status in probe.http]
            for method in ('GET', 'PUT'):
                summary['requests'][method] = sum(m == method for m, _ in probe.http)
            try:
                probe.private('summary', summary)
            except OSError:
                pass
            summary['evidence_files'] = list(probe.evidence)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Bounded one-D-cell Sheets copy probe (admin only).')
    parser.add_argument('config', help='Private pilot inputs JSON (outside Git)')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--read-only', action='store_true', help='Authenticated GET + preconditions, no write')
    group.add_argument('--execute', action='store_true', help='Perform the guarded one-cell write')
    args = parser.parse_args(argv)
    mode = 'execute' if args.execute else 'read_only' if args.read_only else 'preflight'
    if mode == 'preflight':
        summary = run(args.config, mode)
    else:
        with httpx.Client(timeout=httpx.Timeout(20.0), follow_redirects=False) as client:
            summary = run(args.config, mode, client=client)
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0 if summary['state'] in {'preflight_ok', 'read_ok', 'verified', 'restored'} else 2


if __name__ == '__main__':
    sys.exit(main())
