"""Polling bridge tests: all API/model traffic is mocked, no credentials used."""
import asyncio
import json
from pathlib import Path
import subprocess

import pytest
import yaml

from bee_bot.errors import BeeBotError
from bee_bot.mcp_server import create_server
from bee_bot.zalo import ZaloIngress
from bee_bot.zalo_worker import HermesRunner, PollingWorker, update_channel_context


def event(message_id="m1", sender="sender-an"):
    return {"event_name": "message.text.received", "message": {
        "from": {"id": sender, "is_bot": False}, "chat": {"id": "chat-an", "chat_type": "PRIVATE"},
        "message_id": message_id, "text": 'Xin nghỉ; $(do-not-run) `literal`',
    }}


class Client:
    def __init__(self):
        self.payload, self.url, self.sent, self.failure = event(), "", [], False
    def get_webhook_info(self):
        return {"url": self.url}
    def get_updates(self, timeout):
        return self.payload
    def send_message(self, chat, text):
        self.sent.append((chat, text))
        if self.failure:
            raise BeeBotError("ZALO_DELIVERY_UNCERTAIN", "timeout")
        return {"message_id": "out-1"}


class Runner:
    def __init__(self):
        self.calls, self.failure = [], False
    def reply(self, actor, incoming, session_id):
        self.calls.append((actor, incoming.event_id, session_id))
        if self.failure:
            raise BeeBotError("HERMES_UNCERTAIN", "timeout")
        return {"text": "Bot hỏi xác nhận", "session_id": session_id or "session-first"}


class Service:
    def get_my_assignments(self, actor):
        if actor != "an":
            raise BeeBotError("UNAUTHORIZED", "invalid actor")
        return []
    def get_my_notifications(self, actor):
        return [{"notification_id": "NT1", "recipient_id": actor, "event": "invitation", "delivery_status": "pending"}]


def worker(tmp_path):
    client, runner = Client(), Runner()
    ingress = ZaloIngress(tmp_path / "inbox.db", identities={"sender-an": "an"}, webhook_secret="test-secret")
    return PollingWorker(client, ingress, runner, Service())


def test_polling_keeps_sender_session_and_duplicate_dedup(tmp_path):
    w = worker(tmp_path)
    w.once()
    w.once()  # Redelivery: no repeat Hermes or outbox send.
    assert len(w.runner.calls) == 1
    assert len(w.client.sent) == 2  # Reply + one notification.
    w.client.payload = event("m2")
    w.once()
    assert w.runner.calls[1][2] == "session-first"
    assert len(w.client.sent) == 3


def test_active_webhook_never_deleted_or_polled(tmp_path):
    w = worker(tmp_path)
    w.client.url = "https://existing.example/hook"
    with pytest.raises(BeeBotError) as error:
        w.once()
    assert error.value.code == "ZALO_WEBHOOK_ACTIVE"
    assert w.runner.calls == w.client.sent == []


def test_unknown_sender_no_reply_or_model(tmp_path):
    w = worker(tmp_path)
    w.client.payload = event(sender="unknown")
    w.once()
    assert w.runner.calls == w.client.sent == []


def test_two_senders_cannot_share_actor_profile(tmp_path):
    ingress = ZaloIngress(tmp_path / "inbox.db", identities={"first": "an", "second": "an"}, webhook_secret="test-secret")
    with pytest.raises(BeeBotError) as error:
        PollingWorker(Client(), ingress, Runner(), Service())
    assert error.value.code == "ZALO_CONFIG"


def test_send_uncertain_never_retried(tmp_path):
    w = worker(tmp_path)
    w.client.failure = True
    w.once()
    w.once()
    assert len(w.client.sent) == 2
    with w.db() as db:
        assert db.execute("SELECT DISTINCT status FROM zalo_deliveries").fetchall() == [("uncertain",)]


def test_pending_inbox_resumed_but_uncertain_model_not_replayed(tmp_path):
    w = worker(tmp_path)
    incoming = w.ingress.receive_polled(event())
    w.client.payload = None
    w.runner.failure = True
    w.once()
    w.once()
    assert len(w.runner.calls) == 1
    with w.db() as db:
        assert db.execute("SELECT status FROM zalo_inbox WHERE event_id=?", (incoming["event_id"],)).fetchone()[0] == "uncertain"


def source_profile(root):
    source = root / "bee-bot-an"
    (source / "skills/bee-bot").mkdir(parents=True)
    (source / "config.yaml").write_text(yaml.safe_dump({
        "model": {"default": "model-test", "provider": "provider-test", "api_key": "do-not-copy"},
        "mcp_servers": {"bee_bot": {"command": "python", "args": ["-m", "bee_bot.mcp_server"], "env": {"BEE_BOT_ACTOR_ID": "an", "BEE_BOT_DB": "fake.db", "BEE_BOT_SCHEDULE": "fake.json"}}},
    }))
    (source / "SOUL.md").write_text("Use Bee Bot tools")
    (source / "skills/bee-bot/SKILL.md").write_text("Bee Bot workflow")
    (source / "auth.json").write_text('"do-not-copy"')
    (source / ".env").write_text("SECRET=do-not-copy")
    return source


def test_hermes_fixed_profile_stdin_resume_and_event_env(tmp_path, monkeypatch):
    source_profile(tmp_path)
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"type": "result", "session_id": "s1", "exit_code": 0, "text": "Xin xác nhận"}), stderr="private logs")
    monkeypatch.setenv("ZALO_BOT_TOKEN", "do-not-pass")
    runner = HermesRunner(tmp_path, run=run)
    from bee_bot.zalo import parse_update
    incoming = parse_update(event())
    assert runner.reply("an", incoming, "s0")["session_id"] == "s1"
    command, kwargs = calls[0]
    assert command[:5] == ["hermes", "-p", "bee-zalo-an", "chat", "--oneshot"]
    assert command[command.index("--source") + 1] == "zalo"
    assert command[-2:] == ["--resume", "s0"]
    assert kwargs["input"] == incoming.text
    assert kwargs["env"]["BEE_BOT_EVENT_ID"] == incoming.event_id
    assert "ZALO_BOT_TOKEN" not in kwargs["env"]
    assert not (tmp_path / "bee-zalo-an/auth.json").exists()
    assert not (tmp_path / "bee-zalo-an/.env").exists()
    assert "do-not-copy" not in (tmp_path / "bee-zalo-an/config.yaml").read_text()


def test_runner_timeout_safe_error_and_profile_conflict(tmp_path):
    source_profile(tmp_path)
    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"], output="sensitive")
    runner = HermesRunner(tmp_path, run=timeout)
    from bee_bot.zalo import parse_update
    with pytest.raises(BeeBotError) as error:
        runner.reply("an", parse_update(event()))
    assert error.value.code == "HERMES_UNCERTAIN"
    assert "sensitive" not in str(error.value)
    (tmp_path / "bee-zalo-an/config.yaml").write_text("model: changed\n")
    with pytest.raises(BeeBotError) as error:
        runner.prepare_profile("an")
    assert error.value.code == "ZALO_PROFILE_CONFLICT"


def test_existing_zalo_profile_context_updated_preserving_security_and_source(tmp_path):
    source = source_profile(tmp_path)
    original = "Xác nhận trực tiếp, không đổi danh tính. Đây là lịch JSON và thông báo giả lập, không có cập nhật Sheets hoặc gửi Zalo thật."
    (source / "SOUL.md").write_text(original)
    runner = HermesRunner(tmp_path)
    runner.prepare_profile("an")
    target = tmp_path / "bee-zalo-an"
    text = (target / "SOUL.md").read_text()
    assert "chat riêng Zalo" in text and "Bot API thật" in text
    assert "chưa ghi Google Sheets thật" in text
    assert "Xác nhận trực tiếp, không đổi danh tính" in text
    assert "không có cập nhật Sheets hoặc gửi Zalo thật" not in text
    assert (source / "SOUL.md").read_text() == original
    before_config = (target / "config.yaml").read_bytes()
    update_channel_context(target)
    assert (target / "SOUL.md").read_text() == text
    assert (target / "config.yaml").read_bytes() == before_config


def test_adapter_event_mcp_mutations_have_stable_ids(tmp_path, monkeypatch):
    class Schedule:
        def list_people(self):
            return [{"person_id": "an", "role": "labcoach", "active": True}]
    class RecordingService:
        schedule = Schedule()
        def __init__(self): self.ids = []
        def create_issue(self, actor, **kwargs):
            self.ids.append(kwargs["event_id"])
            return {"recorded": True}
    service = RecordingService()
    server = create_server(service, "an")
    async def invoke():
        args = {"room": "A101", "description": "issue", "detected_at": "2026-10-10T08:00:00+07:00"}
        monkeypatch.setenv("BEE_BOT_EVENT_ID", "zalo:stable")
        await server.call_tool("create_issue", args)
        await server.call_tool("create_issue", args)
        await server.call_tool("create_issue", {**args, "description": "other issue"})
        monkeypatch.delenv("BEE_BOT_EVENT_ID")
        await server.call_tool("create_issue", args)
        await server.call_tool("create_issue", args)
    asyncio.run(invoke())
    assert service.ids[0] == service.ids[1]
    assert len(set(service.ids)) == 4
