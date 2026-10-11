"""Additional independent QA edges for the frozen Core recovery checkpoint.

Only synthetic data and the real adapter/service; no live API or credentials.
The converted acceptance fixture is reused to keep its D/J layout consistent.
"""
import json

import pytest

from bee_bot.errors import BeeBotError
from test_sheets_adapter_acceptance import env, replacement


@pytest.mark.parametrize('columns', [[['B']], [{'column': 'B'}]])
def test_S6_unhashable_merge_columns_have_controlled_error_and_no_write(env, columns):
    """Malformed transport data must not escape its public read API as raw TypeError."""
    request, respond = replacement(env, 'chi', 9, 'binh', 'malformed-columns')
    raw = json.loads(env.sheet.read_text())
    raw['merges'].append({'start': 9, 'end': 10, 'columns': columns})
    env.sheet.write_text(json.dumps(raw))
    # Capture both paths first so the failing desired type assertion also has
    # evidence that the service kept the request and performed no write.
    with pytest.raises(Exception) as read_error:
        env.adapter.coverage()
    with pytest.raises(Exception) as service_error:
        respond()
    assert env.transport.write_log() == []
    assert env.service.store.get('request', request['id'])['status'] == 'waiting_confirmation'
    assert isinstance(read_error.value, BeeBotError), type(read_error.value).__name__
    assert read_error.value.code == 'SCHEDULE_MALFORMED'
    assert isinstance(service_error.value, BeeBotError), type(service_error.value).__name__
    assert service_error.value.code == 'SCHEDULE_MALFORMED'
