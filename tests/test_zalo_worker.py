"""Polling bridge tests: all API/model traffic is mocked, no credentials used."""
import asyncio
import json
from pathlib import Path
import sqlite3
import subprocess

import pytest
import yaml

from bee_bot.errors import BeeBotError
from bee_bot.mcp_server import create_server
from bee_bot.zalo import ZaloIngress
from bee_bot.zalo_worker import HermesRunner, PollingWorker, ZALO_CHANNEL_CONTEXT, managed_soul


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
        self.calls, self.failure, self.prepared = [], False, 0
    def prepare_profile(self):
        self.prepared += 1
        return "bee-zalo"
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


def test_shared_profile_starts_fresh_session_without_erasing_legacy_history(tmp_path):
    ingress = ZaloIngress(tmp_path / "inbox.db", identities={"sender-an": "an"}, webhook_secret="test-secret")
    with sqlite3.connect(ingress.path) as db:
        db.execute("CREATE TABLE zalo_sessions (sender TEXT PRIMARY KEY, actor TEXT NOT NULL, chat TEXT NOT NULL, session TEXT)")
        db.execute("INSERT INTO zalo_sessions VALUES (?,?,?,?)", ("sender-an", "an", "chat-an", "old-profile-session"))
    runner = Runner()
    w = PollingWorker(Client(), ingress, runner, Service())
    with w.db() as db:
        assert db.execute("SELECT session FROM zalo_sessions WHERE sender='sender-an'").fetchone() == ("old-profile-session",)
        assert db.execute("SELECT session FROM zalo_shared_sessions WHERE sender='sender-an'").fetchone() == (None,)
    w.once()
    assert len(runner.calls) == 1 and runner.calls[0][0] == "an" and runner.calls[0][2] is None
    with w.db() as db:
        assert db.execute("SELECT session FROM zalo_sessions WHERE sender='sender-an'").fetchone() == ("old-profile-session",)
        assert db.execute("SELECT session FROM zalo_shared_sessions WHERE sender='sender-an'").fetchone() == ("session-first",)


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
    (root.parent / "config.yaml").write_text(yaml.safe_dump({
        "model": {"default": "model-test", "provider": "provider-test", "api_key": "do-not-copy"}}))
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


def hermes_sessions_db(profile, *ids):
    with sqlite3.connect(profile / "state.db") as db:
        db.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,source TEXT,created_source TEXT,title TEXT UNIQUE,
            title_source TEXT,display_name TEXT,origin_json TEXT)""")
        for identifier in ids:
            db.execute("INSERT OR IGNORE INTO sessions VALUES (?,'zalo','zalo',NULL,NULL,NULL,NULL)", (identifier,))


def ok_run(calls, session="s1"):
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(
            {"type": "result", "session_id": session, "exit_code": 0, "text": "Xin xác nhận"}), stderr="private logs")
    return run


def test_hermes_shared_profile_stdin_resume_and_trusted_actor_env(tmp_path, monkeypatch):
    source_profile(tmp_path)
    calls = []
    monkeypatch.setenv("ZALO_BOT_TOKEN", "do-not-pass")
    runner = HermesRunner(tmp_path, run=ok_run(calls))
    runner.prepare_profile()
    hermes_sessions_db(tmp_path / "bee-zalo", "s0")
    from bee_bot.zalo import parse_update
    incoming = parse_update(event())
    assert runner.reply("an", incoming, "s0")["session_id"] == "s1"
    command, kwargs = calls[0]
    assert command[:5] == ["hermes", "-p", "bee-zalo", "chat", "--oneshot"]
    assert command[command.index("--source") + 1] == "zalo"
    assert command[command.index("-t") + 1] == "bee_bot"  # No skills/memory toolsets.
    assert command[-2:] == ["--resume", "s0"]
    assert kwargs["input"] == incoming.text
    assert kwargs["env"]["BEE_BOT_ACTOR_ID"] == "an"
    assert kwargs["env"]["BEE_BOT_EVENT_ID"] == incoming.event_id
    assert kwargs["env"]["BEE_BOT_ZALO_DISPLAY_NAME"] == ""
    assert "ZALO_BOT_TOKEN" not in kwargs["env"]
    assert not (tmp_path / "bee-zalo/auth.json").exists()
    assert not (tmp_path / "bee-zalo/.env").exists()
    assert not (tmp_path / "bee-zalo/skills").exists()
    assert "do-not-copy" not in (tmp_path / "bee-zalo/config.yaml").read_text()
    config = yaml.safe_load((tmp_path / "bee-zalo/config.yaml").read_text())
    env = config["mcp_servers"]["bee_bot"]["env"]
    assert env["BEE_BOT_ACTOR_ID"] == "${BEE_BOT_ACTOR_ID}"
    assert env["BEE_BOT_ZALO_DISPLAY_NAME"] == "${BEE_BOT_ZALO_DISPLAY_NAME}"
    assert env["BEE_BOT_CHANNEL"] == "zalo"
    assert config["platform_toolsets"] == {"acp": ["bee_bot"]}
    assert config["memory"] == {"memory_enabled": False, "user_profile_enabled": False}
    assert runner.reply("binh", incoming)["session_id"] == "s1"
    assert calls[1][0][:3] == ["hermes", "-p", "bee-zalo"]
    assert "--resume" not in calls[1][0]
    assert calls[1][1]["env"]["BEE_BOT_ACTOR_ID"] == "binh"
    named = event("m2")
    named["message"]["from"]["display_name"] = "Duy Nguyễn"
    runner.reply("an", parse_update(named))
    assert calls[2][1]["env"]["BEE_BOT_ZALO_DISPLAY_NAME"] == "Duy Nguyễn"


def test_managed_soul_embeds_bee_bot_guidance_without_skill_reference(tmp_path):
    source_profile(tmp_path)
    HermesRunner(tmp_path).prepare_profile()
    text = (tmp_path / "bee-zalo/SOUL.md").read_text()
    project = Path(__file__).resolve().parents[1]
    assert text == managed_soul(project)
    assert text.startswith(ZALO_CHANNEL_CONTEXT)
    assert 'Bot xưng "mình", gọi người đang chat là "bạn"' in text
    assert "# Hướng dẫn hội thoại Bee Bot" in text and "name: bee-bot" not in text
    assert "Đọc skill `bee-bot`" not in text
    assert "không có cập nhật Sheets hoặc gửi Zalo thật" not in text
    assert "chưa cập nhật Sheets thật" in text


def test_google_copy_profile_pins_same_backend_as_worker(tmp_path, monkeypatch):
    source_profile(tmp_path)
    private = tmp_path / 'private-sheets.json'
    monkeypatch.setenv('BEE_BOT_SCHEDULE_BACKEND', 'google_sheets_test_copy')
    monkeypatch.setenv('BEE_BOT_SHEETS_CONFIG', str(private))
    runner = HermesRunner(tmp_path)
    expected, _, soul = runner._expected()
    env = expected['mcp_servers']['bee_bot']['env']
    assert env['BEE_BOT_SCHEDULE_BACKEND'] == 'google_sheets_test_copy'
    assert env['BEE_BOT_SHEETS_CONFIG'] == str(private)
    assert 'BEE_BOT_SCHEDULE' not in env
    assert 'Google Sheets bản sao thử' in soul
    assert 'Dữ liệu ca là JSON thử' not in soul


def test_google_copy_profile_rejects_relative_private_config(tmp_path, monkeypatch):
    source_profile(tmp_path)
    monkeypatch.setenv('BEE_BOT_SCHEDULE_BACKEND', 'google_sheets_test_copy')
    monkeypatch.setenv('BEE_BOT_SHEETS_CONFIG', 'relative.json')
    with pytest.raises(BeeBotError) as error:
        HermesRunner(tmp_path)._expected()
    assert error.value.code == 'SHEETS_CONFIG_REQUIRED'


def test_json_to_google_profile_switch_requires_explicit_migration(tmp_path, monkeypatch):
    source_profile(tmp_path)
    runner = HermesRunner(tmp_path)
    runner.prepare_profile()
    profile = tmp_path / 'bee-zalo'
    before = (profile / 'config.yaml').read_bytes()
    monkeypatch.setenv('BEE_BOT_SCHEDULE_BACKEND', 'google_sheets_test_copy')
    monkeypatch.setenv('BEE_BOT_SHEETS_CONFIG', str(tmp_path / 'private.json'))
    with pytest.raises(BeeBotError) as error:
        runner.prepare_profile()
    assert error.value.code == 'ZALO_PROFILE_MIGRATION_REQUIRED'
    assert (profile / 'config.yaml').read_bytes() == before
    assert runner.prepare_profile(migrate=True) == 'bee-zalo'
    assert 'Google Sheets bản sao thử' in (profile / 'SOUL.md').read_text()
    assert list((profile / '.bee-bot-backups').iterdir())


def test_runner_labels_new_session_and_updates_name_when_resuming(tmp_path):
    source_profile(tmp_path)
    runner = HermesRunner(tmp_path)
    runner.prepare_profile()
    path = tmp_path / "bee-zalo/state.db"
    def run(command, **kwargs):
        with sqlite3.connect(path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,source TEXT,created_source TEXT,title TEXT UNIQUE,
                title_source TEXT,display_name TEXT,origin_json TEXT)""")
            db.execute("INSERT OR IGNORE INTO sessions VALUES ('s1','zalo','zalo','Tra lịch',NULL,NULL,NULL)")
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps({
            "type": "result", "session_id": "s1", "exit_code": 0, "text": "Lịch của bạn"}))
    runner.run = run
    from bee_bot.zalo import parse_update
    payload = event()
    payload["message"]["from"]["display_name"] = "Nguyễn Duy"
    runner.reply("an", parse_update(payload))
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT title FROM sessions").fetchone()[0] == "Zalo · Nguyễn Duy — Tra lịch"
    payload["message"]["from"]["display_name"] = "Duy Nguyễn"
    runner.reply("an", parse_update(payload), "s1")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT title,display_name FROM sessions").fetchone() == ("Zalo · Duy Nguyễn — Tra lịch", "Duy Nguyễn")


def test_runner_timeout_safe_error_and_profile_conflict(tmp_path):
    source_profile(tmp_path)
    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"], output="sensitive")
    runner = HermesRunner(tmp_path, run=timeout)
    from bee_bot.zalo import parse_update
    with pytest.raises(BeeBotError) as error:
        runner.reply("an", parse_update(event()))
    assert error.value.code == "HERMES_UNCERTAIN"
    assert (error.value.stage, error.value.model_may_have_run) == ("hermes", True)
    assert "sensitive" not in str(error.value)
    (tmp_path / "bee-zalo/config.yaml").write_text("model: changed\n")
    with pytest.raises(BeeBotError) as error:
        runner.prepare_profile()
    assert error.value.code == "ZALO_PROFILE_CONFLICT"


def legacy_profile(tmp_path, display_name=True):
    """Shape written by the earlier shared-profile code: skills toolset, no memory pin."""
    source_profile(tmp_path)
    runner = HermesRunner(tmp_path)
    runner.prepare_profile()
    profile = tmp_path / "bee-zalo"
    config = yaml.safe_load((profile / "config.yaml").read_text())
    config.pop("memory")
    config["platform_toolsets"] = {"acp": ["skills", "bee_bot"]}
    config["mcp_servers"]["bee_bot"]["env"].pop("BEE_BOT_CHANNEL")
    if not display_name:
        config["mcp_servers"]["bee_bot"]["env"].pop("BEE_BOT_ZALO_DISPLAY_NAME")
    config["_config_version"] = 50
    (profile / "config.yaml").write_text(yaml.safe_dump(config))
    (profile / "SOUL.md").write_text(ZALO_CHANNEL_CONTEXT + "Đọc skill `bee-bot` khi xử lý yêu cầu.")
    (profile / "skills/bee-bot").mkdir(parents=True)
    (profile / "skills/bee-bot/SKILL.md").write_text("legacy workflow")
    (profile / "skills/user-own").mkdir()
    (profile / "skills/user-own/SKILL.md").write_text("user skill")
    return runner, profile


@pytest.mark.parametrize("display_name", [True, False])
def test_legacy_profile_requires_explicit_migration_with_backup(tmp_path, display_name):
    runner, profile = legacy_profile(tmp_path, display_name)
    before = {name: (profile / name).read_bytes() for name in ("config.yaml", "SOUL.md")}
    with pytest.raises(BeeBotError) as error:
        runner.prepare_profile()
    assert error.value.code == "ZALO_PROFILE_MIGRATION_REQUIRED"
    assert {name: (profile / name).read_bytes() for name in before} == before
    assert runner.prepare_profile(migrate=True) == "bee-zalo"
    config = yaml.safe_load((profile / "config.yaml").read_text())
    assert config["_config_version"] == 50  # Hermes metadata kept.
    assert config["platform_toolsets"] == {"acp": ["bee_bot"]}
    assert config["memory"] == {"memory_enabled": False, "user_profile_enabled": False}
    assert config["mcp_servers"]["bee_bot"]["env"]["BEE_BOT_ZALO_DISPLAY_NAME"] == "${BEE_BOT_ZALO_DISPLAY_NAME}"
    assert (profile / "SOUL.md").read_text() == managed_soul(Path(__file__).resolve().parents[1])
    backups = list((profile / ".bee-bot-backups").iterdir())
    assert len(backups) == 1
    assert {name: (backups[0] / name).read_bytes() for name in before} == before
    # Skills are never deleted; they are simply not exposed to the model.
    assert (profile / "skills/user-own/SKILL.md").read_text() == "user skill"
    assert (profile / "skills/bee-bot/SKILL.md").read_text() == "legacy workflow"
    assert runner.prepare_profile() == "bee-zalo"


@pytest.mark.parametrize("drift", ["soul", "memory_on", "skills_toolset", "extra_toolset"])
def test_pinned_profile_drift_is_rejected_even_without_rewrite(tmp_path, drift):
    source_profile(tmp_path)
    runner = HermesRunner(tmp_path)
    runner.prepare_profile()
    profile = tmp_path / "bee-zalo"
    config = yaml.safe_load((profile / "config.yaml").read_text())
    if drift == "soul":
        (profile / "SOUL.md").write_text((profile / "SOUL.md").read_text() + "\nInjected rule")
    elif drift == "memory_on":
        config["memory"]["memory_enabled"] = True
    elif drift == "skills_toolset":
        config["platform_toolsets"]["acp"] = ["skills", "bee_bot"]
    else:
        config["platform_toolsets"]["acp"].append("memory")
    (profile / "config.yaml").write_text(yaml.safe_dump(config))
    before = {name: (profile / name).read_bytes() for name in ("config.yaml", "SOUL.md")}
    with pytest.raises(BeeBotError) as error:
        runner.prepare_profile()
    expected = "ZALO_PROFILE_MIGRATION_REQUIRED" if drift == "soul" else "ZALO_PROFILE_CONFLICT"
    assert error.value.code == expected
    if drift != "soul":
        with pytest.raises(BeeBotError):
            runner.prepare_profile(migrate=True)  # Unknown drift is never migrated.
    assert {name: (profile / name).read_bytes() for name in before} == before


def test_shared_profile_accepts_hermes_normalization_without_rewriting(tmp_path):
    source_profile(tmp_path)
    root_config = tmp_path.parent / "config.yaml"
    original = yaml.safe_load(root_config.read_text())
    resolved = {"base_url": "https://provider.example/api", "api_mode": "responses"}
    original["model"].update(resolved)
    root_config.write_text(yaml.safe_dump(original))
    runner = HermesRunner(tmp_path)
    runner.prepare_profile()
    path = tmp_path / "bee-zalo/config.yaml"
    config = yaml.safe_load(path.read_text())
    config["model"].update(resolved)
    config["_config_version"] = 50
    path.write_text(yaml.safe_dump(config))
    before = path.read_bytes()
    runner.prepare_profile()
    runner.prepare_profile()
    assert path.read_bytes() == before


@pytest.mark.parametrize("change", ["actor", "db", "endpoint", "toolsets", "secret", "metadata", "channel"])
def test_shared_profile_normalization_still_rejects_routing_changes(tmp_path, change):
    source_profile(tmp_path)
    root_config = tmp_path.parent / "config.yaml"
    original = yaml.safe_load(root_config.read_text())
    original["model"].update({"base_url": "https://provider.example/api", "api_mode": "responses"})
    root_config.write_text(yaml.safe_dump(original))
    runner = HermesRunner(tmp_path)
    runner.prepare_profile()
    path = tmp_path / "bee-zalo/config.yaml"
    config = yaml.safe_load(path.read_text())
    config["_config_version"] = 50
    config["model"].update(original["model"])
    config["model"].pop("api_key")
    if change == "actor":
        config["mcp_servers"]["bee_bot"]["env"]["BEE_BOT_ACTOR_ID"] = "binh"
    elif change == "db":
        config["mcp_servers"]["bee_bot"]["env"]["BEE_BOT_DB"] = "other.db"
    elif change == "endpoint":
        config["model"]["base_url"] = "https://other.example/api"
    elif change == "toolsets":
        config["platform_toolsets"]["acp"].append("terminal")
    elif change == "secret":
        config["model"]["api_key"] = "do-not-copy"
    elif change == "channel":
        config["mcp_servers"]["bee_bot"]["env"].pop("BEE_BOT_CHANNEL")
    else:
        config["_config_version"] = "50"
    path.write_text(yaml.safe_dump(config))
    before = path.read_bytes()
    for migrate in (False, True):
        with pytest.raises(BeeBotError) as error:
            runner.prepare_profile(migrate=migrate)
        assert error.value.code == "ZALO_PROFILE_CONFLICT"
    assert path.read_bytes() == before


def test_missing_stored_session_recovers_fresh_before_model(tmp_path):
    source_profile(tmp_path)
    calls = []
    runner = HermesRunner(tmp_path, run=ok_run(calls, "s-new"))
    runner.prepare_profile()
    hermes_sessions_db(tmp_path / "bee-zalo", "other")
    from bee_bot.zalo import parse_update
    result = runner.reply("an", parse_update(event()), "s-gone")
    assert result["session_recovered"] is True and result["session_id"] == "s-new"
    assert "--resume" not in calls[0][0]


@pytest.mark.parametrize("state", ["absent", "no_table", "corrupt"])
def test_unreadable_session_db_fails_closed_before_model(tmp_path, state):
    source_profile(tmp_path)
    calls = []
    runner = HermesRunner(tmp_path, run=ok_run(calls))
    runner.prepare_profile()
    path = tmp_path / "bee-zalo/state.db"
    if state == "no_table":
        sqlite3.connect(path).close()
    elif state == "corrupt":
        path.write_bytes(b"not a sqlite database" * 10)
    from bee_bot.zalo import parse_update
    with pytest.raises(BeeBotError) as error:
        runner.reply("an", parse_update(event()), "s-stored")
    assert (error.value.code, error.value.stage, error.value.model_may_have_run) == ("HERMES_SESSION_UNREADABLE", "session", False)
    assert calls == []
    assert state != "absent" or not path.exists()  # Read-only check never creates the DB.


def test_worker_recovers_session_once_and_never_retries_started_turn(tmp_path):
    source_profile(tmp_path)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if len(calls) == 2:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="provider failed")
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(
            {"type": "result", "session_id": "s-new", "exit_code": 0, "text": "ok"}))
    runner = HermesRunner(tmp_path, run=run)
    runner.prepare_profile()
    hermes_sessions_db(tmp_path / "bee-zalo", "s-new")
    client = Client()
    ingress = ZaloIngress(tmp_path / "inbox.db", identities={"sender-an": "an"}, webhook_secret="test-secret")
    w = PollingWorker(client, ingress, runner, Service())
    with w.db() as db:
        db.execute("INSERT INTO zalo_shared_sessions VALUES ('sender-an','an','chat-an','s-gone')")
    w.once()  # Stored session proven missing → fresh session, no --resume.
    client.payload = event("m2")
    w.once()  # Model turn started and failed → uncertain, not retried.
    client.payload = event("m2")
    w.once()
    assert "--resume" not in calls[0] and calls[1][-2:] == ["--resume", "s-new"]
    assert len(calls) == 2
    with w.db() as db:
        assert db.execute("SELECT session FROM zalo_shared_sessions").fetchone() == ("s-new",)
        rows = db.execute("SELECT status,result FROM zalo_inbox ORDER BY rowid").fetchall()
    assert rows[0][0] == "completed" and json.loads(rows[0][1])["session_recovered"] is True
    assert rows[1][0] == "uncertain"
    assert json.loads(rows[1][1]) == {"diagnostic": {"stage": "hermes", "error": "HERMES_UNCERTAIN", "model_may_have_run": True}}


def test_pre_model_failure_records_redacted_stage(tmp_path, caplog):
    w = worker(tmp_path)
    w.service = type("Directory", (Service,), {"get_my_assignments": lambda self, actor: (_ for _ in ()).throw(
        BeeBotError("INVALID_ACTOR", "private detail"))})()
    caplog.set_level("WARNING")
    w.once()
    assert w.runner.calls == [] and w.client.sent == []
    with w.db() as db:
        status, result = db.execute("SELECT status,result FROM zalo_inbox").fetchone()
    assert status == "uncertain"  # Still never replayed automatically.
    assert json.loads(result) == {"diagnostic": {"stage": "directory", "error": "INVALID_ACTOR", "model_may_have_run": False}}
    assert "directory" in caplog.text and "INVALID_ACTOR" in caplog.text
    assert "private detail" not in caplog.text and "Xin nghỉ" not in caplog.text


def test_profile_preflight_stops_worker_before_consuming_updates(tmp_path):
    w = worker(tmp_path)
    def conflict():
        raise BeeBotError("ZALO_PROFILE_CONFLICT", "conflict")
    w.runner.prepare_profile = conflict
    with pytest.raises(BeeBotError) as error:
        w.once()
    assert error.value.code == "ZALO_PROFILE_CONFLICT"
    with w.db() as db:
        assert db.execute("SELECT count(*) FROM zalo_inbox").fetchone() == (0,)
    assert w.runner.calls == [] and w.client.sent == []


def test_zalo_channel_mcp_mutation_requires_worker_event(tmp_path, monkeypatch):
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
    args = {"room": "A101", "description": "issue", "detected_at": "2026-10-10T08:00:00+07:00"}
    async def invoke():
        content = await server.call_tool("create_issue", args)
        content = content[0] if isinstance(content, tuple) else content
        return json.loads(content[0].text)
    monkeypatch.setenv("BEE_BOT_CHANNEL", "zalo")
    for value in (None, "", "${BEE_BOT_EVENT_ID}", "zalo:stable", "adapter:" + "a" * 64):
        if value is None:
            monkeypatch.delenv("BEE_BOT_EVENT_ID", raising=False)
        else:
            monkeypatch.setenv("BEE_BOT_EVENT_ID", value)
        assert asyncio.run(invoke())["error"] == "EVENT_CONTEXT_REQUIRED"
    assert service.ids == []
    from bee_bot.zalo import parse_update
    monkeypatch.setenv("BEE_BOT_EVENT_ID", parse_update(event()).event_id)
    assert asyncio.run(invoke())["ok"] is True
    monkeypatch.delenv("BEE_BOT_CHANNEL")
    monkeypatch.delenv("BEE_BOT_EVENT_ID")
    assert asyncio.run(invoke())["ok"] is True  # Direct Paseo demo keeps fresh UUIDs.
    assert len(service.ids) == 2 and service.ids[1].count("-") == 4


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


def test_interrupted_processing_is_reported_but_never_reset(tmp_path, caplog):
    first = worker(tmp_path)
    incoming = first.ingress.receive_polled(event())
    with first.db() as db:
        db.execute("UPDATE zalo_inbox SET status='processing' WHERE event_id=?", (incoming["event_id"],))
    caplog.set_level("WARNING")
    restarted = worker(tmp_path)
    assert "1 sự kiện Zalo dừng giữa chừng" in caplog.text
    assert "Xin nghỉ" not in caplog.text and incoming["event_id"] not in caplog.text
    restarted.client.payload = None
    restarted.once()
    assert restarted.runner.calls == [] and restarted.client.sent[:1] != [("chat-an", "Bot hỏi xác nhận")]
    with restarted.db() as db:
        assert db.execute("SELECT status,result FROM zalo_inbox").fetchone() == ("processing", None)
