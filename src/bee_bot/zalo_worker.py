"""Explicitly launched first Zalo test: polling, real Hermes, fake schedule."""

import argparse
from copy import deepcopy
from contextlib import contextmanager
import fcntl
import json
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
from .service import BeeBotService
from .schedule import JsonSchedule
from .notification_text import render_notification
from .zalo import ZaloBotClient, ZaloIngress


ZALO_CHANNEL_CONTEXT = """# Kênh thử Zalo — hội thoại thật, lịch JSON giả

Bạn đang trả lời người dùng qua chat riêng Zalo, bằng Hermes và model thật. Worker dùng Bot API thật để chuyển phản hồi tới người đang nhắn. Dữ liệu ca là JSON thử, chưa ghi Google Sheets thật.
Kết quả MCP về thông báo/outbox chỉ chứng minh đã ghi nhận thông báo, không chứng minh API đã gửi hoặc người nhận đã đọc. Mô tả 'fake notifications/no live integrations' trong công cụ nói về dữ liệu/lớp MCP, không có nghĩa kênh chat Zalo bên ngoài là giả lập. Không tự báo đã giao thông báo cho bên khác khi chưa có kết quả giao được kiểm chứng. Giữ nguyên quy tắc danh tính, quyền, xác nhận trực tiếp và kết quả nghiệp vụ authoritative bên dưới.

"""


def update_channel_context(profile):
    """Update only the dedicated Zalo SOUL; no config, credentials or session edits."""
    path = Path(profile) / "SOUL.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("Đây là lịch JSON và thông báo giả lập, không có cập nhật Sheets hoặc gửi Zalo thật.",
                        "Đây là lịch JSON thử, chưa cập nhật Sheets thật. Thông báo ghi trong outbox chưa tự chứng minh đã giao qua Zalo.")
    if not text.startswith("# Kênh thử Zalo —"):
        text = ZALO_CHANNEL_CONTEXT + text
    if path.read_text(encoding="utf-8") != text:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
            file.write(text)
            temporary = file.name
        os.replace(temporary, path)


class HermesRunner:
    def __init__(self, profiles_root=None, executable="hermes", timeout=180, run=subprocess.run, state_dir=None):
        self.root = Path(profiles_root or Path.home() / ".hermes/profiles")
        self.executable, self.timeout, self.run = executable, timeout, run
        self.state_dir = Path(state_dir).resolve() if state_dir is not None else None

    def prepare_profile(self, actor):
        if actor not in {"an", "binh", "chi", "dung", "ops"}:
            raise BeeBotError("ZALO_CONFIG", "Bản thử chỉ hỗ trợ persona demo đã cấu hình.")
        name, source = f"bee-zalo-{actor}", self.root / f"bee-bot-{actor}"
        target = self.root / name
        try:
            original = yaml.safe_load((source / "config.yaml").read_text())
            bee = deepcopy(original["mcp_servers"]["bee_bot"])
            if bee["env"]["BEE_BOT_ACTOR_ID"] != actor:
                raise ValueError
            bee["env"]["BEE_BOT_EVENT_ID"] = "${BEE_BOT_EVENT_ID}"
            if self.state_dir:
                bee["env"].update(BEE_BOT_DB=str(self.state_dir / "state.db"), BEE_BOT_SCHEDULE=str(self.state_dir / "schedule.json"))
            model = original.get("model")
            if isinstance(model, dict):
                model = {k: model[k] for k in ("default", "provider") if k in model}
            config = {"model": model, "mcp_servers": {"bee_bot": bee}, "platform_toolsets": {"acp": ["skills", "bee_bot"]}}
            if isinstance(original.get("provider"), str):
                config["provider"] = original["provider"]
            if target.exists():
                if yaml.safe_load((target / "config.yaml").read_text()) != config:
                    raise BeeBotError("ZALO_PROFILE_CONFLICT", "Profile Zalo thử đã có cấu hình khác; cần kiểm tra trước khi dùng.")
                update_channel_context(target)
                return name
            self.root.mkdir(parents=True, exist_ok=True)
            stage = Path(tempfile.mkdtemp(prefix=".bee-zalo-", dir=self.root))
            try:
                (stage / "config.yaml").write_text(yaml.safe_dump(config, allow_unicode=True))
                shutil.copyfile(source / "SOUL.md", stage / "SOUL.md")
                update_channel_context(stage)
                skill = source / "skills/bee-bot/SKILL.md"
                (stage / "skills/bee-bot").mkdir(parents=True)
                shutil.copyfile(skill, stage / "skills/bee-bot/SKILL.md")
                stage.rename(target)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)
        except BeeBotError:
            raise
        except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError):
            raise BeeBotError("ZALO_CONFIG", "Cần profile Bee Bot demo đúng cấu hình trước khi chạy Zalo.") from None
        return name

    def reply(self, actor, event, session_id=None):
        profile = self.prepare_profile(actor)
        command = [self.executable, "-p", profile, "chat", "--oneshot", "--source", "zalo", "--format", "stream-json", "-t", "skills,bee_bot", "--query-file", "-", "--max-turns", "12"]
        if session_id:
            command.extend(["--resume", session_id])
        env = dict(os.environ, BEE_BOT_EVENT_ID=event.event_id)
        for key in ("ZALO_BOT_TOKEN", "ZALO_WEBHOOK_SECRET"):
            env.pop(key, None)
        try:
            process = self.run(command, input=event.text, text=True, capture_output=True, env=env, timeout=self.timeout)
            results = [json.loads(line) for line in process.stdout.splitlines() if line.startswith("{")]
            result = next(item for item in reversed(results) if item.get("type") == "result")
            if process.returncode or result.get("exit_code") or not result.get("session_id") or not result.get("text"):
                raise ValueError
        except (OSError, subprocess.TimeoutExpired, ValueError, StopIteration):
            raise BeeBotError("HERMES_UNCERTAIN", "Hermes chưa xác nhận kết quả; cần đối chiếu, không tự chạy lại.") from None
        return {"text": result["text"][:2000], "session_id": result["session_id"]}


class PollingWorker:
    def __init__(self, client, ingress, runner, service):
        self.client, self.ingress, self.runner, self.service = client, ingress, runner, service
        actors = list(ingress._identities.values())
        if len(actors) != len(set(actors)):
            raise BeeBotError("ZALO_CONFIG", "Bản thử cần đúng một tài khoản Zalo cho mỗi person ID.")
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS zalo_sessions (sender TEXT PRIMARY KEY, actor TEXT NOT NULL, chat TEXT NOT NULL, session TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS zalo_deliveries (id TEXT PRIMARY KEY, status TEXT NOT NULL)")

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
        self.service.get_my_assignments(actor)  # Revalidate current service directory.
        with self.db() as db:
            row = db.execute("SELECT actor,chat,session FROM zalo_sessions WHERE sender=?", (event.sender_id,)).fetchone()
            if row and row[:2] != (actor, event.chat_id):
                raise BeeBotError("ZALO_IDENTITY_CHANGED", "Danh tính hoặc chat đã đổi; cần đối chiếu.")
            if not row:
                db.execute("INSERT INTO zalo_sessions VALUES (?,?,?,NULL)", (event.sender_id, actor, event.chat_id))
        result = self.runner.reply(actor, event, row[2] if row else None)
        with self.db() as db:
            db.execute("INSERT INTO zalo_sessions VALUES (?,?,?,?) ON CONFLICT(sender) DO UPDATE SET session=excluded.session", (event.sender_id, actor, event.chat_id, result["session_id"]))
        result["delivery_status"] = self.deliver("reply:" + event.event_id, event.chat_id, result["text"])
        return result

    def flush_notifications(self):
        with self.db() as db:
            recipients = db.execute("SELECT sender,actor,chat FROM zalo_sessions").fetchall()
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
    args = parser.parse_args()
    client = service = None
    try:
        if args.env_file:
            if not args.env_file.is_file():
                raise BeeBotError("ZALO_CONFIG", "Không đọc được tệp cấu hình Zalo đã chọn.")
            try:
                values = dotenv_values(args.env_file, interpolate=False)
            except (OSError, UnicodeError):
                raise BeeBotError("ZALO_CONFIG", "Không đọc được tệp cấu hình Zalo đã chọn.") from None
            for key in {"ZALO_BOT_TOKEN", "ZALO_WEBHOOK_SECRET", "BEE_BOT_ZALO_IDENTITIES", "BEE_BOT_ZALO_INBOX"}:
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
            service = BeeBotService(args.state_dir / "state.db", JsonSchedule(args.state_dir / "schedule.json"))
            runner = HermesRunner(state_dir=args.state_dir)
            for actor in set(mapping.values()):
                service.get_my_assignments(actor)
                runner.prepare_profile(actor)
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
