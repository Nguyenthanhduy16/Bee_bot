"""Offline contract tests; no bot token or real send is used."""

from concurrent.futures import ThreadPoolExecutor
import json

import httpx
import pytest

from bee_bot.errors import BeeBotError
from bee_bot.zalo import ZaloBotClient, ZaloIngress, parse_update


def update(text="Tôi là vận hành", sender="sender-an", chat_type="PRIVATE"):
    return {"ok": True, "result": {"event_name": "message.text.received", "message": {
        "from": {"id": sender, "display_name": "Vận hành", "is_bot": False},
        "chat": {"id": "chat-an", "chat_type": chat_type},
        "message_id": "message-1", "date": 1750316131602, "text": text,
    }}}


def ingress(tmp_path):
    return ZaloIngress(tmp_path / "zalo.db", identities={"sender-an": "an"}, webhook_secret="secret-for-test")


def test_api_contract_payload_and_url():
    captured = []
    def respond(request):
        captured.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": "out-1"}})
    client = ZaloBotClient("1:test-token", transport=httpx.MockTransport(respond))
    assert client.send_message("chat-an", "Xin chào")["message_id"] == "out-1"
    client.get_updates(5)
    client.close()
    assert captured == [
        ("/bot1:test-token/sendMessage", {"chat_id": "chat-an", "text": "Xin chào"}),
        ("/bot1:test-token/getUpdates", {"timeout": "5"}),
    ]
    assert "test-token" not in repr(client)


def test_send_timeout_uncertain_and_never_retried():
    calls = []
    def fail(request):
        calls.append(request)
        raise httpx.ReadTimeout("secret-token in a URL", request=request)
    client = ZaloBotClient("1:secret-token", transport=httpx.MockTransport(fail))
    with pytest.raises(BeeBotError) as error:
        client.send_message("chat-an", "Hello")
    client.close()
    assert error.value.code == "ZALO_DELIVERY_UNCERTAIN"
    assert "secret-token" not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize("body", [{"ok": True}, ["not-envelope"]])
def test_malformed_send_response_is_uncertain(body):
    client = ZaloBotClient("1:test-token", transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
    with pytest.raises(BeeBotError) as error:
        client.send_message("chat-an", "hello")
    client.close()
    assert error.value.code == "ZALO_DELIVERY_UNCERTAIN"


def test_api_error_description_cannot_leak_token():
    client = ZaloBotClient("1:test-token", transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": False, "description": "test-token"})))
    with pytest.raises(BeeBotError) as error:
        client.get_me()
    client.close()
    assert error.value.code == "ZALO_API_ERROR"
    assert "test-token" not in str(error.value)


def test_fresh_bot_no_webhook_exact_api_404_normalized():
    client = ZaloBotClient("1:test-token", transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": False, "error_code": 404, "description": "Not Found"})))
    assert client.get_webhook_info() == {"url": ""}
    with pytest.raises(BeeBotError):
        client.get_me()
    client.close()


@pytest.mark.parametrize("http_status,code,description", [(404, 404, "Not Found"), (200, 401, "Unauthorized"), (200, 403, "Internal server error"), (200, "404", "Not Found"), (200, 404, "Other error")])
def test_no_webhook_normalization_does_not_mask_other_failures(http_status, code, description):
    client = ZaloBotClient("1:test-token", transport=httpx.MockTransport(lambda request: httpx.Response(http_status, json={"ok": False, "error_code": code, "description": description})))
    with pytest.raises(BeeBotError) as error:
        client.get_webhook_info()
    assert error.value.code == "ZALO_API_ERROR"
    client.close()


def test_idle_long_poll_exact_api_timeout_returns_none():
    client = ZaloBotClient("1:test-token", transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": False, "error_code": 408, "description": "Request timeout"})))
    assert client.get_updates(timeout=1) is None
    with pytest.raises(BeeBotError):
        client.send_message("chat-an", "hello")
    client.close()


@pytest.mark.parametrize("http_status,code,description", [(408, 408, "Request timeout"), (200, "408", "Request timeout"), (200, 408, "Other timeout"), (200, 401, "Unauthorized")])
def test_idle_normalization_is_not_general_timeout_suppression(http_status, code, description):
    client = ZaloBotClient("1:test-token", transport=httpx.MockTransport(lambda request: httpx.Response(http_status, json={"ok": False, "error_code": code, "description": description})))
    with pytest.raises(BeeBotError):
        client.get_updates(timeout=1)
    client.close()


def test_webhook_config_validation_before_network():
    client = ZaloBotClient("1:test-token", transport=httpx.MockTransport(lambda request: pytest.fail("no network expected")))
    for url, secret in [("http://example.com/hook", "secret-for-test"), ("https://example.com/hook", "short")]:
        with pytest.raises(BeeBotError):
            client.set_webhook(url, secret)
    with pytest.raises(BeeBotError):
        client.send_message("chat-an", "x" * 2001)
    client.close()


def test_update_normalization():
    first = parse_update(update())
    second = parse_update(update()["result"])
    assert first == second
    assert first.event_id.startswith("zalo:")
    assert first.received_at.endswith("+00:00")
    assert first.display_name == "Vận hành"


def test_display_name_is_presentation_only_and_duplicate_may_change_name(tmp_path):
    adapter = ingress(tmp_path)
    first = update()
    first["result"]["message"]["from"]["display_name"] = "  Duy  Nguyễn  "
    incoming = adapter.receive_polled(first)
    seen = []
    adapter.process(incoming["event_id"], lambda actor, event: seen.append((actor, event.display_name)) or {"ok": True})
    assert seen == [("an", "Duy Nguyễn")]
    duplicate = update()
    duplicate["result"]["message"]["from"]["display_name"] = "Tên mới"
    assert adapter.receive_polled(duplicate)["duplicate"] is True
    unsafe = update()
    unsafe["result"]["message"]["from"]["display_name"] = "x" * 81
    assert parse_update(unsafe).display_name is None


def test_auth_checked_before_payload_parsing(tmp_path):
    adapter = ingress(tmp_path)
    with pytest.raises(BeeBotError) as error:
        adapter.receive_webhook(None, "bad-secret")
    assert error.value.code == "ZALO_UNAUTHORIZED"


def test_identity_is_sender_mapping_not_text_or_name(tmp_path):
    adapter = ingress(tmp_path)
    received = adapter.receive_webhook(update(), "secret-for-test")
    observed = []
    result = adapter.process(received["event_id"], lambda actor, event: observed.append((actor, event.text)) or {"ok": True})
    assert result["status"] == "completed"
    assert observed == [("an", "Tôi là vận hành")]
    with pytest.raises(BeeBotError) as error:
        adapter.receive_webhook(update(sender="unknown"), "secret-for-test")
    assert error.value.code == "ZALO_UNKNOWN_USER"


def test_group_and_unsupported_rejected(tmp_path):
    adapter = ingress(tmp_path)
    with pytest.raises(BeeBotError) as error:
        adapter.receive_webhook(update(chat_type="GROUP"), "secret-for-test")
    assert error.value.code == "ZALO_UNSUPPORTED_CHAT"
    payload = update()
    payload["result"]["event_name"] = "message.unsupported.received"
    with pytest.raises(BeeBotError) as error:
        adapter.receive_webhook(payload, "secret-for-test")
    assert error.value.code == "ZALO_UNSUPPORTED_EVENT"


def test_durable_duplicate_does_not_recall_handler(tmp_path):
    adapter = ingress(tmp_path)
    incoming = adapter.receive_polled(update())
    calls = []
    handler = lambda actor, event: calls.append(event.event_id) or {"answer": "Đã ghi nhận"}
    adapter.process(incoming["event_id"], handler)
    restarted = ingress(tmp_path)
    assert restarted.receive_polled(update())["duplicate"] is True
    assert restarted.process(incoming["event_id"], handler)["result"]["answer"] == "Đã ghi nhận"
    assert calls == [incoming["event_id"]]


def test_duplicate_changed_payload_conflicts(tmp_path):
    adapter = ingress(tmp_path)
    adapter.receive_polled(update())
    with pytest.raises(BeeBotError) as error:
        adapter.receive_polled(update("changed text"))
    assert error.value.code == "EVENT_CONFLICT"


def test_pending_event_cannot_use_revoked_identity(tmp_path):
    adapter = ingress(tmp_path)
    incoming = adapter.receive_polled(update())
    revoked = ZaloIngress(tmp_path / "zalo.db", identities={}, webhook_secret="secret-for-test")
    with pytest.raises(BeeBotError) as error:
        revoked.process(incoming["event_id"], lambda actor, event: pytest.fail("revoked identity must not run"))
    assert error.value.code == "ZALO_IDENTITY_CHANGED"


def test_handler_failure_stays_uncertain_not_replayed(tmp_path):
    adapter = ingress(tmp_path)
    incoming = adapter.receive_polled(update())
    calls = []
    def fail(actor, event):
        calls.append(actor)
        raise RuntimeError("possibly committed")
    assert adapter.process(incoming["event_id"], fail)["status"] == "uncertain"
    assert ingress(tmp_path).process(incoming["event_id"], fail)["requires_reconciliation"] is True
    assert calls == ["an"]


def test_two_workers_claim_only_once(tmp_path):
    adapter = ingress(tmp_path)
    incoming = adapter.receive_polled(update())
    calls = []
    def handle(actor, event):
        calls.append(actor)
        return {"answer": "received"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: adapter.process(incoming["event_id"], handle), range(2)))
    assert calls == ["an"]
    assert all(result["status"] in {"completed", "processing"} for result in results)
