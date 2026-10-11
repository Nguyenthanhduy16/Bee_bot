"""Hermes session presentation; no API/model traffic or authentication changes."""

from dataclasses import replace
import json
import sqlite3

import pytest

from bee_bot.errors import BeeBotError
from bee_bot.hermes_sessions import label_zalo_session
from bee_bot.zalo import IncomingText


@pytest.fixture
def profile(tmp_path):
    with sqlite3.connect(tmp_path / "state.db") as db:
        db.execute("""CREATE TABLE sessions (
            id TEXT PRIMARY KEY, source TEXT, created_source TEXT, title TEXT UNIQUE,
            title_source TEXT, display_name TEXT, origin_json TEXT,
            user_id TEXT, session_key TEXT, chat_id TEXT)""")
        db.execute("INSERT INTO sessions (id,source,created_source,title,origin_json) VALUES (?,?,?,?,?)",
                   ("s1", "zalo", "zalo", "Xem lịch cá nhân", '{"existing":"keep"}'))
    return tmp_path


def incoming(name="Nguyễn Duy", sender="sender-duy"):
    return IncomingText("zalo:e1", sender, "chat-duy", "m1", "Xem lịch", None, name)


def session(profile, sid="s1"):
    with sqlite3.connect(profile / "state.db") as db:
        db.row_factory = sqlite3.Row
        return dict(db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone())


def test_sender_label_preserves_topic_origin_and_authentication(profile):
    assert label_zalo_session(profile, "s1", incoming())
    row = session(profile)
    assert row["title"] == "Zalo · Nguyễn Duy — Xem lịch cá nhân"
    assert row["display_name"] == "Nguyễn Duy"
    assert row["title_source"] == "user"  # Hermes's auto-titler cannot erase the label.
    origin = json.loads(row["origin_json"])
    assert origin["existing"] == "keep"
    assert origin["bee_bot_zalo"]["sender_id"] == "sender-duy"
    assert all(row[key] is None for key in ("user_id", "session_key", "chat_id"))
    assert label_zalo_session(profile, "s1", incoming())
    assert session(profile) == row


def test_name_changes_and_missing_name_retain_topic(profile):
    label_zalo_session(profile, "s1", incoming())
    label_zalo_session(profile, "s1", incoming("Duy Nguyễn"))
    assert session(profile)["title"] == "Zalo · Duy Nguyễn — Xem lịch cá nhân"
    label_zalo_session(profile, "s1", incoming(None))
    assert session(profile)["display_name"] == "Duy Nguyễn"
    with sqlite3.connect(profile / "state.db") as db:
        db.execute("UPDATE sessions SET title='Tra yêu cầu' WHERE id='s1'")
    label_zalo_session(profile, "s1", incoming())
    assert session(profile)["title"] == "Zalo · Nguyễn Duy — Tra yêu cầu"


@pytest.mark.parametrize("event", [incoming(sender="other"), replace(incoming(), chat_id="other")])
def test_same_name_does_not_allow_different_sender_or_chat(profile, event):
    label_zalo_session(profile, "s1", incoming())
    before = session(profile)
    with pytest.raises(BeeBotError, match="Session đã liên kết"):
        label_zalo_session(profile, "s1", event)
    assert session(profile) == before


def test_non_zalo_session_cannot_be_relabelled(profile):
    with sqlite3.connect(profile / "state.db") as db:
        db.execute("UPDATE sessions SET source='desktop',created_source='desktop' WHERE id='s1'")
    with pytest.raises(BeeBotError):
        label_zalo_session(profile, "s1", incoming())


def test_unknown_name_uses_stable_sender_label_and_same_name_titles_are_unique(profile):
    label_zalo_session(profile, "s1", incoming(None))
    assert session(profile)["title"].startswith("Zalo · Người dùng ")
    assert session(profile)["display_name"] is None
    label_zalo_session(profile, "s1", incoming())
    with sqlite3.connect(profile / "state.db") as db:
        db.execute("INSERT INTO sessions (id,source,created_source) VALUES ('s2','zalo','zalo')")
        db.execute("UPDATE sessions SET title='Xem lịch cá nhân' WHERE id='s2'")
    label_zalo_session(profile, "s2", incoming(sender="another-duy"))
    assert session(profile, "s2")["title"] == "Zalo · Nguyễn Duy — Xem lịch cá nhân #2"
    label_zalo_session(profile, "s2", incoming(sender="another-duy"))
    assert session(profile, "s2")["title"] == "Zalo · Nguyễn Duy — Xem lịch cá nhân #2"


def test_long_names_and_control_characters_fit_hermes_title_limit(profile):
    label_zalo_session(profile, "s1", incoming("Duy\u202e\u200b Nguyễn"))
    assert session(profile)["display_name"] == "Duy Nguyễn"
    label_zalo_session(profile, "s1", incoming("D" * 80))
    assert len(session(profile)["title"]) <= 100
    assert json.loads(session(profile)["origin_json"])["bee_bot_zalo"]["topic"] == "Xem lịch cá nhân"


def test_missing_db_or_schema_does_not_create_fake_session(tmp_path):
    assert label_zalo_session(tmp_path, "missing", incoming()) is False
    assert not (tmp_path / "state.db").exists()
    with sqlite3.connect(tmp_path / "state.db") as db:
        db.execute("CREATE TABLE unrelated (id TEXT)")
    assert label_zalo_session(tmp_path, "missing", incoming()) is False
