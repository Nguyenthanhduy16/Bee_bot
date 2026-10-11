"""Presentation metadata for worker-owned Zalo sessions in Hermes's profile DB.

Hermes CLI currently accepts a source but no sender label. Its UI renders the
session title, so prefix that title and retain the topic in namespaced metadata.
Do not change Hermes authentication, transport routing, or message history.
"""

import hashlib
from contextlib import closing
import json
import logging
from pathlib import Path
import sqlite3
import unicodedata

from .errors import BeeBotError

logger = logging.getLogger(__name__)
METADATA_KEY = "bee_bot_zalo"
MAX_TITLE_LENGTH = 100  # Hermes SessionDB's title limit.


def _clean_name(value):
    if not isinstance(value, str):
        return None
    value = " ".join("".join(char for char in value
                             if unicodedata.category(char) not in {"Cc", "Cf", "Cs"}).split())
    return value if 1 <= len(value) <= 80 else None


def label_zalo_session(profile, session_id, event):
    """Label an existing session; missing/incompatible DB is a nonfatal UI failure.

    An existing peer binding must match, even if both peers share a display name.
    The sender comes from the verified worker event, never from model text.
    """
    path = Path(profile) / "state.db"
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, timeout=5)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT source,created_source,title,display_name,origin_json FROM sessions WHERE id=?",
                (session_id,),
            ).fetchone()
            if row is None:
                return False
            if "zalo" not in row[:2]:
                raise BeeBotError("ZALO_IDENTITY_CHANGED", "Session không thuộc kênh Zalo đã xác thực.")
            origin = json.loads(row[4]) if row[4] else {}
            if not isinstance(origin, dict):
                raise ValueError
            old = origin.get(METADATA_KEY, {})
            if not isinstance(old, dict):
                raise ValueError
            if old and (old.get("sender_id"), old.get("chat_id")) != (event.sender_id, event.chat_id):
                raise BeeBotError("ZALO_IDENTITY_CHANGED", "Session đã liên kết với người gửi hoặc chat khác.")
            name = _clean_name(event.display_name) or (_clean_name(row[3]) if old else None)
            fallback = hashlib.sha256(event.sender_id.encode()).hexdigest()[:8]
            header = "Zalo · " + (name or f"Người dùng {fallback}")
            title = row[2] or ""
            topic = old.get("topic", "") if title == old.get("title") else title
            if not isinstance(topic, str):
                raise ValueError
            # A compression continuation can inherit our title plus a #N suffix.
            previous_header = old.get("header")
            if previous_header and topic.startswith(previous_header + " — "):
                topic = topic[len(previous_header) + 3:]
            base = header + (" — " + topic if topic else "")
            title = base[:MAX_TITLE_LENGTH]
            number = 1
            while db.execute("SELECT 1 FROM sessions WHERE title=? AND id<>?", (title, session_id)).fetchone():
                number += 1
                suffix = f" #{number}"
                title = base[:MAX_TITLE_LENGTH - len(suffix)] + suffix
            origin[METADATA_KEY] = {"sender_id": event.sender_id, "chat_id": event.chat_id,
                                    "header": header, "topic": topic, "title": title}
            db.execute(
                "UPDATE sessions SET title=?,title_source='user',display_name=?,origin_json=? WHERE id=?",
                (title, name, json.dumps(origin, ensure_ascii=False), session_id),
            )
        return True
    except (OSError, sqlite3.Error, ValueError, TypeError):
        # A presentation failure must not discard a model reply or replay a mutation.
        logger.warning("Không cập nhật được nhãn session Zalo trong Hermes; giữ phản hồi và lịch sử.")
        return False
