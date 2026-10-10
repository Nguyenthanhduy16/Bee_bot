"""Local development commands; these are not user identity authentication."""

from __future__ import annotations

import argparse
import inspect
import json
import sys
import time
from pathlib import Path
from uuid import uuid4

from bee_bot.errors import BeeBotError


def main() -> None:
    parser = argparse.ArgumentParser(description="Bee Bot local prototype (fake Sheets/Zalo)")
    parser.add_argument("--state-dir", type=Path, default=Path(".bee-bot"))
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init-demo", help="Create future demo schedule without resetting requests")
    init.add_argument("--overwrite", action="store_true", help="Replace only demo schedule; use a new state directory for a fresh scenario")
    commands.add_parser("show-schedule", help="View the local fake sheet")
    source = commands.add_parser("import-xlsx", help="Normalize a read-only XLSX snapshot into a separate local file")
    source.add_argument("input", type=Path)
    source.add_argument("--output", type=Path, default=None)
    worker = commands.add_parser("worker", help="Run expiry/reconciliation/summary maintenance on local fake data")
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--interval", type=float, default=30.0)
    call = commands.add_parser("call", help="Invoke a service method as a trusted local demo persona")
    call.add_argument("method")
    call.add_argument("--actor", required=True, choices=("an", "binh", "chi", "dung", "ops"))
    call.add_argument("--args", default="{}", help="JSON keyword arguments (actor_id cannot be overridden)")
    call.add_argument("--event-id", help="External event id for deterministic replay tests")
    args = parser.parse_args()
    try:
        from bee_bot.fixtures import write_demo_schedule
        from bee_bot.schedule import JsonSchedule

        schedule_path = args.state_dir.resolve() / "schedule.json"
        if args.command == "init-demo":
            if not schedule_path.exists() or args.overwrite:
                write_demo_schedule(schedule_path, overwrite=args.overwrite)
            result = {"ok": True, "schedule": str(schedule_path), "state_dir": str(args.state_dir.resolve()), "simulated": True}
        elif args.command == "import-xlsx":
            from bee_bot.sheets_import import write_snapshot
            output = args.output or args.state_dir.resolve() / "source" / "normalized.json"
            result = {"ok": True, "result": write_snapshot(args.input, output), "source_modified": False}
        else:
            schedule = JsonSchedule(schedule_path)
            if args.command == "show-schedule":
                result = {"ok": True, "assignments": schedule.list_assignments(), "simulated": True}
            else:
                from bee_bot.service import BeeBotService

                service = BeeBotService(args.state_dir.resolve() / "state.db", schedule)
                if args.command == "worker":
                    if args.interval < 1:
                        raise BeeBotError("INVALID_ARGUMENTS", "Worker interval phải ít nhất 1 giây.")
                    try:
                        while True:
                            print(json.dumps(service.run_maintenance("ops"), ensure_ascii=False), flush=True)
                            if args.once:
                                return
                            time.sleep(args.interval)
                    except KeyboardInterrupt:
                        return
                    finally:
                        service.close()
                allowed = {
                    "get_my_assignments", "create_change_request", "get_request_status", "list_my_requests",
                    "add_substitute", "approve_leave_request", "nominate_replacement", "get_my_invitations",
                    "respond_to_invitation", "cancel_request", "withdraw_leave_approval", "reconcile_request",
                    "create_issue", "get_issue_status", "update_issue", "get_my_notifications", "run_maintenance",
                }
                if args.method not in allowed:
                    raise BeeBotError("UNKNOWN_METHOD", "Công cụ không tồn tại.")
                payload = json.loads(args.args)
                if not isinstance(payload, dict) or "actor_id" in payload:
                    raise BeeBotError("INVALID_ARGUMENTS", "Danh tính thử lấy từ --actor; không truyền actor_id trong --args.")
                method = getattr(service, args.method)
                if "event_id" in inspect.signature(method).parameters:
                    payload["event_id"] = args.event_id or payload.get("event_id") or str(uuid4())
                result = {"ok": True, "result": method(actor_id=args.actor, **payload), "simulated": True}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except BeeBotError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
    except (ValueError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": "INVALID_ARGUMENTS", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
