"""Pinned, single-tab Google API transport for SheetsScheduleAdapter.

Only one column-D RAW value update is exposed. No OAuth flow, metadata writes,
append, retry, or compare-and-set. Credentials refresh in memory only.
See docs/GOOGLE_SHEETS_SETUP.md for the private configuration contract.
"""
from contextvars import ContextVar
from copy import deepcopy
from hashlib import sha256
import json
import logging
import math
import os
from pathlib import Path
import re
import stat
from urllib.parse import quote

from google.auth.transport.requests import Request
from google.oauth2 import credentials as user_credentials, service_account
import httpx

from .errors import BeeBotError
from .sheets_copy_transport import COLUMNS, TransportRejected, TransportTimeout

SHEETS_SCOPE = 'https://www.googleapis.com/auth/spreadsheets'
API_ROOT = 'https://sheets.googleapis.com/v4/spreadsheets/'
REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_CREDENTIAL_BYTES = 64 * 1024
TOKEN_URI = 'https://oauth2.googleapis.com/token'
_PRIVATE_IO = ContextVar('bee_bot_google_private_io', default=False)


class _PrivateIOFilter(logging.Filter):
    def filter(self, record):
        return not _PRIVATE_IO.get()


# httpx logs request URLs at INFO; these contain workbook IDs and tab names.
# Suppress library diagnostics only during this transport's private I/O, in
# this context. Do not alter log levels or suppress other callers' requests.
for _name in ('httpx', 'httpcore.connection', 'httpcore.http11', 'httpcore.http2',
              'httpcore.proxy', 'httpcore.http_proxy', 'httpcore.socks',
              'urllib3.connectionpool', 'google.auth.transport.requests',
              'google.auth._client', 'google.oauth2._client', 'google.oauth2.credentials'):
    logging.getLogger(_name).addFilter(_PrivateIOFilter())


def _error(code):
    return BeeBotError(code, 'Google Sheets operation blocked; inspect private configuration or reconcile.')


def _integer(value, minimum=0):
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _hash(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def row_fingerprint(cells):
    """Offline sidecar proof, excluding mutable D and ops-owned J. Not an ID."""
    return _hash({c: cells.get(c) for c in COLUMNS if c not in {'D', 'J'}})


def structure_fingerprint(rows, merges):
    """Bind test sidecars to the complete A-J layout (including headers/merges).

    A structural edit requires ops to reapprove the sidecar; do not relocate
    sidecar IDs by matching names/STT/fingerprints. Metadata is the movable ID.
    """
    return _hash({'rows': [[r['row'], row_fingerprint(r['cells'])] for r in rows], 'merges': merges})


class GoogleSheetsTransport:
    def __init__(self, config, credentials=None, http_client=None):
        try:
            cfg = deepcopy(dict(config))
            sid, tab, gid = cfg['spreadsheet_id'], cfg['tab'], cfg['sheet_id']
            for key in ('allowed_spreadsheet_ids', 'denied_source_ids'):
                if (not isinstance(cfg[key], list)
                        or any(not isinstance(v, str) or not v.strip() for v in cfg[key])):
                    raise ValueError
            allowed = {v.strip() for v in cfg['allowed_spreadsheet_ids']}
            denied = {v.strip() for v in cfg['denied_source_ids']}
            if (not isinstance(sid, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', sid)
                    or sid not in allowed or sid in denied or not isinstance(tab, str)
                    or not tab.strip() or any(ord(c) < 32 for c in tab) or not _integer(gid)
                    or cfg.get('owner_confirmed_copy') is not True):
                raise ValueError
            copy_of = cfg.get('copy_of')
            if copy_of is not None and (not isinstance(copy_of, str) or not copy_of.strip()
                                        or copy_of != copy_of.strip() or copy_of == sid or copy_of in allowed):
                raise ValueError
            max_rows = cfg.get('max_rows', 10000)
            count = cfg['expected_anchor_count']
            if not _integer(max_rows, 1) or not _integer(count, 1) or count > max_rows:
                raise ValueError
            mode = cfg['anchor_mode']
            if mode == 'metadata':
                if not isinstance(cfg.get('metadata_key'), str) or not cfg['metadata_key'].strip():
                    raise ValueError
            elif mode == 'test_sidecar':
                if not isinstance(cfg.get('anchor_sidecar_path'), str) or not Path(cfg['anchor_sidecar_path']).is_absolute():
                    raise ValueError
            else:
                raise ValueError
            anchors = cfg.get('allowed_write_anchors', [])
            if (not isinstance(anchors, list) or any(not isinstance(a, str) or not a for a in anchors)
                    or len(set(anchors)) != len(anchors) or type(cfg.get('write_enabled', False)) is not bool):
                raise ValueError
            timeout = cfg.get('timeout_seconds', 20)
            if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 120:
                raise ValueError
        except (KeyError, TypeError, ValueError, AttributeError):
            raise _error('SHEETS_PROVENANCE_REJECTED') from None
        self._config = cfg
        self._sid, self._tab, self._gid = sid, tab, gid
        self._copy_of, self._max_rows, self._count = copy_of, max_rows, count
        self._write_enabled, self._allowed_anchors = cfg.get('write_enabled', False), frozenset(anchors)
        self._timeout = timeout
        self._credentials = credentials if credentials is not None else self._load_credentials(cfg.get('credential_path'))
        self._check_scopes()
        self._owns_client = http_client is None
        self._client = http_client if http_client is not None else httpx.Client(
            transport=httpx.HTTPTransport(retries=0), follow_redirects=False)

    @staticmethod
    def _declared_scopes(payload):
        """Scopes recorded in the file, accepting list, space-separated or legacy key."""
        raw = payload.get('scopes')
        if raw is None:
            raw = payload.get('scope')
        if raw is None:
            return None
        return raw.split() if isinstance(raw, str) else raw

    @staticmethod
    def _read_credential_file(path):
        """Read a private credential file, or fail closed without naming it.

        The file must sit outside this repository so a credential can never be
        committed, must not be reached through a symlinked final component, must
        be a regular file, and must not be readable by group or others. The
        location is checked both literally and after resolution. File type,
        mode and size are checked on the opened descriptor; directory parents
        must remain private because their path can change before os.open.
        """
        if not isinstance(path, str) or not path or not Path(path).is_absolute():
            raise _error('SHEETS_AUTH_REQUIRED')
        for variant in (Path(os.path.normpath(path)), Path(os.path.realpath(path))):
            if variant == REPO_ROOT or REPO_ROOT in variant.parents:
                raise _error('SHEETS_AUTH_LOCATION')
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0))
        except FileNotFoundError:
            raise _error('SHEETS_AUTH_REQUIRED') from None
        except OSError:
            # Symlinked final component (ELOOP), a directory, or no permission.
            raise _error('SHEETS_AUTH_LOCATION') from None
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise _error('SHEETS_AUTH_LOCATION')
            if info.st_mode & 0o077:
                raise _error('SHEETS_AUTH_INSECURE')
            if info.st_size > MAX_CREDENTIAL_BYTES:
                raise _error('SHEETS_AUTH_FAILED')
            chunks = []
            while len(chunk := os.read(descriptor, MAX_CREDENTIAL_BYTES)) > 0:
                chunks.append(chunk)
                if sum(map(len, chunks)) > MAX_CREDENTIAL_BYTES:
                    raise _error('SHEETS_AUTH_FAILED')
        finally:
            os.close(descriptor)
        try:
            return json.loads(b''.join(chunks).decode('utf-8'))
        except (UnicodeError, ValueError):
            raise _error('SHEETS_AUTH_FAILED') from None

    def _load_credentials(self, path):
        payload = self._read_credential_file(path)
        try:
            if not isinstance(payload, dict):
                raise ValueError
            kind = payload.get('type', 'authorized_user')
            scopes = self._declared_scopes(payload)
            if kind == 'authorized_user':
                # A Sheets-only grant is required: a broad Workspace token (for
                # example the shared Hermes one) fails closed here, before any
                # Google call, instead of being narrowed at refresh time. A
                # dedicated Sheets-only token in the same format is accepted.
                if not isinstance(scopes, list) or set(scopes) != {SHEETS_SCOPE}:
                    raise _error('SHEETS_AUTH_SCOPE')
                payload['type'] = kind
                return user_credentials.Credentials.from_authorized_user_info(payload, scopes=[SHEETS_SCOPE])
            if kind == 'service_account' and payload.get('token_uri') == TOKEN_URI:
                # A key file normally records no scopes; if it does, the same
                # Sheets-only rule applies before a token is ever requested.
                if scopes is not None and (not isinstance(scopes, list) or set(scopes) != {SHEETS_SCOPE}):
                    raise _error('SHEETS_AUTH_SCOPE')
                return service_account.Credentials.from_service_account_info(payload, scopes=[SHEETS_SCOPE])
            raise ValueError
        except BeeBotError:
            raise
        except Exception:
            raise _error('SHEETS_AUTH_FAILED') from None

    def _check_scopes(self):
        try:
            granted = getattr(self._credentials, 'granted_scopes', None)
            if (set(self._credentials.scopes or []) != {SHEETS_SCOPE}
                    or not self._credentials.has_scopes([SHEETS_SCOPE])
                    or (granted is not None and set(granted) != {SHEETS_SCOPE})):
                raise ValueError
        except Exception:
            raise _error('SHEETS_AUTH_SCOPE') from None

    def provenance(self):
        return {'kind': 'test_copy', 'spreadsheet_id': self._sid, 'tab': self._tab,
                'sheet_id': self._gid, 'copy_of': self._copy_of, 'owner_confirmed_copy': True,
                'contains_real_data': True}

    def _request(self, method, suffix='', **kwargs):
        private = _PRIVATE_IO.set(True)
        try:
            try:
                self._check_scopes()
                if not self._credentials.valid:
                    # This is BEFORE any Sheets dispatch, including each PUT.
                    request = Request()
                    try:
                        self._credentials.refresh(request)
                    finally:
                        request.session.close()
                self._check_scopes()
                if not self._credentials.valid or not isinstance(self._credentials.token, str) or not self._credentials.token:
                    raise ValueError
            except BeeBotError:
                raise
            except Exception:
                raise _error('SHEETS_AUTH_FAILED') from None
            try:
                response = self._client.request(method, API_ROOT + self._sid + suffix,
                    headers={'Authorization': 'Bearer ' + self._credentials.token},
                    timeout=self._timeout, follow_redirects=False, **kwargs)
            except Exception:
                if method == 'PUT':
                    raise TransportTimeout('Google Sheets write outcome unknown; reconcile without retry.') from None
                raise _error('SCHEDULE_UNAVAILABLE') from None
            status = response.status_code
            if not 200 <= status < 300:
                if method == 'PUT':
                    if status in {400, 401, 403, 404}:
                        raise TransportRejected('Google Sheets refused the write.')
                    raise TransportTimeout('Google Sheets write outcome unknown; reconcile without retry.')
                code = ('SHEETS_RATE_LIMITED' if status == 429 else
                        'SHEETS_PERMISSION_DENIED' if status == 403 else
                        'SHEETS_AUTH_FAILED' if status == 401 else 'SCHEDULE_UNAVAILABLE')
                raise _error(code)
            try:
                result = response.json()
                if not isinstance(result, dict):
                    raise ValueError
                return result
            except Exception:
                if method == 'PUT':
                    raise TransportTimeout('Google Sheets write receipt unknown; reconcile without retry.') from None
                raise _error('SCHEDULE_MALFORMED') from None
        finally:
            _PRIVATE_IO.reset(private)

    def _range(self, cells):
        return "'" + self._tab.replace("'", "''") + "'!" + cells

    def read_tab(self):
        # Grid effectiveValue keeps numeric types; userEnteredValue identifies
        # formulas/errors without a second, potentially mismatched values GET.
        payload = self._request('GET', params={
            'ranges': self._range(f'A1:J{self._max_rows + 1}'),
            'fields': 'spreadsheetId,developerMetadata,sheets(properties(sheetId,title,gridProperties(rowCount,columnCount)),merges,developerMetadata,data(startRow,startColumn,rowData(values(userEnteredValue,effectiveValue)),rowMetadata(developerMetadata)))',
        })
        try:
            rows, merges, metadata = self._normalize(payload)
            if self._config['anchor_mode'] == 'metadata':
                anchors = self._metadata_anchors(metadata, len(rows))
            else:
                anchors = self._sidecar_anchors(rows, merges)
            for row in rows:
                row['anchor'] = anchors.get(row['row'])
            self._check_coverage(rows, merges, anchors)
            return {'rows': rows, 'merges': merges}
        except BeeBotError:
            raise
        except Exception:
            raise _error('SCHEDULE_MALFORMED') from None

    def _normalize(self, payload):
        if payload.get('spreadsheetId') != self._sid:
            raise _error('SHEETS_PROVENANCE_REJECTED')
        sheets = payload['sheets']
        if not isinstance(sheets, list) or any(
                not _integer(s['properties']['sheetId']) or not isinstance(s['properties']['title'], str)
                for s in sheets):
            raise ValueError
        matched = [s for s in sheets if s['properties']['sheetId'] == self._gid]
        titled = [s for s in sheets if s['properties']['title'] == self._tab]
        if len(matched) != 1 or len(titled) != 1 or matched[0] is not titled[0]:
            raise _error('SHEETS_PROVENANCE_REJECTED')
        sheet = matched[0]
        size = sheet['properties']['gridProperties']
        n = size['rowCount']
        if not _integer(n, 1) or n > self._max_rows or not _integer(size['columnCount'], 10):
            raise _error('SCHEDULE_SCOPE_INCOMPLETE')
        rows = [{'row': i, 'anchor': None, 'cells': dict.fromkeys(COLUMNS)} for i in range(1, n + 1)]
        seen = set()
        row_metadata = []
        for grid in sheet.get('data', []):
            start, column = grid.get('startRow', 0), grid.get('startColumn', 0)
            if not _integer(start) or not _integer(column) or column != 0:
                raise ValueError
            for offset, data in enumerate(grid.get('rowData', [])):
                index = start + offset
                if index >= n or index in seen:
                    raise ValueError
                seen.add(index)
                values = data.get('values', [])
                if not isinstance(values, list) or len(values) > 10:
                    raise ValueError
                for c, cell in zip(COLUMNS, values):
                    entered, effective = cell.get('userEnteredValue', {}), cell.get('effectiveValue', {})
                    if 'formulaValue' in entered:
                        # Formula-derived canonical identity/data are unapproved.
                        # J is ops-owned; preserve its expression, never write it.
                        if c != 'J' or not isinstance(entered['formulaValue'], str):
                            raise _error('SCHEDULE_SCOPE_INCOMPLETE')
                        value = entered['formulaValue']
                    elif not effective:
                        if entered:
                            raise ValueError
                        value = None
                    else:
                        if len(effective) != 1:
                            raise ValueError
                        kind, value = next(iter(effective.items()))
                        if (kind == 'numberValue' and (isinstance(value, bool) or not isinstance(value, (int, float))
                                                       or not math.isfinite(value))
                                or kind == 'stringValue' and not isinstance(value, str)
                                or kind == 'boolValue' and type(value) is not bool
                                or kind not in {'numberValue', 'stringValue', 'boolValue'}):
                            raise ValueError
                    rows[index]['cells'][c] = value
            for offset, dimension in enumerate(grid.get('rowMetadata', [])):
                index = start + offset
                if index >= n or not isinstance(dimension, dict):
                    raise ValueError
                items = dimension.get('developerMetadata', [])
                if not isinstance(items, list):
                    raise ValueError
                for item in items:
                    if not isinstance(item, dict):
                        raise ValueError
                    location = item.get('location', {}).get('dimensionRange', {})
                    if (location.get('sheetId') != self._gid or location.get('dimension') != 'ROWS'
                            or location.get('startIndex') != index or location.get('endIndex') != index + 1):
                        raise ValueError
                    row_metadata.append(item)
        merges = []
        for m in sheet.get('merges', []):
            if m.get('sheetId', self._gid) != self._gid:
                raise ValueError
            a, b, c, d = m.get('startRowIndex', 0), m['endRowIndex'], m.get('startColumnIndex', 0), m['endColumnIndex']
            if (not all(_integer(v) for v in (a, b, c, d)) or not a < b <= n
                    or not c < d <= size['columnCount']):
                raise ValueError
            if c < 10:
                merges.append({'start': a + 1, 'end': b, 'columns': list(COLUMNS[c:min(d, 10)])})
        merges.sort(key=lambda m: (m['start'], m['end'], m['columns']))
        return rows, merges, payload.get('developerMetadata', []) + sheet.get('developerMetadata', []) + row_metadata

    def _metadata_anchors(self, metadata, row_count):
        anchors, seen_ids = {}, {}
        for item in metadata:
            if item.get('metadataKey') != self._config['metadata_key']:
                continue
            loc = item.get('location', {}).get('dimensionRange', {})
            if loc.get('sheetId') != self._gid:
                continue
            mid = item['metadataId']
            if not _integer(mid, 1):
                raise ValueError
            if mid in seen_ids:
                if seen_ids[mid] != item:
                    raise ValueError
                continue
            seen_ids[mid] = item
            start, end = loc.get('startIndex', 0), loc['endIndex']
            anchor = item['metadataValue']
            if (loc.get('dimension') != 'ROWS' or not _integer(start) or not _integer(end, 1)
                    or end != start + 1 or end > row_count or not isinstance(anchor, str)
                    or not anchor.strip() or start + 1 in anchors or anchor in anchors.values()):
                raise _error('SCHEDULE_SCOPE_INCOMPLETE')
            anchors[start + 1] = anchor
        return anchors

    def _sidecar_anchors(self, rows, merges):
        try:
            sidecar = json.loads(Path(self._config['anchor_sidecar_path']).read_text(encoding='utf-8'))
            if ((sidecar['spreadsheet_id'], sidecar['tab'], sidecar['sheet_id']) != (self._sid, self._tab, self._gid)
                    or sidecar['structure_fingerprint'] != structure_fingerprint(rows, merges)):
                raise ValueError
            anchors = {}
            for item in sidecar['anchors']:
                row, anchor = item['row'], item['anchor']
                if (not _integer(row, 1) or row > len(rows) or row in anchors or not isinstance(anchor, str)
                        or not anchor.strip() or anchor in anchors.values()
                        or item['fingerprint'] != row_fingerprint(rows[row - 1]['cells'])):
                    raise ValueError
                anchors[row] = anchor
            return anchors
        except Exception:
            raise _error('SCHEDULE_SCOPE_INCOMPLETE') from None

    def _check_coverage(self, rows, merges, anchors):
        # Conservatively cover numeric/STT rows, populated D, or canonical
        # B-G content. Business date/roster/overlap validation is the adapter's.
        candidates = set()
        for row in rows:
            cells = row['cells']
            a = cells['A']
            if isinstance(a, str) and a.strip().casefold() == 'stt':
                continue
            numeric = (isinstance(a, (int, float)) and not isinstance(a, bool)
                       or isinstance(a, str) and re.fullmatch(r'[1-9]\d*(?:\.0+)?', a.strip()))
            if numeric or any(cells[c] not in (None, '') for c in 'BCDEFG'):
                candidates.add(row['row'])
        if len(anchors) != self._count or set(anchors) != candidates:
            raise _error('SCHEDULE_SCOPE_INCOMPLETE')
        for row in rows:
            if row['row'] not in anchors:
                continue
            a = row['cells']['A']
            valid_stt = (not isinstance(a, bool) and isinstance(a, (int, float)) and a > 0 and float(a).is_integer()
                         or isinstance(a, str) and re.fullmatch(r'[1-9]\d*(?:\.0+)?', a.strip()))
            if not valid_stt:
                raise _error('SCHEDULE_SCOPE_INCOMPLETE')
        if any('D' in m['columns'] or ('A' in m['columns'] and m['end'] > m['start'])
               for m in merges if any(m['start'] <= r <= m['end'] for r in candidates)):
            raise _error('SCHEDULE_SCOPE_INCOMPLETE')

    def write_d(self, anchor, value, spreadsheet_id, tab):
        if ((spreadsheet_id, tab) != (self._sid, self._tab) or not self._write_enabled
                or not isinstance(anchor, str) or anchor not in self._allowed_anchors
                or not isinstance(value, str) or not value.strip()):
            raise TransportRejected('Google Sheets write outside pinned authorization.')
        snapshot = self.read_tab()
        matches = [r for r in snapshot['rows'] if r['anchor'] == anchor]
        if len(matches) != 1:
            raise TransportRejected('Google Sheets anchor not unique.')
        target = self._range(f"D{matches[0]['row']}")
        result = self._request('PUT', '/values/' + quote(target, safe=''),
            params={'valueInputOption': 'RAW'}, json={'range': target, 'majorDimension': 'ROWS', 'values': [[value]]})
        receipt_ranges = {target, target + f":D{matches[0]['row']}"}
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', self._tab):
            plain = f"{self._tab}!D{matches[0]['row']}"
            receipt_ranges.update({plain, plain + f":D{matches[0]['row']}"})
        if (result.get('spreadsheetId') != self._sid or not isinstance(result.get('updatedRange'), str)
                or result['updatedRange'] not in receipt_ranges
                or any(not _integer(result.get(k), 1) or result[k] != 1
                       for k in ('updatedCells', 'updatedRows', 'updatedColumns'))):
            raise TransportTimeout('Google Sheets write receipt mismatch; reconcile without retry.')

    def close(self):
        if self._owns_client:
            self._client.close()
