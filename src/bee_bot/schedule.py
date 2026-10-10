"""Local JSON sheet emulator. Its advisory lock is not a Google Sheets lock."""

from contextlib import contextmanager
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import tempfile

from .errors import BeeBotError


class JsonSchedule:
    """Read fake schedules and conditionally change only column D (coach_id)."""

    SIGNATURE_FIELDS = (
        "assignment_id", "shift_id", "coach_id", "starts_at", "ends_at",
        "room", "site", "class_name", "revision",
    )

    def __init__(self, path):
        self.path = Path(path)
        self.next_write_fault = None

    @contextmanager
    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix(self.path.suffix + ".lock").open("a") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _read(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data.get("people"), list) or not isinstance(data.get("assignments"), list):
                raise ValueError("Invalid schedule structure")
            return data
        except (OSError, ValueError, AttributeError) as exc:
            raise BeeBotError("SCHEDULE_UNAVAILABLE", "Không đọc được lịch thử; cần kiểm tra tệp dữ liệu.") from exc

    def _write(self, data):
        tmp_name = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as tmp:
                tmp_name = tmp.name
                json.dump(data, tmp, ensure_ascii=False, indent=2)
                tmp.write("\n")
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, self.path)
        except OSError as exc:
            raise BeeBotError("WRITE_UNCERTAIN", "Không xác minh được việc ghi lịch; cần đọc lại kết quả.") from exc
        finally:
            if tmp_name and os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def list_people(self):
        with self._locked():
            return deepcopy(self._read()["people"])

    def list_assignments(self):
        with self._locked():
            return deepcopy(self._read()["assignments"])

    def get_assignment(self, assignment_id):
        for assignment in self.list_assignments():
            if assignment["assignment_id"] == assignment_id:
                return assignment
        raise BeeBotError("ASSIGNMENT_NOT_FOUND", "Không tìm thấy ca được yêu cầu.")

    def apply_updates(self, updates, expected):
        with self._locked():
            data = self._read()
            rows = {row["assignment_id"]: row for row in data["assignments"]}
            active_coaches = {person["person_id"] for person in data["people"]
                              if person.get("active") and person.get("role") == "labcoach"}
            for assignment_id, coach_id in updates.items():
                current, original = rows.get(assignment_id), expected.get(assignment_id)
                if current is None or original is None or any(
                    current.get(field) != original.get(field) for field in self.SIGNATURE_FIELDS
                ):
                    raise BeeBotError("SCHEDULE_CHANGED", "Lịch đã thay đổi; dừng cập nhật để đối chiếu lại.")
                if coach_id not in active_coaches:
                    raise BeeBotError("INVALID_SUBSTITUTE", "Người nhận ca không phải labcoach đang hoạt động.")
            fault, self.next_write_fault = self.next_write_fault, None
            if fault == "failure":
                raise BeeBotError("WRITE_FAILED", "Ghi lịch thất bại; dữ liệu chưa được thay đổi.")
            if fault == "timeout_before":
                raise BeeBotError("WRITE_UNCERTAIN", "Ghi lịch hết thời gian chờ; cần đối chiếu dữ liệu thực tế.")
            selected = list(updates.items())
            if fault == "partial":
                selected = selected[:1]
            for assignment_id, coach_id in selected:
                rows[assignment_id]["coach_id"] = coach_id
                rows[assignment_id]["revision"] = rows[assignment_id].get("revision", 0) + 1
            self._write(data)
            if fault in {"timeout_after", "partial"}:
                raise BeeBotError("WRITE_UNCERTAIN", "Kết quả ghi chưa chắc chắn; cần đọc lại mọi ca liên quan.")
