"""Independent factory preparation; Google transport wiring is pending Lead."""
import asyncio
import json

import pytest

from bee_bot.errors import BeeBotError
from bee_bot.mcp_server import create_server
from bee_bot.schedule import JsonSchedule
from bee_bot.schedule_factory import _check_google_copy, create_schedule
from bee_bot.service import BeeBotService


def test_default_json_uses_data_directory(tmp_path):
    schedule = create_schedule(environ={'BEE_BOT_DATA_DIR': str(tmp_path)})
    assert isinstance(schedule, JsonSchedule)
    assert schedule.path == tmp_path / 'schedule.json'


def test_explicit_json_path_overrides_environment(tmp_path):
    path = tmp_path / 'explicit.json'
    schedule = create_schedule(path, environ={'BEE_BOT_SCHEDULE': str(tmp_path / 'other.json')})
    assert schedule.path == path


def test_json_environment_path_and_backend(tmp_path):
    path = tmp_path / 'schedule.json'
    assert create_schedule(environ={'BEE_BOT_SCHEDULE_BACKEND': 'json',
                                    'BEE_BOT_SCHEDULE': str(path)}).path == path


def test_sheets_config_does_not_implicitly_enable_google(tmp_path):
    schedule = create_schedule(environ={'BEE_BOT_DATA_DIR': str(tmp_path),
                                        'BEE_BOT_SHEETS_CONFIG': '/missing/private.json'})
    assert isinstance(schedule, JsonSchedule)


@pytest.mark.parametrize('backend', ['', 'google_sheets', 'production', 'JSON'])
def test_unknown_backend_does_not_fall_back_to_json(backend):
    with pytest.raises(BeeBotError) as error:
        create_schedule(environ={'BEE_BOT_SCHEDULE_BACKEND': backend})
    assert error.value.code == 'SCHEDULE_BACKEND_INVALID'


@pytest.mark.parametrize('path', [None, '', 'private.json'])
def test_google_requires_absolute_private_config(path):
    env = {'BEE_BOT_SCHEDULE_BACKEND': 'google_sheets_test_copy'}
    if path is not None:
        env['BEE_BOT_SHEETS_CONFIG'] = path
    with pytest.raises(BeeBotError) as error:
        create_schedule(environ=env)
    assert error.value.code == 'SHEETS_CONFIG_REQUIRED'


@pytest.mark.parametrize('contents', [None, 'private-secret: malformed json', '[]', 'null', '\ufffd'])
def test_invalid_google_config_errors_do_not_expose_private_inputs(tmp_path, contents):
    config = tmp_path / 'private-secret-config.json'
    if contents is not None:
        config.write_text(contents, encoding='utf-8')
    with pytest.raises(BeeBotError) as error:
        create_schedule(environ={'BEE_BOT_SCHEDULE_BACKEND': 'google_sheets_test_copy',
                                 'BEE_BOT_SHEETS_CONFIG': str(config)})
    assert error.value.code == 'SHEETS_CONFIG_INVALID'
    assert 'private-secret' not in str(error.value)
    assert str(config) not in str(error.value)


def test_google_requires_complete_pinned_config(tmp_path):
    config = tmp_path / 'private.json'
    config.write_text('{}', encoding='utf-8')
    with pytest.raises(BeeBotError) as error:
        create_schedule(environ={'BEE_BOT_SCHEDULE_BACKEND': 'google_sheets_test_copy',
                                 'BEE_BOT_SHEETS_CONFIG': str(config)})
    assert error.value.code == 'SHEETS_CONFIG_INVALID'


def test_google_owner_gate_runs_before_credentials(tmp_path):
    config = tmp_path / 'private.json'
    config.write_text(json.dumps({
        'spreadsheet_id': 'copy', 'tab': 'Tab', 'sheet_id': 0,
        'allowed_spreadsheet_ids': ['copy'], 'denied_source_ids': [],
        'allowed_tabs': ['Tab'], 'owner_confirmed_copy': False,
        'people': [{'person_id': 'an'}],
    }), encoding='utf-8')
    with pytest.raises(BeeBotError) as error:
        create_schedule(environ={'BEE_BOT_SCHEDULE_BACKEND': 'google_sheets_test_copy',
                                 'BEE_BOT_SHEETS_CONFIG': str(config)})
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'


def test_google_factory_constructs_pinned_adapter_from_private_config(tmp_path, monkeypatch):
    import bee_bot.google_sheets_transport as google
    from bee_bot.sheets_adapter import SheetsScheduleAdapter

    config = tmp_path / 'private.json'
    config.write_text(json.dumps({
        'spreadsheet_id': 'copy', 'tab': 'Tab', 'sheet_id': 0,
        'allowed_spreadsheet_ids': ['copy'], 'denied_source_ids': [],
        'allowed_tabs': ['Tab'], 'owner_confirmed_copy': True,
        'people': [{'person_id': 'an', 'display_name': 'An', 'role': 'labcoach',
                    'active': True, 'sheet_names': ['An']}],
    }), encoding='utf-8')

    class FakeTransport:
        def __init__(self, settings):
            self.settings = settings

        def provenance(self):
            return {'kind': 'test_copy', 'spreadsheet_id': self.settings['spreadsheet_id'],
                    'tab': self.settings['tab'], 'sheet_id': self.settings['sheet_id'],
                    'owner_confirmed_copy': self.settings['owner_confirmed_copy']}

        def close(self):
            pass

    monkeypatch.setattr(google, 'GoogleSheetsTransport', FakeTransport)
    schedule = create_schedule(environ={'BEE_BOT_SCHEDULE_BACKEND': 'google_sheets_test_copy',
                                        'BEE_BOT_SHEETS_CONFIG': str(config)})
    assert isinstance(schedule, SheetsScheduleAdapter)
    assert schedule.backend_name == 'google_sheets_test_copy'
    assert schedule.list_people()[0]['person_id'] == 'an'


def test_default_factory_service_mcp_reads_json(env):
    schedule = create_schedule(environ={'BEE_BOT_SCHEDULE': str(env.path)})
    service = BeeBotService(env.db, schedule, clock=lambda: env.clock.now)

    async def read():
        server = create_server(service, 'an')
        response = await server.call_tool('get_my_assignments', {})
        payload = response[1] if isinstance(response, tuple) else json.loads(response[0].text)
        assert payload['ok'] is True
        assert [a['assignment_id'] for a in payload['result']] == ['a1']

    try:
        asyncio.run(read())
    finally:
        service.close()


def copy_provenance(**changes):
    return {'kind': 'test_copy', 'spreadsheet_id': 'placeholder-copy',
            'tab': 'Synthetic', 'sheet_id': 0, 'owner_confirmed_copy': True, **changes}


def test_google_gate_accepts_owner_confirmed_unknown_source_and_sheet_zero():
    provenance = copy_provenance()
    assert _check_google_copy(provenance, {'placeholder-copy'}, ['Synthetic']) == provenance
    assert 'copy_of' not in provenance


@pytest.mark.parametrize('confirmed', [False, None, 1, 'true'])
def test_google_gate_requires_owner_confirmation_even_with_legacy_source(confirmed):
    with pytest.raises(BeeBotError) as error:
        _check_google_copy(copy_provenance(owner_confirmed_copy=confirmed, copy_of='placeholder-source'),
                           {'placeholder-copy'}, ['Synthetic'])
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'


@pytest.mark.parametrize('tabs', [[], ['Other tab'], None, 'Synthetic'])
def test_google_gate_requires_an_explicit_allowed_tab(tabs):
    with pytest.raises(BeeBotError) as error:
        _check_google_copy(copy_provenance(), {'placeholder-copy'}, tabs)
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'


def test_google_gate_source_denylist_overrides_destination_allowlist():
    with pytest.raises(BeeBotError) as error:
        _check_google_copy(copy_provenance(), {'placeholder-copy'}, ['Synthetic'], [' placeholder-copy '])
    assert error.value.code == 'SHEETS_PROVENANCE_REJECTED'


def test_google_gate_rejects_unapproved_destination():
    with pytest.raises(BeeBotError):
        _check_google_copy(copy_provenance(), {'other-copy'}, ['Synthetic'])


def test_google_gate_rejects_self_copy_despite_confirmation():
    with pytest.raises(BeeBotError):
        _check_google_copy(copy_provenance(copy_of='placeholder-copy'), {'placeholder-copy'}, ['Synthetic'])
