"""Hermes-facing MCP tools with one trusted, fixed local demo identity."""

import logging
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

from .errors import BeeBotError
from .schedule import JsonSchedule

logger = logging.getLogger(__name__)


def create_server(service=None, actor_id=None):
    actor_id = actor_id or os.environ.get("BEE_BOT_ACTOR_ID")
    if not actor_id:
        raise BeeBotError("ACTOR_REQUIRED", "Cần cấu hình danh tính thử cố định qua BEE_BOT_ACTOR_ID.")
    if service is None:
        from .service import BeeBotService
        base = Path(os.environ.get("BEE_BOT_DATA_DIR", ".bee-bot")).resolve()
        schedule = JsonSchedule(os.environ.get("BEE_BOT_SCHEDULE", str(base / "schedule.json")))
        service = BeeBotService(os.environ.get("BEE_BOT_DB", str(base / "state.db")), schedule)
    people = service.schedule.list_people()
    person = next((entry for entry in people if entry["person_id"] == actor_id and entry.get("active")), None)
    if person is None:
        raise BeeBotError("INVALID_ACTOR", "Danh tính thử không tồn tại hoặc đã ngừng hoạt động.")
    mcp = FastMCP("Bee Bot", instructions=(
        "Bee Bot local prototype: actor is fixed by trusted server configuration. "
        "Fake schedule and notifications only, no live Sheets/Zalo. "
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

    def mutate(method, **kwargs):
        external_event = os.environ.get("BEE_BOT_EVENT_ID")
        if external_event and "${" in external_event:
            return {"ok": False, "error": "EVENT_CONTEXT_REQUIRED", "message": "Thiếu mã sự kiện xác thực từ adapter; chưa thực hiện thao tác."}
        if external_event:
            identity = json.dumps([external_event, method, kwargs], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            event_id = "adapter:" + hashlib.sha256(identity.encode()).hexdigest()
        else:
            event_id = str(uuid4())
        return call(method, event_id=event_id, **kwargs)

    @mcp.tool()
    def get_bot_context() -> dict:
        """Identify the configured local demo persona and simulation boundaries. Cannot change identity."""
        try:
            current = next((entry for entry in service.schedule.list_people()
                            if entry["person_id"] == actor_id and entry.get("active")), None)
            if current is None:
                raise BeeBotError("INVALID_ACTOR", "Danh tính thử không tồn tại hoặc đã ngừng hoạt động.")
            return {"ok": True, "result": {"actor": current, "schedule": "fake_json", "notifications": "durable_fake_outbox", "live_integrations": False}}
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
        """Read invitations addressed to this authenticated demo persona."""
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
        return call("reconcile_request", request_id=request_id)

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
        return call("run_maintenance")

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
