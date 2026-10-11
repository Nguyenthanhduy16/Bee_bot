"""Sheets copy probe: fully mocked with httpx.MockTransport; no network request is ever sent."""
import importlib.util
import json
import os
from pathlib import Path
import stat
from urllib.parse import unquote

import httpx
import pytest

spec = importlib.util.spec_from_file_location('sheets_copy_probe', Path(__file__).parents[1] / 'scripts/sheets_copy_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

COPY_ID = 'synthCopyId_0123456789abcdefXYZ'
TAB = "Lịch lab synth's"
TOKEN = 'ya29.synthetic-access-credential-0123456789'
D, J, TEST = 'Synthetic Coach', 'Rảnh', 'BEE BOT PROBE (synthetic)'


def config(tmp_path, **changes):
    sheets = {
        'candidate_copy_id': COPY_ID, 'known_source_ids': ['synthSourceId_0123456789abcdef'],
        'verification_status': 'owner_confirmed_test_copy', 'write_enabled': True,
        'allowed_tabs': [TAB], 'allowed_cells': ['D5'],
        'test_probe': {'tab': TAB, 'cell': 'D5', 'guard_cell': 'J5', 'date': '2026-10-12',
                       'starts_at': '09:00', 'ends_at': '13:00', 'expected_d': D, 'expected_j': J,
                       'test_value': TEST, 'restore_original': True,
                       'evidence_dir': str(tmp_path / '.bee-bot' / 'probe-evidence')}}
    for key, value in changes.items():
        target, field = (sheets['test_probe'], key[6:]) if key.startswith('probe_') else (sheets, key)
        if value is DELETE:
            target.pop(field, None)
        else:
            target[field] = value
    path = tmp_path / '.bee-bot' / 'pilot-inputs.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'sheets': sheets}), encoding='utf-8')
    return path


DELETE = object()


class FakeSheets:
    """Minimal values.get/values.update emulator. No CAS, like the real API."""

    def __init__(self):
        self.grid = [['STT', 'Khóa', 'Session', 'Lab Coach'] + [''] * 5 + ['Trạng thái'],
                     ['Thứ 2 - 12/10/2026']] + [[i, 'Track 1', 'CS1', f'Coach {i}', 'Key', 'H210', 'Sáng', 30, '', 'Bận']
                                               for i in (1, 2)]
        self.grid.append([3, 'Track 1', 'CS1', D, 'Key', 'H210', 'Sáng', 30, '', J])
        self.requests, self.script = [], []

    def cell(self, ref):
        column, row = probe.cell_ref(ref)
        values = self.grid[row - 1]
        index = probe.column_index(column)
        return values[index] if index < len(values) else ''

    def set(self, ref, value):
        column, row = probe.cell_ref(ref)
        while len(self.grid) < row:
            self.grid.append([])
        values, index = self.grid[row - 1], probe.column_index(column)
        values.extend([''] * (index + 1 - len(values)))
        values[index] = value

    def handler(self, request):
        step = self.script.pop(0) if self.script else {}
        self.requests.append(request)
        assert request.headers['Authorization'] == 'Bearer ' + TOKEN
        assert request.url.host == 'sheets.googleapis.com'
        path = unquote(request.url.raw_path.decode().split('?')[0])
        prefix = f'/v4/spreadsheets/{COPY_ID}/values/'
        assert path.startswith(prefix)
        quoted_tab = "'" + TAB.replace("'", "''") + "'!"
        assert path[len(prefix):].startswith(quoted_tab)
        if step.get('before'):
            step['before'](self)
        if step.get('raise'):
            raise step['raise']('synthetic', request=request)
        if step.get('status'):
            return httpx.Response(step['status'], json={})
        if request.method == 'GET':
            assert request.url.params['valueRenderOption'] == 'FORMULA'
            assert path.endswith('!A1:T1000')
            response = httpx.Response(200, json={'range': 'x', 'majorDimension': 'ROWS',
                                                 'values': json.loads(json.dumps(self.grid))})
        else:
            assert request.method == 'PUT' and request.url.params['valueInputOption'] == 'RAW'
            body = json.loads(request.content)
            ref = path[len(prefix) + len(quoted_tab):]
            assert ref == 'D5' and body['range'] == quoted_tab + 'D5'
            assert body['majorDimension'] == 'ROWS' and len(body['values']) == 1 and len(body['values'][0]) == 1
            self.set(ref, body['values'][0][0])
            response = httpx.Response(200, json={'updatedCells': step.get('updated', 1)})
        if step.get('after'):
            step['after'](self)
        if step.get('raise_after'):
            raise step['raise_after']('synthetic', request=request)
        return response


@pytest.fixture
def sheets():
    return FakeSheets()


def run(path, sheets, mode='execute', token=TOKEN):
    client = httpx.Client(transport=httpx.MockTransport(sheets.handler))
    environ = {} if token is None else {probe.TOKEN_ENV: token}
    return probe.run(path, mode, client=client, environ=environ, stamp='T')


def methods(sheets):
    return [r.method for r in sheets.requests]


def public_text(summary):
    return json.dumps(summary, ensure_ascii=False)


def assert_redacted(summary):
    text = public_text(summary)
    for secret in (TOKEN, COPY_ID, TAB, D, J, TEST, 'googleapis', 'Bearer'):
        assert secret not in text


# -- success paths ------------------------------------------------------------

def test_execute_writes_one_d_cell_verifies_then_restores(tmp_path, sheets):
    original = json.loads(json.dumps(sheets.grid))
    summary = run(config(tmp_path), sheets)
    assert (summary['state'], summary['code']) == ('restored', 'ORIGINAL_RANGE_CONFIRMED')
    assert methods(sheets) == ['GET', 'PUT', 'GET', 'PUT', 'GET']
    assert summary['http'] == ['GET:200', 'PUT:200', 'GET:200', 'PUT:200', 'GET:200']
    assert summary['changed_cells'] == ['D5'] and summary['guard_unchanged'] is True
    assert sheets.grid == original
    assert summary['compare_and_set'] is False and summary['anchors_or_roster_verified'] is False
    assert_redacted(summary)


def test_execute_without_restore_leaves_test_value(tmp_path, sheets):
    summary = run(config(tmp_path, probe_restore_original=False), sheets)
    assert summary['state'] == 'verified' and methods(sheets) == ['GET', 'PUT', 'GET']
    assert sheets.cell('D5') == TEST and sheets.cell('J5') == J


def test_private_evidence_is_0600_and_holds_raw_reads(tmp_path, sheets):
    summary = run(config(tmp_path), sheets)
    directory = tmp_path / '.bee-bot' / 'probe-evidence'
    assert sorted(summary['evidence_files']) == sorted(
        f'probe-T-{n}.json' for n in ('before', 'after-write', 'scoped-changes', 'after-restore', 'summary'))
    for name in summary['evidence_files']:
        assert stat.S_IMODE(os.stat(directory / name).st_mode) == 0o600
        assert TOKEN not in (directory / name).read_text(encoding='utf-8')
    before = json.loads((directory / 'probe-T-before.json').read_text(encoding='utf-8'))
    assert before['values'][4][3] == D
    changes = json.loads((directory / 'probe-T-scoped-changes.json').read_text(encoding='utf-8'))
    assert changes['cells'] == [{'row': 5, 'col': 3, 'before': D, 'after': TEST}]


def test_read_only_mode_never_writes(tmp_path, sheets):
    summary = run(config(tmp_path, write_enabled=False), sheets, mode='read_only')
    assert summary['state'] == 'read_ok' and methods(sheets) == ['GET']


# -- clean pre-network blockers ------------------------------------------------

@pytest.mark.parametrize('changes, state, code', [
    ({'write_enabled': False}, 'precondition_failed', 'WRITE_DISABLED'),
    ({'verification_status': 'owner_asserted'}, 'precondition_failed', 'OWNER_CONFIRMATION_MISSING'),
    ({'candidate_copy_id': 'short'}, 'precondition_failed', 'COPY_ID_INVALID'),
    ({'known_source_ids': [COPY_ID]}, 'precondition_failed', 'SOURCE_ID_DENIED'),
    ({'probe_tab': 'Other tab'}, 'precondition_failed', 'TAB_NOT_ALLOWED'),
    ({'allowed_tabs': []}, 'precondition_failed', 'TAB_NOT_ALLOWED'),
    ({'probe_cell': 'J5', 'allowed_cells': ['J5']}, 'precondition_failed', 'CELL_NOT_ALLOWED'),
    ({'probe_cell': 'D6'}, 'precondition_failed', 'CELL_NOT_ALLOWED'),
    ({'probe_cell': 'D5:D6'}, 'precondition_failed', 'INVALID_CELL_REF'),
    ({'probe_guard_cell': 'J6'}, 'precondition_failed', 'GUARD_NOT_SAME_ROW_J'),
    ({'probe_guard_cell': 'I5'}, 'precondition_failed', 'GUARD_NOT_SAME_ROW_J'),
    ({'probe_expected_d': DELETE}, 'precondition_failed', 'EXPECTED_SNAPSHOT_MISSING'),
    ({'probe_expected_j': DELETE}, 'precondition_failed', 'EXPECTED_SNAPSHOT_MISSING'),
    ({'probe_expected_d': ' '}, 'precondition_failed', 'EXPECTED_SNAPSHOT_MISSING'),
    ({'probe_test_value': D}, 'precondition_failed', 'TEST_VALUE_INVALID'),
    ({'probe_test_value': '=A1'}, 'precondition_failed', 'TEST_VALUE_INVALID'),
    ({'probe_read_range': 'A1:I1000'}, 'precondition_failed', 'READ_RANGE_INVALID'),
    ({'probe_read_range': 'A:T'}, 'precondition_failed', 'READ_RANGE_INVALID'),
    ({'probe_read_range': 'A1:T99999'}, 'precondition_failed', 'READ_RANGE_INVALID'),
    ({'probe_evidence_dir': '/tmp/public-evidence'}, 'precondition_failed', 'EVIDENCE_DIR_NOT_PRIVATE'),
    ({'probe_evidence_dir': '.bee-bot/source'}, 'precondition_failed', 'EVIDENCE_DIR_NOT_PRIVATE'),
])
def test_config_blockers_stop_before_any_request(tmp_path, sheets, changes, state, code):
    summary = run(config(tmp_path, **changes), sheets)
    assert (summary['state'], summary['code']) == (state, code)
    assert sheets.requests == [] and summary['requests'] == {'GET': 0, 'PUT': 0}
    assert not (tmp_path / '.bee-bot' / 'probe-evidence').exists()


@pytest.mark.parametrize('token, code', [(None, 'TOKEN_MISSING'), ('  ', 'TOKEN_MISSING'),
                                         ('<your-token>', 'TOKEN_PLACEHOLDER'), ('changeme', 'TOKEN_PLACEHOLDER'),
                                         ('$BEE_BOT_SHEETS_ACCESS_TOKEN_PLACEHOLDER', 'TOKEN_PLACEHOLDER')])
@pytest.mark.parametrize('mode', ['preflight', 'read_only', 'execute'])
def test_missing_or_placeholder_credential_is_clean_blocker(tmp_path, sheets, token, code, mode):
    summary = run(config(tmp_path), sheets, mode=mode, token=token)
    assert (summary['state'], summary['code']) == ('missing_credential', code)
    assert sheets.requests == []


def test_preflight_never_uses_network_even_with_credential(tmp_path, sheets):
    summary = probe.run(config(tmp_path), 'preflight', client=None, environ={probe.TOKEN_ENV: TOKEN})
    assert (summary['state'], summary['credential']) == ('preflight_ok', 'present')
    assert_redacted(summary)


def test_unreadable_config(tmp_path, sheets):
    summary = run(tmp_path / 'missing.json', sheets)
    assert summary['code'] == 'CONFIG_UNREADABLE' and sheets.requests == []


# -- fresh-read preconditions --------------------------------------------------

@pytest.mark.parametrize('ref, value, code', [
    ('D5', 'Somebody Else', 'EXPECTED_SNAPSHOT_MISMATCH'),
    ('J5', 'Bận', 'EXPECTED_SNAPSHOT_MISMATCH'),
    ('D5', '=VLOOKUP(A5,X!A:B,2)', 'FORMULA_TARGET'),
    ('J5', '=IF(1,"Rảnh")', 'FORMULA_TARGET'),
])
def test_fresh_get_mismatch_or_formula_stops_before_put(tmp_path, sheets, ref, value, code):
    sheets.set(ref, value)
    summary = run(config(tmp_path), sheets)
    assert (summary['state'], summary['code']) == ('precondition_failed', code)
    assert methods(sheets) == ['GET'] and summary['evidence_files'][0] == 'probe-T-before.json'


def test_row_shift_moves_expected_values_away_and_blocks(tmp_path, sheets):
    sheets.grid.insert(2, ['inserted by ops'])
    summary = run(config(tmp_path), sheets)
    assert summary['code'] == 'EXPECTED_SNAPSHOT_MISMATCH' and methods(sheets) == ['GET']


@pytest.mark.parametrize('step, code', [({'status': 403}, 'GET_HTTP_403'),
                                        ({'raise': httpx.ConnectTimeout}, 'GET_TRANSPORT_ERROR')])
def test_initial_read_failure_never_writes(tmp_path, sheets, step, code):
    sheets.script = [step]
    summary = run(config(tmp_path), sheets)
    assert (summary['state'], summary['code']) == ('read_failed', code) and methods(sheets) == ['GET']


# -- uncertain writes: no restore, no retry ------------------------------------

@pytest.mark.parametrize('step, state, code, landed', [
    ({'raise': httpx.ReadTimeout}, 'write_uncertain', 'PUT_TRANSPORT_ERROR', False),
    ({'raise_after': httpx.ReadTimeout}, 'write_uncertain', 'PUT_TRANSPORT_ERROR', True),
    ({'status': 503}, 'write_uncertain', 'PUT_HTTP_503', False),
    ({'status': 403}, 'write_rejected', 'PUT_HTTP_403', False),
    ({'updated': 2}, 'write_uncertain', 'PUT_UPDATED_CELLS_NOT_ONE', True),
])
def test_put_failures_stop_without_restore_or_retry(tmp_path, sheets, step, state, code, landed):
    sheets.script = [{}, step]
    summary = run(config(tmp_path), sheets)
    assert (summary['state'], summary['code']) == (state, code)
    assert methods(sheets) == ['GET', 'PUT']
    assert sheets.cell('D5') == (TEST if landed else D)


def test_concurrent_edit_elsewhere_after_write_blocks_restore(tmp_path, sheets):
    sheets.script = [{}, {'after': lambda s: s.set('J4', 'Rảnh')}]
    summary = run(config(tmp_path), sheets)
    assert (summary['state'], summary['code']) == ('unexpected_concurrent_diff', 'OTHER_CELLS_CHANGED')
    assert summary['changed_cells'] == ['D5', 'J4'] and methods(sheets) == ['GET', 'PUT', 'GET']
    assert sheets.cell('D5') == TEST  # left for ops; never auto-restored


def test_guard_j_change_blocks_restore(tmp_path, sheets):
    sheets.script = [{}, {'after': lambda s: s.set('J5', 'Bận')}]
    summary = run(config(tmp_path), sheets)
    assert summary['state'] == 'unexpected_concurrent_diff' and summary['guard_unchanged'] is False
    assert methods(sheets) == ['GET', 'PUT', 'GET']


def test_ops_overwrite_of_target_after_write_is_readback_mismatch(tmp_path, sheets):
    sheets.script = [{}, {'after': lambda s: s.set('D5', 'Ops value')}]
    summary = run(config(tmp_path), sheets)
    assert (summary['state'], summary['code']) == ('write_uncertain', 'READBACK_MISMATCH')
    assert methods(sheets) == ['GET', 'PUT', 'GET'] and sheets.cell('D5') == 'Ops value'


def test_LIMITATION_no_cas_edit_between_get_and_put_is_overwritten(tmp_path, sheets):
    """Not a safety success: the PUT is unconditional, so this ops edit is lost undetected."""
    sheets.script = [{}, {'before': lambda s: s.set('D5', 'Ops edit in window')}]
    summary = run(config(tmp_path, probe_restore_original=False), sheets)
    assert summary['state'] == 'verified' and sheets.cell('D5') == TEST
    assert summary['compare_and_set'] is False


@pytest.mark.parametrize('step, state', [({'raise': httpx.ReadTimeout}, 'restore_uncertain'),
                                         ({'status': 500}, 'restore_uncertain'),
                                         ({'status': 403}, 'restore_rejected')])
def test_restore_failure_is_not_retried(tmp_path, sheets, step, state):
    sheets.script = [{}, {}, {}, step]
    summary = run(config(tmp_path), sheets)
    assert summary['state'] == state and methods(sheets) == ['GET', 'PUT', 'GET', 'PUT']


def test_restore_readback_with_concurrent_change_is_unverified(tmp_path, sheets):
    sheets.script = [{}, {}, {}, {'after': lambda s: s.set('A1', 'ops')}]
    summary = run(config(tmp_path), sheets)
    assert (summary['state'], summary['code']) == ('restore_unverified', 'RANGE_NOT_EQUAL_TO_BEFORE')
    assert methods(sheets) == ['GET', 'PUT', 'GET', 'PUT', 'GET']


# -- CLI -------------------------------------------------------------------------

def test_cli_default_is_preflight_without_client(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(probe.TOKEN_ENV, TOKEN)
    monkeypatch.setattr(probe.httpx, 'Client', lambda *a, **k: pytest.fail('network client created'))
    assert probe.main([str(config(tmp_path))]) == 0
    output = capsys.readouterr().out
    assert json.loads(output)['state'] == 'preflight_ok' and TOKEN not in output and COPY_ID not in output


def test_cli_has_no_token_argument():
    with pytest.raises(SystemExit):
        probe.main(['config.json', '--token', TOKEN])


def test_cli_execute_blocked_by_write_disabled_creates_no_request(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(probe.TOKEN_ENV, TOKEN)
    sent = []
    real_client = httpx.Client
    monkeypatch.setattr(probe.httpx, 'Client', lambda *a, **k: real_client(
        transport=httpx.MockTransport(lambda r: sent.append(r) or httpx.Response(500))))
    assert probe.main([str(config(tmp_path, write_enabled=False)), '--execute']) == 2
    assert json.loads(capsys.readouterr().out)['code'] == 'WRITE_DISABLED' and sent == []
