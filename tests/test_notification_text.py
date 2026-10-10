from bee_bot.errors import BeeBotError
from bee_bot.notification_text import render_notification


class AuthorizedService:
    def get_my_invitations(self, actor):
        assert actor == "binh"
        return [{"invitation_id": "IV1", "status": "pending", "expires_at": "2026-10-11T17:00:00+07:00", "assignments": [{"assignment_id": "A1", "starts_at": "2026-10-12T09:00:00+07:00", "ends_at": "2026-10-12T13:00:00+07:00", "room": "A101", "site": "Cơ sở A"}], "private_leave_reason": "must-not-show"}]
    def get_request_status(self, actor, request_id):
        assert actor in {"an", "ops"}
        return {"status": "completed", "reason": "must-not-show"}
    def get_issue_status(self, actor, issue_id):
        assert actor in {"an", "ops"}
        return {"status": "resolved", "room": "A101", "result": "Đã thay dây máy chiếu"}


def test_invitation_authorized_shows_shift_deadline_two_confirmations():
    text = render_notification(AuthorizedService(), "binh", {"event": "invitation", "request_id": "YC1", "invitation_id": "IV1", "recipient_id": "binh", "delivery_status": "pending"})
    for expected in ["YC1", "12/10/2026 09:00", "13:00", "A101", "11/10/2026 17:00", "đồng ý nhận ca", "không bận ngoài chương trình"]:
        assert expected in text
    for hidden in ["must-not-show", "recipient_id", "delivery_status", "invitation", '{"']:
        assert hidden not in text


def test_completed_request_and_issue_human_text():
    service = AuthorizedService()
    text = render_notification(service, "an", {"event": "request_completed", "request_id": "YC1"})
    assert "YC1 đã hoàn tất cập nhật lịch" in text
    assert "must-not-show" not in text
    issue = render_notification(service, "ops", {"event": "issue_updated", "issue_id": "IS1"})
    assert "IS1 tại phòng A101 đã giải quyết" in issue
    assert "Đã thay dây máy chiếu" in issue
    assert '{"' not in issue


def test_permission_denied_generic_does_not_reveal_data():
    class Denied:
        def get_request_status(self, actor, request_id):
            raise BeeBotError("FORBIDDEN", "private-details")
    text = render_notification(Denied(), "chi", {"event": "request_completed", "request_id": "PRIVATE1"})
    assert "Có cập nhật dành cho bạn" in text
    assert "PRIVATE1" not in text
    assert "private-details" not in text


def test_closed_invitation_not_offered_again():
    class Closed(AuthorizedService):
        def get_my_invitations(self, actor):
            return [{"invitation_id": "IV1", "status": "expired"}]
    text = render_notification(Closed(), "binh", {"event": "invitation", "request_id": "YC1", "invitation_id": "IV1"})
    assert "đã đóng" in text
    assert "đồng ý nhận ca" not in text


def test_summary_includes_authorized_open_issues_only():
    class Summary:
        def list_my_requests(self, actor):
            return []
        def get_issue_status(self, actor, issue_id):
            assert actor == "ops"
            if issue_id == "hidden":
                raise BeeBotError("FORBIDDEN", "private")
            return {"status": "resolved" if issue_id == "closed" else "processing"}
    text = render_notification(Summary(), "ops", {"event": "pending_summary", "issue_ids": ["open", "open", "closed", "hidden"]})
    assert "0 yêu cầu và 1 sự cố đang mở" in text
    assert "hidden" not in text
