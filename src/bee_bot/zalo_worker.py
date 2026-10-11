"""Explicitly launched first Zalo test: polling, real Hermes, fake schedule."""

import argparse
from copy import deepcopy
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import fcntl
import json
import logging
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile

import yaml
from dotenv import dotenv_values

from .errors import BeeBotError
from .hermes_sessions import label_zalo_session
from .service import BeeBotService
from .schedule_factory import create_schedule
from .notification_text import render_notification
from .zalo import ZaloBotClient, ZaloIngress

logger = logging.getLogger(__name__)


ZALO_CHANNEL_CONTEXT = """# Kênh thử Zalo — hội thoại thật, lịch JSON giả

Bot xưng "mình", gọi người đang chat là "bạn" hoặc tên hiển thị Zalo do `get_bot_context` trả về. Tên này chỉ để xưng hô, không cấp quyền. Tên của actor trong lịch JSON là vai thử, không phải tên thật của người đang chat: không gọi người dùng là An/Bình/Chi/Dũng chỉ vì actor đó được liên kết. Nếu họ hỏi danh tính, nói rõ tên hiển thị Zalo và vai thử đang dùng lịch giả; không khẳng định họ chính là persona thử.

Bạn đang trả lời người dùng qua chat riêng Zalo, bằng Hermes và model thật. Worker dùng Bot API thật để chuyển phản hồi tới người đang nhắn. Dữ liệu ca là JSON thử, chưa ghi Google Sheets thật.
Kết quả MCP về thông báo/outbox chỉ chứng minh đã ghi nhận thông báo, không chứng minh API đã gửi hoặc người nhận đã đọc. Mô tả 'fake notifications/no live integrations' trong công cụ nói về dữ liệu/lớp MCP, không có nghĩa kênh chat Zalo bên ngoài là giả lập. Không tự báo đã giao thông báo cho bên khác khi chưa có kết quả giao được kiểm chứng. Giữ nguyên quy tắc danh tính, quyền, xác nhận trực tiếp và kết quả nghiệp vụ authoritative bên dưới.

"""


SKILL_REFERENCE = "Đọc skill `bee-bot` khi xử lý yêu cầu."
MEMORY_DISABLED = {"memory_enabled": False, "user_profile_enabled": False}


def managed_soul(project, backend="json"):
    """Deterministic SOUL for the shared profile; Bee Bot guidance is embedded.

    The shared profile has no skill toolset, so senders cannot create or patch
    instructions that other senders' sessions would load.
    """
    if backend not in {"json", "google_sheets_test_copy"}:
        raise BeeBotError("SCHEDULE_BACKEND_INVALID", "Backend lịch không được hỗ trợ.")
    soul = (project / "examples/SOUL.md").read_text(encoding="utf-8")
    if backend == "google_sheets_test_copy":
        context = ZALO_CHANNEL_CONTEXT.replace(
            "Kênh thử Zalo — hội thoại thật, lịch JSON giả", "Kênh thử Zalo — hội thoại thật, lịch Google Sheets bản sao")
        context = context.replace("Tên của actor trong lịch JSON là vai thử", "Tên của actor trong lịch thử là vai đã xác thực")
        context = context.replace("vai thử đang dùng lịch giả", "vai đã xác thực đang dùng bản sao thử")
        context = context.replace("Dữ liệu ca là JSON thử, chưa ghi Google Sheets thật.",
                                  "Dữ liệu ca lấy từ Google Sheets bản sao thử. Chỉ tin kết quả cập nhật do Bee Bot MCP xác nhận.")
        replacement = "Đây là Google Sheets bản sao thử; chỉ báo đã cập nhật khi Bee Bot MCP xác nhận. Thông báo outbox chưa tự chứng minh đã giao qua Zalo."
    else:
        context = ZALO_CHANNEL_CONTEXT
        replacement = "Đây là lịch JSON thử, chưa cập nhật Sheets thật. Thông báo ghi trong outbox chưa tự chứng minh đã giao qua Zalo."
    soul = soul.replace("Đây là lịch JSON và thông báo giả lập, không có cập nhật Sheets hoặc gửi Zalo thật.",
                        replacement)
    soul = soul.replace(SKILL_REFERENCE, "Làm theo hướng dẫn hội thoại Bee Bot ở cuối tài liệu này.")
    skill = (project / "examples/skills/bee-bot/SKILL.md").read_text(encoding="utf-8")
    if skill.startswith("---\n"):
        skill = skill.split("\n---\n", 1)[1]
    return context + soul.rstrip() + "\n\n" + skill.strip() + "\n"


class StageError(BeeBotError):
    """Handler failure with a redacted stage; message text and causes are not kept."""

    def __init__(self, stage, code, model_may_have_run):
        super().__init__(code, f"Xử lý tin Zalo dừng ở bước {stage}.")
        self.stage, self.model_may_have_run = stage, model_may_have_run


@contextmanager
def stage(name, model_may_have_run):
    try:
        yield
    except StageError:
        raise
    except BeeBotError as exc:
        raise StageError(name, exc.code, model_may_have_run) from None
    except Exception as exc:
        raise StageError(name, type(exc).__name__, model_may_have_run) from None


def _atomic_write(path, text):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
        file.write(text)
        temporary = file.name
    try:
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class HermesRunner:
    PROFILE = "bee-zalo"
    TOOLSETS = "bee_bot"

    def __init__(self, profiles_root=None, executable="hermes", timeout=180, run=subprocess.run, state_dir=None):
        self.root = Path(profiles_root or Path.home() / ".hermes/profiles")
        self.executable, self.timeout, self.run = executable, timeout, run
        self.state_dir = Path(state_dir).resolve() if state_dir is not None else None

    def _expected(self):
        original = yaml.safe_load((self.root.parent / "config.yaml").read_text()) or {}
        model = original.get("model")
        if not isinstance(model, dict) or not model.get("provider") or not model.get("default"):
            raise ValueError
        project = Path(__file__).resolve().parents[2]
        state = self.state_dir or project / ".bee-bot"
        schedule_env = {"BEE_BOT_SCHEDULE": str(state / "schedule.json")}
        backend = os.environ.get("BEE_BOT_SCHEDULE_BACKEND", "json")
        if backend == "google_sheets_test_copy":
            config_path = os.environ.get("BEE_BOT_SHEETS_CONFIG")
            if not config_path or not Path(config_path).is_absolute():
                raise BeeBotError("SHEETS_CONFIG_REQUIRED", "Cần đường dẫn tuyệt đối tới cấu hình Sheets riêng ngoài Git.")
            schedule_env = {"BEE_BOT_SCHEDULE_BACKEND": backend, "BEE_BOT_SHEETS_CONFIG": config_path}
        elif backend != "json":
            raise BeeBotError("SCHEDULE_BACKEND_INVALID", "Backend lịch không được hỗ trợ.")
        config = {
            "model": {key: model[key] for key in ("default", "provider")},
            "mcp_servers": {"bee_bot": {
                "command": str(project / ".venv/bin/python"),
                "args": ["-m", "bee_bot.mcp_server"],
                "timeout": 30,
                "supports_parallel_tool_calls": False,
                "env": {"BEE_BOT_ACTOR_ID": "${BEE_BOT_ACTOR_ID}",
                        "BEE_BOT_EVENT_ID": "${BEE_BOT_EVENT_ID}",
                        "BEE_BOT_ZALO_DISPLAY_NAME": "${BEE_BOT_ZALO_DISPLAY_NAME}",
                        "BEE_BOT_CHANNEL": "zalo",
                        "BEE_BOT_DB": str(state / "state.db"),
                        **schedule_env},
            }},
            "platform_toolsets": {"acp": [self.TOOLSETS]},
            "memory": dict(MEMORY_DISABLED),
        }
        return config, model, managed_soul(project, backend)

    @staticmethod
    def _legacy(config):
        """Exact shapes written by the earlier shared-profile code."""
        legacy = deepcopy(config)
        legacy.pop("memory")
        legacy["platform_toolsets"] = {"acp": ["skills", "bee_bot"]}
        legacy["mcp_servers"]["bee_bot"]["env"].pop("BEE_BOT_CHANNEL")
        without_name = deepcopy(legacy)
        without_name["mcp_servers"]["bee_bot"]["env"].pop("BEE_BOT_ZALO_DISPLAY_NAME")
        return [legacy, without_name]

    @staticmethod
    def _schedule_switch(current, target, current_soul):
        """Accept only a known JSON ↔ test-copy profile change, with clean SOUL."""
        try:
            previous = deepcopy(current)
            desired = deepcopy(target)
            old_env = previous['mcp_servers']['bee_bot']['env']
            new_env = desired['mcp_servers']['bee_bot']['env']
            old_backend = old_env.pop('BEE_BOT_SCHEDULE_BACKEND', 'json')
            new_backend = new_env.pop('BEE_BOT_SCHEDULE_BACKEND', 'json')
            old_config = old_env.pop('BEE_BOT_SHEETS_CONFIG', None)
            new_config = new_env.pop('BEE_BOT_SHEETS_CONFIG', None)
            old_json = old_env.pop('BEE_BOT_SCHEDULE', None)
            new_json = new_env.pop('BEE_BOT_SCHEDULE', None)
            valid_old = ((old_backend == 'json' and old_json and old_config is None)
                         or (old_backend == 'google_sheets_test_copy' and old_config and old_json is None))
            valid_new = ((new_backend == 'json' and new_json and new_config is None)
                         or (new_backend == 'google_sheets_test_copy' and new_config and new_json is None))
            project = Path(__file__).resolve().parents[2]
            return (bool(valid_old and valid_new and old_backend != new_backend)
                    and previous == desired and current_soul == managed_soul(project, old_backend))
        except (KeyError, TypeError, ValueError):
            return False

    @staticmethod
    def _comparable(installed, model):
        comparable = deepcopy(installed)
        if isinstance(comparable, dict):
            # Hermes persists schema metadata and resolved provider settings
            # when this profile is opened. Only accept known additions that
            # match the trusted root; MCP routing, env, toolsets and memory stay exact.
            version = comparable.get("_config_version")
            if type(version) is int and version > 0:
                comparable.pop("_config_version")
            installed_model = comparable.get("model")
            if isinstance(installed_model, dict):
                for key in ("base_url", "api_mode"):
                    if key in model and installed_model.get(key) == model[key]:
                        installed_model.pop(key)
        return comparable

    def prepare_profile(self, migrate=False):
        """Verify pinned config/SOUL; create when absent. Never deletes skills or history.

        A legacy profile is changed only with migrate=True, after a backup of the
        two managed files. Any other drift is a conflict, migration or not.
        """
        name = self.PROFILE
        target = self.root / name
        try:
            config, model, soul = self._expected()
            if target.exists():
                installed = yaml.safe_load((target / "config.yaml").read_text())
                comparable = self._comparable(installed, model)
                current_soul = (target / "SOUL.md").read_text(encoding="utf-8")
                if comparable == config and current_soul == soul:
                    return name
                if (comparable != config and comparable not in self._legacy(config)
                        and not self._schedule_switch(comparable, config, current_soul)):
                    raise BeeBotError("ZALO_PROFILE_CONFLICT", "Profile Zalo thử đã có cấu hình khác; cần kiểm tra trước khi dùng.")
                if not migrate:
                    raise BeeBotError("ZALO_PROFILE_MIGRATION_REQUIRED",
                                      "Profile Zalo cần chuyển đổi tường minh (--migrate-profile) trước khi dùng.")
                backup = target / ".bee-bot-backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                backup.mkdir(parents=True, mode=0o700)
                for managed in ("config.yaml", "SOUL.md"):
                    shutil.copy2(target / managed, backup / managed)
                # Keep Hermes-added metadata; replace only routing, toolsets and memory.
                for key in ("mcp_servers", "platform_toolsets", "memory"):
                    installed[key] = deepcopy(config[key])
                _atomic_write(target / "config.yaml", yaml.safe_dump(installed, allow_unicode=True))
                _atomic_write(target / "SOUL.md", soul)
                return name
            self.root.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".bee-zalo-", dir=self.root))
            try:
                (staging / "config.yaml").write_text(yaml.safe_dump(config, allow_unicode=True))
                (staging / "SOUL.md").write_text(soul, encoding="utf-8")
                staging.rename(target)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
        except BeeBotError:
            raise
        except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError):
            raise BeeBotError("ZALO_CONFIG", "Cần model Hermes gốc và cấu hình Bee Bot hợp lệ trước khi chạy Zalo.") from None
        return name

    def session_exists(self, profile, session_id):
        """Trusted read-only lookup; unreadable or malformed DB fails closed."""
        path = self.root / profile / "state.db"
        try:
            with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as db:
                return db.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone() is not None
        except (OSError, sqlite3.Error):
            raise BeeBotError("HERMES_SESSION_UNREADABLE", "Không đọc được danh sách session Hermes; chưa chạy model.") from None

    def reply(self, actor, event, session_id=None):
        with stage("prepare", False):
            profile = self.prepare_profile()
        recovered = False
        if session_id:
            with stage("session", False):
                if not self.session_exists(profile, session_id):
                    # Proven absent before any model call: start fresh, never after.
                    logger.warning("Session Hermes đã lưu không còn; bắt đầu session mới trước khi chạy model.")
                    session_id, recovered = None, True
                else:
                    label_zalo_session(self.root / profile, session_id, event)
        command = [self.executable, "-p", profile, "chat", "--oneshot", "--source", "zalo", "--format", "stream-json", "-t", self.TOOLSETS, "--query-file", "-", "--max-turns", "12"]
        if session_id:
            command.extend(["--resume", session_id])
        env = dict(os.environ, BEE_BOT_ACTOR_ID=actor, BEE_BOT_EVENT_ID=event.event_id,
                   BEE_BOT_ZALO_DISPLAY_NAME=event.display_name or "")
        for key in ("ZALO_BOT_TOKEN", "ZALO_WEBHOOK_SECRET"):
            env.pop(key, None)
        with stage("hermes", True):
            try:
                process = self.run(command, input=event.text, text=True, capture_output=True, env=env, timeout=self.timeout)
                results = [json.loads(line) for line in process.stdout.splitlines() if line.startswith("{")]
                result = next(item for item in reversed(results) if item.get("type") == "result")
                if process.returncode or result.get("exit_code") or not result.get("session_id") or not result.get("text"):
                    raise ValueError
            except (OSError, subprocess.TimeoutExpired, ValueError, StopIteration):
                raise BeeBotError("HERMES_UNCERTAIN", "Hermes chưa xác nhận kết quả; cần đối chiếu, không tự chạy lại.") from None
        with stage("label", True):
            label_zalo_session(self.root / profile, result["session_id"], event)
        return {"text": result["text"][:2000], "session_id": result["session_id"], "session_recovered": recovered}


class PollingWorker:
    def __init__(self, client, ingress, runner, service):
        self.client, self.ingress, self.runner, self.service = client, ingress, runner, service
        actors = list(ingress._identities.values())
        if len(actors) != len(set(actors)):
            raise BeeBotError("ZALO_CONFIG", "Bản thử cần đúng một tài khoản Zalo cho mỗi person ID.")
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS zalo_sessions (sender TEXT PRIMARY KEY, actor TEXT NOT NULL, chat TEXT NOT NULL, session TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS zalo_shared_sessions (sender TEXT PRIMARY KEY, actor TEXT NOT NULL, chat TEXT NOT NULL, session TEXT UNIQUE)")
            # Preserve legacy profile sessions; only carry over verified chat routing.
            db.execute("INSERT OR IGNORE INTO zalo_shared_sessions (sender,actor,chat,session) "
                       "SELECT sender,actor,chat,NULL FROM zalo_sessions")
            db.execute("CREATE TABLE IF NOT EXISTS zalo_deliveries (id TEXT PRIMARY KEY, status TEXT NOT NULL)")
            interrupted = db.execute("SELECT count(*) FROM zalo_inbox WHERE status='processing'").fetchone()[0]
        if interrupted:
            # A crash mid-handler leaves no stage; the model may have run. Never reset or replay.
            logger.warning("%d sự kiện Zalo dừng giữa chừng (processing); vận hành cần đối chiếu, không tự phát lại.", interrupted)

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.ingress.path, timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def check_polling(self):
        info = self.client.get_webhook_info()
        if not isinstance(info, dict) or "url" not in info or info.get("url"):
            raise BeeBotError("ZALO_WEBHOOK_ACTIVE", "Bot đang có webhook hoặc trạng thái chưa rõ; không tự xóa để polling.")

    def deliver(self, delivery_id, chat, text):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM zalo_deliveries WHERE id=?", (delivery_id,)).fetchone()
            if row:
                return row[0]
            db.execute("INSERT INTO zalo_deliveries VALUES (?,'sending')", (delivery_id,))
        try:
            self.client.send_message(chat, text[:2000])
            status = "sent"
        except Exception:
            status = "uncertain"
        with self.db() as db:
            db.execute("UPDATE zalo_deliveries SET status=? WHERE id=?", (status, delivery_id))
        return status

    def handle(self, actor, event):
        with stage("directory", False):
            self.service.get_my_assignments(actor)  # Revalidate current service directory.
        with stage("session_lookup", False), self.db() as db:
            row = db.execute("SELECT actor,chat,session FROM zalo_shared_sessions WHERE sender=?", (event.sender_id,)).fetchone()
            if row and row[:2] != (actor, event.chat_id):
                raise BeeBotError("ZALO_IDENTITY_CHANGED", "Danh tính hoặc chat đã đổi; cần đối chiếu.")
            if not row:
                db.execute("INSERT INTO zalo_shared_sessions VALUES (?,?,?,NULL)", (event.sender_id, actor, event.chat_id))
        with stage("hermes", True):
            result = self.runner.reply(actor, event, row[2] if row else None)
        with stage("session_store", True), self.db() as db:
            db.execute("INSERT INTO zalo_shared_sessions VALUES (?,?,?,?) ON CONFLICT(sender) DO UPDATE SET session=excluded.session", (event.sender_id, actor, event.chat_id, result["session_id"]))
        result["delivery_status"] = self.deliver("reply:" + event.event_id, event.chat_id, result["text"])
        return result

    def flush_notifications(self):
        with self.db() as db:
            recipients = db.execute("SELECT sender,actor,chat FROM zalo_shared_sessions").fetchall()
        for sender, actor, chat in recipients:
            if self.ingress._identities.get(sender) != actor:
                continue
            try:
                notifications = self.service.get_my_notifications(actor)
            except BeeBotError:
                continue
            for notification in notifications:
                identifier = notification.get("notification_id", notification.get("id"))
                text = render_notification(self.service, actor, notification)
                self.deliver("notification:" + identifier, chat, text)

    def once(self):
        self.check_polling()
        # A profile conflict stops the worker before any update is consumed.
        self.runner.prepare_profile()
        payload = self.client.get_updates(timeout=30)
        if payload:
            try:
                received = self.ingress.receive_polled(payload)
            except BeeBotError as exc:
                if exc.code not in {"ZALO_UNKNOWN_USER", "ZALO_UNSUPPORTED_EVENT", "ZALO_UNSUPPORTED_CHAT"}:
                    raise
        with self.db() as db:
            pending = db.execute("SELECT event_id FROM zalo_inbox WHERE status='pending' ORDER BY rowid").fetchall()
        for (event_id,) in pending:
            self.ingress.process(event_id, self.handle)
        self.flush_notifications()


def main():
    parser = argparse.ArgumentParser(description="First Zalo polling test: real Hermes, fake JSON schedule")
    parser.add_argument("--state-dir", type=Path, default=Path(".bee-bot"))
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--env-file", type=Path, help="Explicit private Zalo configuration file; never loaded implicitly")
    parser.add_argument("--migrate-profile", action="store_true",
                        help="Back up and migrate a legacy dedicated bee-zalo profile, then exit; no Zalo/model call")
    args = parser.parse_args()
    client = service = None
    try:
        if args.migrate_profile:
            profile = HermesRunner(state_dir=args.state_dir).prepare_profile(migrate=True)
            print(json.dumps({"ok": True, "profile": profile, "message_sent": False}, ensure_ascii=False))
            return
        if args.env_file:
            if not args.env_file.is_file():
                raise BeeBotError("ZALO_CONFIG", "Không đọc được tệp cấu hình Zalo đã chọn.")
            try:
                values = dotenv_values(args.env_file, interpolate=False)
            except (OSError, UnicodeError):
                raise BeeBotError("ZALO_CONFIG", "Không đọc được tệp cấu hình Zalo đã chọn.") from None
            for key in {"ZALO_BOT_TOKEN", "ZALO_WEBHOOK_SECRET", "BEE_BOT_ZALO_IDENTITIES", "BEE_BOT_ZALO_INBOX",
                        "BEE_BOT_SCHEDULE_BACKEND", "BEE_BOT_SHEETS_CONFIG"}:
                if values.get(key) is not None:
                    os.environ[key] = values[key]
        token = os.environ.get("ZALO_BOT_TOKEN")
        mapping_path = os.environ.get("BEE_BOT_ZALO_IDENTITIES")
        if not token or not mapping_path:
            raise BeeBotError("ZALO_CONFIG", "Cần tài khoản bot/token và tệp danh tính trước khi chạy Zalo; hiện chưa gửi gì.")
        try:
            mapping = json.loads(Path(mapping_path).read_text())
        except (OSError, ValueError):
            raise BeeBotError("ZALO_CONFIG", "Không đọc được tệp danh tính Zalo.") from None
        args.state_dir.mkdir(parents=True, exist_ok=True)
        with (args.state_dir / "zalo-worker.lock").open("a") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise BeeBotError("ZALO_WORKER_RUNNING", "Đã có worker Zalo chạy trong thư mục trạng thái này.") from None
            ingress = ZaloIngress(os.environ.get("BEE_BOT_ZALO_INBOX", str(args.state_dir / "zalo-inbox.db")), identities=mapping, webhook_secret=os.environ.get("ZALO_WEBHOOK_SECRET", ""))
            service = BeeBotService(args.state_dir / "state.db", create_schedule(args.state_dir / "schedule.json"))
            runner = HermesRunner(state_dir=args.state_dir)
            for actor in set(mapping.values()):
                service.get_my_assignments(actor)
            runner.prepare_profile()
            client = ZaloBotClient(token)
            worker = PollingWorker(client, ingress, runner, service)
            while True:
                worker.once()
                if args.once:
                    break
    except BeeBotError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        pass
    finally:
        if client:
            client.close()
        if service:
            service.close()


if __name__ == "__main__":
    main()
