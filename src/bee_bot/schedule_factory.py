"""Select a schedule from trusted local configuration, never model arguments."""
import json
import os
from pathlib import Path

from .errors import BeeBotError
from .schedule import JsonSchedule


def _check_google_copy(provenance, allowed_spreadsheet_ids, allowed_tabs, known_source_ids=()):
    """Private-config gate, ready for the Data config-key handshake.

    Real Google requires explicit owner confirmation, including when copy_of is
    known. Legacy adapter provenance alone does not enable this backend. The
    caller supplies only trusted config, never model tool arguments.
    """
    from .sheets_adapter import check_provenance

    if (not isinstance(provenance, dict) or provenance.get('kind') != 'test_copy'
            or provenance.get('owner_confirmed_copy') is not True
            or not isinstance(allowed_tabs, (list, tuple, set, frozenset))
            or not allowed_tabs or provenance.get('tab') not in allowed_tabs):
        raise BeeBotError('SHEETS_PROVENANCE_REJECTED',
                          'Backend Google chỉ dùng bản sao và tab đã được chủ sở hữu cho phép.')
    return check_provenance(provenance, allowed_spreadsheet_ids, known_source_ids)


def _read_sheets_config(environ):
    location = environ.get('BEE_BOT_SHEETS_CONFIG')
    if not location or not Path(location).is_absolute():
        raise BeeBotError('SHEETS_CONFIG_REQUIRED',
                          'Cần đường dẫn tuyệt đối tới cấu hình Sheets riêng ngoài Git.')
    try:
        config = json.loads(Path(location).read_text(encoding='utf-8'))
        if not isinstance(config, dict):
            raise ValueError('config must be an object')
    except (OSError, ValueError, UnicodeError):
        # Neither the private path nor its content belongs in the public error.
        raise BeeBotError('SHEETS_CONFIG_INVALID', 'Không đọc được cấu hình Sheets riêng hợp lệ.') from None
    return config


def create_schedule(json_path=None, *, environ=None):
    """Create the configured schedule without changing runtime configuration.

    JSON uses the explicit path, BEE_BOT_SCHEDULE, or DATA_DIR/schedule.json.
    Unknown backends fail closed. Google requires an explicit backend and an
    absolute private config with a pinned destination and explicit roster.
    """
    environ = os.environ if environ is None else environ
    backend = environ.get('BEE_BOT_SCHEDULE_BACKEND', 'json')
    if backend == 'json':
        base = Path(environ.get('BEE_BOT_DATA_DIR', '.bee-bot')).resolve()
        path = json_path if json_path is not None else environ.get('BEE_BOT_SCHEDULE', str(base / 'schedule.json'))
        return JsonSchedule(path)
    if backend == 'google_sheets_test_copy':
        config = _read_sheets_config(environ)
        from .google_sheets_transport import GoogleSheetsTransport
        from .sheets_adapter import SheetsScheduleAdapter
        try:
            allowed = config['allowed_spreadsheet_ids']
            denied = config['denied_source_ids']
            tabs = config['allowed_tabs']
            people = config['people']
            if (not isinstance(allowed, list) or not isinstance(denied, list)
                    or not isinstance(tabs, list) or not isinstance(people, list) or not people):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise BeeBotError('SHEETS_CONFIG_INVALID', 'Cấu hình Sheets thiếu phạm vi hoặc roster tin cậy.') from None
        _check_google_copy({
            'kind': 'test_copy', 'spreadsheet_id': config.get('spreadsheet_id'),
            'tab': config.get('tab'), 'sheet_id': config.get('sheet_id'),
            'copy_of': config.get('copy_of'),
            'owner_confirmed_copy': config.get('owner_confirmed_copy'),
        }, allowed, tabs, denied)
        transport = GoogleSheetsTransport(config)
        try:
            _check_google_copy(transport.provenance(), allowed, tabs, denied)
            schedule = SheetsScheduleAdapter(transport, people, allowed, denied)
        except Exception:
            transport.close()
            raise
        schedule.backend_name = backend
        return schedule
    raise BeeBotError('SCHEDULE_BACKEND_INVALID', 'Backend lịch không được hỗ trợ; không tự chọn backend khác.')
