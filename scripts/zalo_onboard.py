#!/usr/bin/env python3
"""Explicit owner-operated Bot API checks; no signup or unsolicited messages."""

import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import dotenv_values

from bee_bot.errors import BeeBotError
from bee_bot.zalo import ZaloBotClient, parse_update

ALLOWED_ENV = {"ZALO_BOT_TOKEN", "ZALO_WEBHOOK_SECRET", "BEE_BOT_ZALO_IDENTITIES", "BEE_BOT_ZALO_INBOX"}


def main():
    parser = argparse.ArgumentParser(description="Read-only Bot API check or link an explicitly selected local demo persona")
    parser.add_argument("command", choices=("check", "identify"))
    parser.add_argument("--env-file", type=Path, default=Path(".bee-bot/zalo.env"))
    parser.add_argument("--actor", choices=("an", "binh", "chi", "dung", "ops"), help="Explicit local demo identity to link from the next private test message")
    parser.add_argument("--verification-file", type=Path, default=Path(".bee-bot/link-code.txt"), help="Private one-time text the known tester sends to the bot for identity linking")
    args = parser.parse_args()
    client = None
    try:
        values = dotenv_values(args.env_file, interpolate=False) if args.env_file.exists() else {}
        config = {key: os.environ.get(key) or values.get(key) for key in ALLOWED_ENV}
        if not config.get("ZALO_BOT_TOKEN"):
            raise BeeBotError("ZALO_CONFIG", "Chưa có token bot; tạo bot trong Zalo Bot Manager rồi cấu hình tệp riêng. Chưa gọi API.")
        if args.command == "identify" and not args.actor:
            raise BeeBotError("ACTOR_REQUIRED", "Chọn --actor rõ ràng để liên kết danh tính thử.")
        verification = None
        if args.command == "identify":
            verification = args.verification_file.read_text().strip()
            if len(verification) < 16:
                raise BeeBotError("VERIFICATION_REQUIRED", "Cần mã liên kết riêng dài ít nhất 16 ký tự do tài khoản thử gửi tới bot.")
        client = ZaloBotClient(config["ZALO_BOT_TOKEN"])
        info = client.get_webhook_info()
        if not isinstance(info, dict) or "url" not in info:
            raise BeeBotError("ZALO_CONFIG", "Chưa xác định được cấu hình webhook của bot.")
        if args.command == "check":
            me = client.get_me()
            if not isinstance(me, dict):
                raise BeeBotError("ZALO_INVALID_RESPONSE", "Không xác minh được thông tin bot.")
            print(json.dumps({"ok": True, "bot_id": me.get("id"), "bot_name": me.get("display_name") or me.get("name") or me.get("account_name"), "webhook_configured": bool(info.get("url")), "message_sent": False}, ensure_ascii=False))
            return
        if info.get("url"):
            raise BeeBotError("ZALO_WEBHOOK_ACTIVE", "Bot đang có webhook; không tự xóa để lấy sender ID bằng polling.")
        mapping_path = config.get("BEE_BOT_ZALO_IDENTITIES")
        if not mapping_path:
            raise BeeBotError("ZALO_CONFIG", "Cần cấu hình đường dẫn tệp danh tính riêng.")
        payload = client.get_updates(timeout=30)
        if not payload:
            raise BeeBotError("NO_TEST_MESSAGE", "Chưa có tin thử; gửi một tin riêng tới bot rồi chạy lại.")
        incoming = parse_update(payload)
        if incoming.text.strip() != verification:
            raise BeeBotError("VERIFICATION_MISMATCH", "Tin tiếp nhận chưa khớp mã liên kết riêng; chưa liên kết tài khoản nào.")
        path = Path(mapping_path)
        mapping = json.loads(path.read_text()) if path.exists() else {}
        if not isinstance(mapping, dict):
            raise BeeBotError("ZALO_CONFIG", "Tệp danh tính phải là đối tượng JSON.")
        if incoming.sender_id in mapping and mapping[incoming.sender_id] != args.actor:
            raise BeeBotError("ZALO_IDENTITY_CHANGED", "Tài khoản đã có liên kết khác; đối chiếu trước khi đổi.")
        if any(actor == args.actor and sender != incoming.sender_id for sender, actor in mapping.items()):
            raise BeeBotError("ZALO_IDENTITY_CHANGED", "Persona này đã liên kết với tài khoản khác.")
        mapping[incoming.sender_id] = args.actor
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n")
        path.chmod(0o600)
        args.verification_file.unlink()  # One-time challenge cannot register another sender later.
        print(json.dumps({"ok": True, "linked_demo_actor": args.actor, "mapping_file": str(path), "message_sent": False, "note": "Chỉ dùng tin của tài khoản thử đã được người quản trị đối chiếu; không phải liên kết người dùng production."}, ensure_ascii=False))
    except BeeBotError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from None
    except (OSError, ValueError):
        print(json.dumps({"ok": False, "error": "ZALO_CONFIG", "message": "Không đọc/ghi được cấu hình riêng; chưa gửi tin."}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    main()
