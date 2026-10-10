import pytest

from bee_bot.errors import BeeBotError


def test_fake_schedule_rejects_manual_change_between_read_and_write(env):
    before = env.schedule.get_assignment("a1")
    env.edit("a1", coach_id="chi")
    with pytest.raises(BeeBotError) as exc:
        env.schedule.apply_updates({"a1": "binh"}, {"a1": before})
    assert exc.value.code == "SCHEDULE_CHANGED"
    assert env.schedule.get_assignment("a1")["coach_id"] == "chi"


def test_fake_schedule_validates_entire_swap_before_any_change(env):
    expected = {key: env.schedule.get_assignment(key) for key in ("a1", "a2")}
    env.edit("a2", room="H205")
    with pytest.raises(BeeBotError):
        env.schedule.apply_updates({"a1": "binh", "a2": "an"}, expected)
    assert env.schedule.get_assignment("a1")["coach_id"] == "an"
    assert env.schedule.get_assignment("a2")["coach_id"] == "binh"


def test_fake_schedule_j_only_change_is_preserved(env):
    before = env.schedule.get_assignment("a1")
    env.edit("a1", j="Edited manually")
    env.schedule.apply_updates({"a1": "binh"}, {"a1": before})
    assert env.schedule.get_assignment("a1")["j"] == "Edited manually"
    assert env.schedule.get_assignment("a1")["coach_id"] == "binh"
