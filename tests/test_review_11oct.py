"""Independent QA-11OCT regressions for the repaired Zalo candidate.

F1–F4 assert desired safety behaviour; F6 remains an explicit unfixed
observation. No network, model, credential or live profile access.
"""
import asyncio
import json
import sqlite3
import subprocess

import pytest
import yaml

from bee_bot.errors import BeeBotError
from bee_bot.mcp_server import create_server
from bee_bot.zalo import ZaloIngress, parse_update
from bee_bot.zalo_worker import HermesRunner, PollingWorker


def update(message_id="m1", name=None):
    sender = {"id": "sender-an", "is_bot": False}
    if name is not None:
        sender["display_name"] = name
    return {"event_name": "message.text.received", "message": {
        "from": sender, "chat": {"id": "chat-an", "chat_type": "PRIVATE"},
        "message_id": message_id, "text": "Tôi là ai"}}


class Client:
    def __init__(self):
        self.payload, self.sent, self.polls = update(), [], 0
    def get_webhook_info(self):
        return {"url": ""}
    def get_updates(self, timeout):
        self.polls += 1
        return self.payload
    def send_message(self, chat, text):
        self.sent.append((chat, text))
        return {"message_id": "out"}


class Service:
    def get_my_assignments(self, actor):
        return []
    def get_my_notifications(self, actor):
        return []


def root_profile(root, model=None):
    (root.parent / "config.yaml").write_text(yaml.safe_dump(
        {"model": model or {"default": "model-test", "provider": "provider-test"}}))


def hermes_db(path, rows):
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,source TEXT,created_source TEXT,title TEXT UNIQUE,
            title_source TEXT,display_name TEXT,origin_json TEXT)""")
        for row in rows:
            db.execute("INSERT OR REPLACE INTO sessions VALUES (?,?,?,?,?,?,?)", row)


def statuses(worker):
    with worker.db() as db:
        return [row[0] for row in db.execute("SELECT status FROM zalo_inbox ORDER BY rowid")]


def test_r1_profile_preflight_stops_before_poll_or_pending_consumption(tmp_path):
    """F2: profile failure must preserve both remote and already queued messages."""
    profiles = tmp_path / "profiles"
    root_profile(profiles)
    calls = []
    runner = HermesRunner(profiles, run=lambda command, **kw: calls.append(command))
    runner.prepare_profile()
    config_path = profiles / "bee-zalo/config.yaml"
    config = yaml.safe_load(config_path.read_text())
    # Hermes Desktop resolves provider settings into the profile; root lacks them.
    config["model"]["base_url"] = "https://provider.invalid/v1"
    config_path.write_text(yaml.safe_dump(config))

    client = Client()
    ingress = ZaloIngress(tmp_path / "inbox.db", identities={"sender-an": "an"}, webhook_secret="test-secret")
    worker = PollingWorker(client, ingress, runner, Service())
    ingress.receive_polled(update("already-queued"))
    for message_id in ("m1", "m2"):
        client.payload = update(message_id)
        with pytest.raises(BeeBotError) as error:
            worker.once()
        assert error.value.code == "ZALO_PROFILE_CONFLICT"

    assert calls == []  # Hermes/model never started.
    assert client.polls == 0
    assert statuses(worker) == ["pending"]
    with worker.db() as db:
        assert db.execute("SELECT DISTINCT result FROM zalo_inbox").fetchall() == [(None,)]
        assert db.execute("SELECT count(*) FROM zalo_deliveries").fetchone() == (0,)
    assert client.sent == []


def test_r2_absent_resume_recovers_before_start_and_failed_turn_never_retries(tmp_path):
    """F3: absence is proven in a readable DB; a started failure stays uncertain."""
    profiles = tmp_path / "profiles"
    root_profile(profiles)
    calls = []
    path = profiles / "bee-zalo/state.db"
    def run(command, **kwargs):
        calls.append(command)
        if len(calls) == 2:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="session not found")
        hermes_db(path, [("s-new", "zalo", "zalo", "topic", None, None, None)])
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(
            {"type": "result", "session_id": "s-new", "exit_code": 0, "text": "ok"}))
    runner = HermesRunner(profiles, run=run)
    runner.prepare_profile()
    hermes_db(path, [])
    client = Client()
    ingress = ZaloIngress(tmp_path / "inbox.db", identities={"sender-an": "an"}, webhook_secret="test-secret")
    worker = PollingWorker(client, ingress, runner, Service())
    with worker.db() as db:
        db.execute("INSERT INTO zalo_shared_sessions VALUES ('sender-an','an','chat-an','s-gone')")
    for message in ("m1", "m2", "m2"):
        client.payload = update(message)
        worker.once()
    assert statuses(worker) == ["completed", "uncertain"]
    assert len(calls) == 2 and "--resume" not in calls[0]
    assert calls[1][-2:] == ["--resume", "s-new"]
    assert client.sent == [("chat-an", "ok")]
    with worker.db() as db:
        assert db.execute("SELECT session FROM zalo_shared_sessions").fetchone() == ("s-new",)
        results = [json.loads(row[0]) for row in db.execute("SELECT result FROM zalo_inbox ORDER BY rowid")]
    assert results[0]["session_recovered"] is True
    assert results[1] == {"diagnostic": {"stage": "hermes", "error": "HERMES_UNCERTAIN", "model_may_have_run": True}}


def test_r3_skills_unexposed_memory_disabled_and_soul_drift_stops_run(tmp_path):
    """F1: legacy skills are preserved but not exposed; managed SOUL is pinned."""
    profiles = tmp_path / "profiles"
    root_profile(profiles)
    runner = HermesRunner(profiles)
    runner.prepare_profile()
    profile = profiles / "bee-zalo"
    assert not (profile / "skills").exists()
    config = yaml.safe_load((profile / "config.yaml").read_text())
    assert config["platform_toolsets"] == {"acp": ["bee_bot"]}
    assert config["memory"] == {"memory_enabled": False, "user_profile_enabled": False}
    assert runner.TOOLSETS == "bee_bot"
    skill = profiles / "bee-zalo/skills/bee-bot/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("Injected by one sender's conversation")
    extra = profiles / "bee-zalo/skills/injected/SKILL.md"
    extra.parent.mkdir(parents=True)
    extra.write_text("Applies to all senders")
    assert runner.prepare_profile() == "bee-zalo"
    assert skill.read_text() == "Injected by one sender's conversation"
    assert extra.exists()
    soul = profile / "SOUL.md"
    assert "Đọc skill `bee-bot`" not in soul.read_text()
    soul.write_text(soul.read_text() + "\nInjected by one sender")
    before = soul.read_bytes()
    with pytest.raises(BeeBotError) as error:
        runner.prepare_profile()
    assert error.value.code == "ZALO_PROFILE_MIGRATION_REQUIRED"
    assert soul.read_bytes() == before


def test_r4_pre_resume_identity_failure_has_effect_free_redacted_diagnostic(tmp_path, caplog):
    """F2/F4: binding mismatch blocks Hermes and records the precise safe stage."""
    profiles = tmp_path / "profiles"
    root_profile(profiles)
    calls = []
    runner = HermesRunner(profiles, run=lambda command, **kw: calls.append(command))
    runner.prepare_profile()
    hermes_db(profiles / "bee-zalo/state.db", [("s1", "zalo", "zalo", "Zalo · X — t", "user", "X", json.dumps(
        {"bee_bot_zalo": {"sender_id": "other", "chat_id": "other", "header": "Zalo · X", "topic": "t", "title": "Zalo · X — t"}}))])
    client = Client()
    ingress = ZaloIngress(tmp_path / "inbox.db", identities={"sender-an": "an"}, webhook_secret="test-secret")
    worker = PollingWorker(client, ingress, runner, Service())
    with worker.db() as db:
        db.execute("INSERT INTO zalo_shared_sessions VALUES ('sender-an','an','chat-an','s1')")
    worker.once()
    assert calls == []
    assert statuses(worker) == ["uncertain"]
    with worker.db() as db:
        assert json.loads(db.execute("SELECT result FROM zalo_inbox").fetchone()[0]) == {
            "diagnostic": {"stage": "session", "error": "ZALO_IDENTITY_CHANGED", "model_may_have_run": False}}
    assert "session" in caplog.text and "ZALO_IDENTITY_CHANGED" in caplog.text
    assert "sender-an" not in caplog.text and "Tôi là ai" not in caplog.text
    assert client.sent == []


def test_r5_emoji_zwj_display_name_is_dropped_not_cleaned():
    """F6: parse_update rejects names containing Cf characters (ZWJ emoji)
    instead of cleaning them like hermes_sessions._clean_name does."""
    assert parse_update(update(name="Duy 👨‍💻")).display_name is None
    assert parse_update(update(name="Duy 💻")).display_name == "Duy 💻"


def test_r6_display_name_change_on_redelivery_is_not_a_conflict(tmp_path):
    """Regression guard (passes): redelivery with a new name stays a duplicate."""
    ingress = ZaloIngress(tmp_path / "inbox.db", identities={"sender-an": "an"}, webhook_secret="test-secret")
    first = ingress.receive_polled(update(name="A"))
    again = ingress.receive_polled(update(name="B"))
    assert first["event_id"] == again["event_id"] and again["duplicate"] is True
    try:
        changed = update(name="A")
        changed["message"]["text"] = "khác"
        ingress.receive_polled(changed)
    except BeeBotError as exc:
        assert exc.code == "EVENT_CONFLICT"
    else:
        raise AssertionError("changed text must conflict")


@pytest.mark.parametrize("tool,args", [
    ("create_change_request", {"kind": "leave", "assignment_id": "a1", "sender_confirmed": True}),
    ("add_substitute", {"request_id": "request", "substitute_id": "binh"}),
    ("approve_leave_request", {"request_id": "request"}),
    ("nominate_replacement", {"request_id": "request", "substitute_id": "binh"}),
    ("respond_to_invitation", {"invitation_id": "invitation", "accept": True, "no_other_busy": True}),
    ("cancel_request", {"request_id": "request", "reason": "test"}),
    ("withdraw_leave_approval", {"request_id": "request", "reason": "test"}),
    ("create_issue", {"room": "H210", "description": "synthetic", "detected_at": "2026-10-10T08:00:00+07:00"}),
    ("update_issue", {"issue_id": "issue", "status": "processing"}),
    ("reconcile_request", {"request_id": "request"}),
    ("run_maintenance", {}),
])
def test_r7_zalo_context_gate_covers_every_state_changing_tool(monkeypatch, tool, args):
    """F5: a launch with an ambient ops actor must not change state without an event.

    Reconcile and maintenance read Sheets but change persisted request/outbox state.
    A recording mock makes their invocation observable without touching any DB.
    """
    class Directory:
        def list_people(self):
            return [{"person_id": "ops", "active": True, "role": "ops"}]

    class RecordingService:
        schedule = Directory()
        def __init__(self):
            self.calls = []
        def __getattr__(self, name):
            def record(actor, **kwargs):
                self.calls.append((name, actor, kwargs))
                return {"state_changed": True}
            return record

    monkeypatch.setenv("BEE_BOT_ACTOR_ID", "ops")
    monkeypatch.setenv("BEE_BOT_CHANNEL", "zalo")
    service = RecordingService()
    server = create_server(service)  # Exercise actor from launch environment.

    async def invoke():
        content = await server.call_tool(tool, args)
        content = content[0] if isinstance(content, tuple) else content
        return json.loads(content[0].text)

    for event_id in (None, "", "${BEE_BOT_EVENT_ID}", "zalo:invalid", "adapter:" + "a" * 64):
        if event_id is None:
            monkeypatch.delenv("BEE_BOT_EVENT_ID", raising=False)
        else:
            monkeypatch.setenv("BEE_BOT_EVENT_ID", event_id)
        result = asyncio.run(invoke())
        assert service.calls == [], (tool, event_id, result, service.calls)
        assert result.get("error") == "EVENT_CONTEXT_REQUIRED", result

    monkeypatch.setenv("BEE_BOT_EVENT_ID", parse_update(update()).event_id)
    assert asyncio.run(invoke())["ok"] is True
    assert len(service.calls) == 1 and service.calls[0][0:2] == (tool, "ops")


def test_r8_zalo_reads_remain_available_without_worker_event(env, monkeypatch):
    """F5 gate must preserve reads for the configured actor without performing work."""
    monkeypatch.setenv("BEE_BOT_ACTOR_ID", "an")
    monkeypatch.setenv("BEE_BOT_CHANNEL", "zalo")
    monkeypatch.delenv("BEE_BOT_EVENT_ID", raising=False)
    server = create_server(env.service)

    async def read():
        content = await server.call_tool("get_my_assignments", {})
        content = content[0] if isinstance(content, tuple) else content
        return json.loads(content[0].text)

    result = asyncio.run(read())
    assert result["ok"] is True
    assert {a["coach_id"] for a in result["result"]} == {"an"}
    assert env.service.list_my_requests("an") == []
    assert env.service.get_my_notifications("an") == []
