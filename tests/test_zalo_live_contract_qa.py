"""Observed live API envelope regressions using mock transport only."""

import logging

import httpx
import pytest

from bee_bot.errors import BeeBotError
from bee_bot.zalo import ZaloBotClient


def client_for(body, status=200):
    return ZaloBotClient("1:synthetic-live-contract-token", transport=httpx.MockTransport(
        lambda request: httpx.Response(status, json=body)))


def test_fresh_bot_no_webhook_envelope_is_empty_webhook_only():
    client = client_for({"ok": False, "error_code": 404, "description": "Not Found"})
    try:
        assert client.get_webhook_info() == {"url": ""}
        for call in (client.get_me, lambda: client.get_updates(1), lambda: client.send_message("demo-chat", "Demo")):
            with pytest.raises(BeeBotError):
                call()
    finally:
        client.close()


@pytest.mark.parametrize("body,status", [
    ({"ok": False, "error_code": 401, "description": "Not Found"}, 200),
    ({"ok": False, "error_code": 403, "description": "Not Found"}, 200),
    ({"ok": False, "error_code": "404", "description": "Not Found"}, 200),
    ({"ok": False, "error_code": 404, "description": "Authentication failed"}, 200),
    ({"ok": False, "description": "Not Found"}, 200),
    ({"ok": True, "error_code": 404}, 200),
    ({"ok": False, "error_code": 404, "description": "Not Found"}, 404),
    ({"ok": False, "error_code": 404, "description": "Not Found"}, 201),
])
def test_webhook_empty_state_does_not_hide_other_failures(body, status):
    client = client_for(body, status)
    try:
        with pytest.raises(BeeBotError):
            client.get_webhook_info()
    finally:
        client.close()


def test_api_error_details_and_token_are_not_logged_or_exposed(caplog):
    token = "1:synthetic-live-contract-token"
    client = client_for({"ok": False, "error_code": 401, "description": f"private response {token}"})
    try:
        with caplog.at_level(logging.DEBUG), pytest.raises(BeeBotError) as error:
            client.get_webhook_info()
        assert token not in caplog.text
        assert "private response" not in caplog.text
        assert token not in str(error.value)
        assert "private response" not in str(error.value)
    finally:
        client.close()


def test_network_timeout_cannot_be_treated_as_empty_poll_result():
    def timeout(request):
        raise httpx.ReadTimeout("synthetic transport failure", request=request)

    client = ZaloBotClient("1:synthetic-live-contract-token", transport=httpx.MockTransport(timeout))
    try:
        with pytest.raises(BeeBotError) as error:
            client.get_updates(1)
        assert error.value.code == "ZALO_UNAVAILABLE"
    finally:
        client.close()


def test_only_expected_api_poll_timeout_is_normal_empty_result():
    client = client_for({"ok": False, "error_code": 408, "description": "Request timeout"})
    try:
        assert client.get_updates(1) is None
        for call in (client.get_me, client.get_webhook_info, lambda: client.send_message("demo-chat", "Demo")):
            with pytest.raises(BeeBotError):
                call()
    finally:
        client.close()


@pytest.mark.parametrize("body,status", [
    ({"ok": False, "error_code": 401, "description": "Request timeout"}, 200),
    ({"ok": False, "error_code": "408", "description": "Request timeout"}, 200),
    ({"ok": False, "error_code": 408, "description": "Authentication failed"}, 200),
    ({"ok": False, "description": "Request timeout"}, 200),
    ({"ok": True, "error_code": 408}, 200),
    ({"ok": False, "error_code": 408, "description": "Request timeout"}, 408),
    ({"ok": False, "error_code": 408, "description": "Request timeout"}, 500),
])
def test_poll_idle_normalization_does_not_hide_other_errors(body, status):
    client = client_for(body, status)
    try:
        with pytest.raises(BeeBotError):
            client.get_updates(1)
    finally:
        client.close()
