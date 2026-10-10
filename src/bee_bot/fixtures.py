"""Synthetic Vietnamese demo data, generated relative to the initialization date."""

from datetime import datetime, timedelta
import json
from pathlib import Path
from zoneinfo import ZoneInfo


def demo_data(now=None):
    now = now or datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Demo initialization date must include a timezone")
    day = now.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).replace(hour=0, minute=0, second=0, microsecond=0)
    people = [
        {"person_id": person_id, "display_name": name, "role": role, "active": True}
        for person_id, name, role in [
            ("an", "An", "labcoach"), ("binh", "Bình", "labcoach"),
            ("chi", "Chi", "labcoach"), ("dung", "Dũng", "labcoach"),
            ("ops", "Vận hành", "ops"),
        ]
    ]
    assignments = []
    for assignment_id, offset, hour, coach, room in [
        ("A001", 2, 9, "an", "A101"), ("A002", 2, 9, "chi", "A102"),
        ("A003", 2, 14, "binh", "A101"), ("A004", 2, 14, "dung", "A102"),
        ("A005", 3, 9, "an", "A101"), ("A006", 3, 14, "chi", "A102"),
        ("A007", 4, 9, "binh", "A101"), ("A008", 4, 14, "dung", "A102"),
    ]:
        start = day + timedelta(days=offset, hours=hour)
        assignments.append({
            "assignment_id": assignment_id, "shift_id": f"{start.date()}-{'AM' if hour < 12 else 'PM'}-{room}",
            "coach_id": coach, "starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=4)).isoformat(),
            "room": room, "site": "Cơ sở A", "class_name": f"Lớp thử {room}",
            "j": f"Ghi chú vận hành {assignment_id} — giữ nguyên", "revision": 1,
        })
    return {"people": people, "assignments": assignments, "demo_initialized_at": now.isoformat()}


def write_demo_schedule(path, now=None, overwrite=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "x"
    with path.open(mode, encoding="utf-8") as handle:
        json.dump(demo_data(now), handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path
