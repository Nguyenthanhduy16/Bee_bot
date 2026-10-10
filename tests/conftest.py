import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from bee_bot.schedule import JsonSchedule
from bee_bot.service import BeeBotService


@pytest.fixture
def env(tmp_path):
    now = datetime(2026, 10, 10, 8, tzinfo=timezone(timedelta(hours=7)))
    clock = SimpleNamespace(now=now)
    people = [
        {"person_id": person, "display_name": person.title(), "role": "ops" if person == "ops" else "labcoach", "active": True}
        for person in ("an", "binh", "chi", "dung", "ops")
    ]
    people.append({"person_id": "inactive", "display_name": "Inactive", "role": "labcoach", "active": False})

    def assignment(key, coach, day, hour=9, j="Chưa cập nhật"):
        start = now.replace(hour=hour) + timedelta(days=day)
        return {"assignment_id": key, "shift_id": f"shift-{key}", "coach_id": coach,
                "starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=4)).isoformat(),
                "room": "H210", "site": "A", "class_name": f"Class {key}", "j": j, "revision": 1}

    payload = {"people": people, "assignments": [
        assignment("a1", "an", 3), assignment("a2", "binh", 3, 14, "Bận"),
        assignment("a3", "chi", 4), assignment("a4", "dung", 5),
    ]}
    path = tmp_path / "schedule.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    schedule = JsonSchedule(path)
    db = tmp_path / "bee.sqlite3"
    service = BeeBotService(db, schedule, clock=lambda: clock.now)

    def edit(assignment_id, **updates):
        data = json.loads(path.read_text(encoding="utf-8"))
        row = next(row for row in data["assignments"] if row["assignment_id"] == assignment_id)
        row.update(updates)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    return SimpleNamespace(service=service, schedule=schedule, db=db, path=path,
                           clock=clock, edit=edit, payload=payload, assignment=assignment)


def create(env, actor="an", kind="replacement", assignment_id="a1", event_id="create-1", **kwargs):
    options = {"sender_confirmed": True}
    if kind == "replacement":
        options["substitute_id"] = "binh"
    if kind == "swap":
        options.update(target_assignment_id="a2", sender_no_other_busy=True)
    options.update(kwargs)
    return env.service.create_change_request(actor, kind, assignment_id, event_id, **options)


def invitation(env, actor, request):
    return next(item for item in env.service.get_my_invitations(actor)
                if item["request_id"] == request["request_id"])


def respond(env, actor, request, event_id="respond-1", accept=True, no_other_busy=True):
    item = invitation(env, actor, request)
    return env.service.respond_to_invitation(actor, item["invitation_id"], accept, no_other_busy, event_id)
