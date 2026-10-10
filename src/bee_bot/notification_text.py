"""Recipient-authorized Vietnamese notification text; no raw metadata dump."""
from datetime import datetime
from zoneinfo import ZoneInfo

from .errors import BeeBotError

ZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def when(value, fmt="%d/%m/%Y %H:%M"):
    time = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if time.tzinfo is None:
        raise ValueError("Timezone required")
    return time.astimezone(ZONE).strftime(fmt)


def render_notification(service, actor, notification):
    """Read only service-authorized data. Candidate text never includes leave reason."""
    event = notification.get("event")
    request_id, issue_id = notification.get("request_id"), notification.get("issue_id")
    prefix = "Bee Bot thử (lịch giả): "
    try:
        if event == "invitation":
            invitation = next((item for item in service.get_my_invitations(actor)
                               if item["invitation_id"] == notification.get("invitation_id")), None)
            if not invitation or invitation["status"] not in {"pending", "incomplete"}:
                return prefix + f"Lời mời cho yêu cầu {request_id} đã đóng. Hãy hỏi bot trạng thái hiện tại."
            lines = [f"Bạn có lời mời nhận ca cho yêu cầu {request_id}:"]
            for assignment in invitation["assignments"]:
                lines.append(f"Ca {assignment['assignment_id']}: {when(assignment['starts_at'])}–{when(assignment['ends_at'], '%H:%M')}, phòng {assignment['room']}, {assignment['site']}.")
            lines.extend([f"Hạn xác nhận: {when(invitation['expires_at'])} (giờ Việt Nam).",
                          "Hãy trả lời trực tiếp: bạn đồng ý nhận ca và không bận ngoài chương trình, hoặc từ chối. Chưa xác nhận đủ hai điều thì chưa giữ ca."])
            return prefix + "\n".join(lines)
        if issue_id:
            issue = service.get_issue_status(actor, issue_id)
            label = {"open": "đã ghi nhận", "processing": "đang xử lý", "resolved": "đã giải quyết", "cancelled": "đã hủy"}.get(issue["status"], "có cập nhật")
            text = f"Sự cố {issue_id} tại phòng {issue['room']} {label}."
            if issue["status"] == "resolved" and issue.get("result"):
                text += " Kết quả: " + str(issue["result"])
            return prefix + text + " Bạn có thể hỏi bot chi tiết mã sự cố."
        if request_id:
            request = service.get_request_status(actor, request_id)
            status = request["status"]
            labels = {
                "waiting_ops_approval": "đang chờ vận hành chấp nhận nghỉ; chưa mời người thay",
                "waiting_confirmation": "đang chờ người nhận xác nhận trực tiếp",
                "searching": "đang tìm người nhận ca sau khi vận hành chấp nhận nghỉ",
                "completed": "đã hoàn tất cập nhật lịch",
                "cancelled": "đã hủy",
                "approval_withdrawn": "đã rút chấp nhận nghỉ; dừng tìm người thay",
                "needs_ops": "cần vận hành kiểm tra và bố trí tiếp",
                "write_failed": "chưa xác nhận cập nhật lịch thành công; cần vận hành kiểm tra",
                "reconciliation_required": "đang chờ vận hành đối chiếu kết quả ghi lịch",
                "updating": "đang cập nhật và kiểm tra lại lịch",
                "reserved": "đã giữ vị trí, đang chờ đối chiếu kết quả",
                "expired": "đã hết hạn",
            }
            text = f"Yêu cầu {request_id} {labels.get(status, 'có cập nhật')}."
            if event == "substitute_added":
                text += " Người gửi đã bổ sung người thay; chuyển sang nhận thay, người nhận vẫn cần xác nhận trực tiếp."
            elif event == "invitation_declined":
                text += " Người được mời đã từ chối."
            elif event in {"invitation_expired", "invitation_closed"}:
                text += " Lời mời nhận ca đã đóng."
            elif event == "schedule_conflict":
                text += " Bạn có lịch trùng nên chưa thể nhận ca này."
            elif event == "shift_within_two_hours":
                text += " Ca bắt đầu trong vòng hai giờ; vận hành cần xử lý sớm."
            elif event == "shift_started_unfilled":
                text += " Ca đã bắt đầu mà chưa có người thay hoàn tất."
            return prefix + text + " Hãy hỏi bot trạng thái mã yêu cầu để xem bước tiếp theo."
        if event == "pending_summary":
            # Counts/IDs only after ops-authorized public service calls.
            requests = service.list_my_requests(actor)
            open_issues = 0
            for identifier in set(notification.get("issue_ids", [])):
                try:
                    issue = service.get_issue_status(actor, identifier)
                    open_issues += issue["status"] not in {"resolved", "cancelled"}
                except BeeBotError:
                    continue
            return prefix + f"Đến giờ tổng hợp: còn {sum(item['status'] not in {'completed', 'cancelled', 'approval_withdrawn', 'expired'} for item in requests)} yêu cầu và {open_issues} sự cố đang mở. Hãy hỏi bot danh sách cần xử lý."
    except (BeeBotError, ValueError, KeyError, TypeError, AttributeError):
        pass
    return prefix + "Có cập nhật dành cho bạn. Hãy hỏi bot danh sách thông báo hoặc trạng thái yêu cầu."
