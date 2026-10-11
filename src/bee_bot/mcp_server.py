"""Hermes-facing MCP tools with a trusted, fixed actor and schedule backend."""

import logging
import hashlib
import json
import os
import re
from pathlib import Path
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

from .errors import BeeBotError
from .schedule import JsonSchedule
from .schedule_factory import create_schedule

logger = logging.getLogger(__name__)


def _schedule_context(schedule):
    """Describe the service's trusted instance, never ambient backend/model input.

    Expose only policy and scope, not private workbook IDs, tabs or config paths.
    The Google factory sets backend_name on the constructed adapter.
    """
    if isinstance(schedule, JsonSchedule):
        return {"schedule": "fake_json", "schedule_backend": "json",
                "provenance": {"kind": "synthetic"},
                "live_integrations": False, "actor_is_demo_persona": True}
    from .sheets_adapter import SheetsScheduleAdapter
    if isinstance(schedule, SheetsScheduleAdapter):
        coverage = schedule.coverage()  # Public read validates the pinned provenance.
        provenance = schedule.provenance
        synthetic = provenance["kind"] == "synthetic"
        backend = getattr(schedule, "backend_name", "sheets_adapter")
        google = backend == "google_sheets_test_copy"
        return {"schedule": "google_sheets_test_copy" if google else (
                    "synthetic_sheets" if synthetic else "sheets_test_copy"),
                "schedule_backend": backend,
                "provenance": {"kind": provenance["kind"],
                               "owner_confirmed_copy": provenance.get("owner_confirmed_copy") is True,
                               "scope": coverage["scope"], "writable": coverage["writable"],
                               "compare_and_set": coverage["compare_and_set"]},
                "live_integrations": True if google else (False if synthetic else None),
                "actor_is_demo_persona": synthetic}
    raise BeeBotError("SCHEDULE_BACKEND_UNKNOWN", "Không xác định được backend lịch đã cấu hình.")


def create_server(service=None, actor_id=None):
    actor_id = actor_id or os.environ.get("BEE_BOT_ACTOR_ID")
    if not actor_id:
        raise BeeBotError("ACTOR_REQUIRED", "Cần cấu hình danh tính thử cố định qua BEE_BOT_ACTOR_ID.")
    if service is None:
        from .service import BeeBotService
        base = Path(os.environ.get("BEE_BOT_DATA_DIR", ".bee-bot")).resolve()
        schedule = create_schedule()
        service = BeeBotService(os.environ.get("BEE_BOT_DB", str(base / "state.db")), schedule)
    people = service.schedule.list_people()
    person = next((entry for entry in people if entry["person_id"] == actor_id and entry.get("active")), None)
    if person is None:
        raise BeeBotError("INVALID_ACTOR", "Danh tính thử không tồn tại hoặc đã ngừng hoạt động.")
    mcp = FastMCP("Bee Bot", instructions=(
        "Bee Bot: actor is fixed by trusted server configuration. "
        "Read get_bot_context for the configured schedule backend and provenance. "
        "Notifications are stored in a durable local outbox. "
        "Use authoritative tool results; never invent successful updates. "
        "Ask direct explicit confirmation before submitting requests or accepting invitations."
    ))

    def call(method, **kwargs):
        try:
            return {"ok": True, "result": getattr(service, method)(actor_id, **kwargs)}
        except BeeBotError as exc:
            return exc.as_dict()
        except Exception as exc:
            # Exception text/trace may contain local paths or data, so do not echo it.
            logger.error("Bee Bot tool %s failed (%s)", method, type(exc).__name__)
            return {"ok": False, "error": "INTERNAL_ERROR", "message": "Không xử lý được yêu cầu; vận hành cần kiểm tra trước khi thử lại."}

    def event_context_error():
        external_event = os.environ.get("BEE_BOT_EVENT_ID")
        # Every state-changing Zalo tool needs the worker's event context,
        # including reconciliation/maintenance that only read Sheets.
        if os.environ.get("BEE_BOT_CHANNEL") == "zalo" and not re.fullmatch(r"zalo:[0-9a-f]{64}", external_event or ""):
            return {"ok": False, "error": "EVENT_CONTEXT_REQUIRED", "message": "Thiếu mã sự kiện xác thực từ adapter; chưa thực hiện thao tác."}
        if external_event and "${" in external_event:
            return {"ok": False, "error": "EVENT_CONTEXT_REQUIRED", "message": "Thiếu mã sự kiện xác thực từ adapter; chưa thực hiện thao tác."}
        return None

    def state_call(method, **kwargs):
        error = event_context_error()
        return error if error else call(method, **kwargs)

    def mutate(method, **kwargs):
        error = event_context_error()
        if error:
            return error
        external_event = os.environ.get("BEE_BOT_EVENT_ID")
        if external_event:
            identity = json.dumps([external_event, method, kwargs], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            event_id = "adapter:" + hashlib.sha256(identity.encode()).hexdigest()
        else:
            event_id = str(uuid4())
        return call(method, event_id=event_id, **kwargs)

    @mcp.tool()
    def get_bot_context() -> dict:
        """Read the trusted actor, schedule backend and provenance. Cannot change identity or configuration."""
        try:
            current = next((entry for entry in service.schedule.list_people()
                            if entry["person_id"] == actor_id and entry.get("active")), None)
            if current is None:
                raise BeeBotError("INVALID_ACTOR", "Danh tính thử không tồn tại hoặc đã ngừng hoạt động.")
            display_name = os.environ.get("BEE_BOT_ZALO_DISPLAY_NAME", "")
            if display_name.startswith("${") or not 1 <= len(display_name) <= 80 or not display_name.isprintable():
                display_name = None
            return {"ok": True, "result": {"actor": current, **_schedule_context(service.schedule),
                                           "notifications": "durable_fake_outbox",
                                           "zalo_display_name": display_name}}
        except BeeBotError as exc:
            return exc.as_dict()
        except Exception as exc:
            logger.error("Bee Bot context failed (%s)", type(exc).__name__)
            return {"ok": False, "error": "INTERNAL_ERROR", "message": "Không đọc được danh tính thử; vận hành cần kiểm tra."}

    @mcp.tool()
    def get_my_assignments() -> dict:
        """Read the authenticated person's assignments. Ops access is enforced by service."""
        return call("get_my_assignments")

    @mcp.tool()
    def create_change_request(kind: str, assignment_id: str, substitute_id: str | None = None,
                              target_assignment_id: str | None = None, sender_confirmed: bool = False,
                              sender_no_other_busy: bool = False) -> dict:
        """Create replacement/leave/swap after the sender explicitly confirms. Swap also requires no external conflict."""
        if not sender_confirmed:
            return {"ok": False, "error": "CONFIRMATION_REQUIRED", "message": "Cần người gửi xác nhận rõ yêu cầu trước khi tạo."}
        return mutate("create_change_request", kind=kind, assignment_id=assignment_id,
                      substitute_id=substitute_id, target_assignment_id=target_assignment_id,
                      sender_confirmed=sender_confirmed, sender_no_other_busy=sender_no_other_busy)

    @mcp.tool()
    def get_request_status(request_id: str) -> dict:
        """Read a request only when the fixed actor is permitted to see it."""
        return call("get_request_status", request_id=request_id)

    @mcp.tool()
    def list_my_requests() -> dict:
        """List requests visible to the fixed actor; ops can review all requests."""
        return call("list_my_requests")

    @mcp.tool()
    def add_substitute(request_id: str, substitute_id: str) -> dict:
        """Owner adds a substitute to a leave awaiting approval. Keeps ID, alerts ops, changes to replacement."""
        return mutate("add_substitute", request_id=request_id, substitute_id=substitute_id)

    @mcp.tool()
    def approve_leave_request(request_id: str) -> dict:
        """Ops approves leave without a substitute, allowing invitations to eligible coaches."""
        return mutate("approve_leave_request", request_id=request_id)

    @mcp.tool()
    def nominate_replacement(request_id: str, substitute_id: str) -> dict:
        """Ops nominates a recipient, who must still confirm directly in their own session."""
        return mutate("nominate_replacement", request_id=request_id, substitute_id=substitute_id)

    @mcp.tool()
    def get_my_invitations() -> dict:
        """Read invitations addressed to this authenticated person."""
        return call("get_my_invitations")

    @mcp.tool()
    def respond_to_invitation(invitation_id: str, accept: bool, no_other_busy: bool = False) -> dict:
        """Accept/reject directly as recipient. Both accept and no_other_busy must be explicit for allocation."""
        return mutate("respond_to_invitation", invitation_id=invitation_id, accept=accept, no_other_busy=no_other_busy)

    @mcp.tool()
    def cancel_request(request_id: str, reason: str) -> dict:
        """Owner or ops cancels before updating. Completed schedule changes cannot be reversed here."""
        return mutate("cancel_request", request_id=request_id, reason=reason)

    @mcp.tool()
    def withdraw_leave_approval(request_id: str, reason: str) -> dict:
        """Ops withdraws leave approval with a reason; uncertain writes must first be reconciled."""
        return mutate("withdraw_leave_approval", request_id=request_id, reason=reason)

    @mcp.tool()
    def reconcile_request(request_id: str) -> dict:
        """Ops reads actual schedule results after uncertain writes. Never blindly retries or rolls back."""
        return state_call("reconcile_request", request_id=request_id)

    @mcp.tool()
    def create_issue(room: str, description: str, detected_at: str, photo: str | None = None,
                     related_issue_id: str | None = None) -> dict:
        """Report an issue with room, description and offset-aware ISO detection time. Photo optional."""
        return mutate("create_issue", room=room, description=description, detected_at=detected_at,
                      photo=photo, related_issue_id=related_issue_id)

    @mcp.tool()
    def get_issue_status(issue_id: str) -> dict:
        """Issue recorder or ops reads issue status."""
        return call("get_issue_status", issue_id=issue_id)

    @mcp.tool()
    def update_issue(issue_id: str, status: str, result: str | None = None) -> dict:
        """Ops processes/resolves/cancels an issue; recorder may cancel before processing. Resolution needs result."""
        return mutate("update_issue", issue_id=issue_id, status=status, result=result)

    @mcp.tool()
    def get_my_notifications() -> dict:
        """Read simulated durable notifications for the fixed actor. No real Zalo delivery."""
        return call("get_my_notifications")

    @mcp.tool()
    def run_maintenance() -> dict:
        """Ops expires invitations, flags urgent requests, produces due summaries and safely reconciles writes."""
        return state_call("run_maintenance")

    return mcp


def main():
    logging.basicConfig(level=logging.WARNING)
    try:
        create_server().run(transport="stdio")
    except BeeBotError as exc:
        logger.error("Bee Bot MCP could not start: %s — %s", exc.code, exc.message)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
