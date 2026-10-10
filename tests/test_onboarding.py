"""Owner-assisted demo linking never trusts an arbitrary pending message."""

import importlib.util
import json
from pathlib import Path
import sys

import pytest


@pytest.fixture
def onboard(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("zalo_onboard_test", Path(__file__).parents[1] / "scripts/zalo_onboard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for key in module.ALLOWED_ENV:
        monkeypatch.delenv(key, raising=False)
    env, mapping, verification = tmp_path / "zalo.env", tmp_path / "identities.json", tmp_path / "verification.txt"
    env.write_text(f"ZALO_BOT_TOKEN=dummy-token\nBEE_BOT_ZALO_IDENTITIES={mapping}\n")
    verification.write_text("BeeBot-private-local-verification-text\n")

    class Client:
        text = "unrelated pending message"
        calls = []

        def __init__(self, token):
            assert token == "dummy-token"
            self.calls.append("init")

        def get_webhook_info(self):
            return {"url": ""}

        def get_updates(self, timeout):
            return {"event_name": "message.text.received", "message": {
                "from": {"id": "verified-sender", "is_bot": False},
                "chat": {"id": "private-chat", "chat_type": "PRIVATE"},
                "message_id": "link-message", "text": self.text,
            }}

        def close(self):
            pass

    monkeypatch.setattr(module, "ZaloBotClient", Client)
    monkeypatch.setattr(sys, "argv", ["zalo_onboard", "identify", "--env-file", str(env), "--actor", "an", "--verification-file", str(verification)])
    return module, Client, env, mapping, verification


def test_arbitrary_pending_message_does_not_grant_demo_identity(onboard, capsys):
    module, client, _, mapping, verification = onboard
    with pytest.raises(SystemExit):
        module.main()
    assert not mapping.exists()
    assert verification.exists()
    assert "VERIFICATION_MISMATCH" in capsys.readouterr().err


def test_matching_private_code_links_once_without_outbound_message(onboard, capsys):
    module, client, _, mapping, verification = onboard
    client.text = verification.read_text().strip()
    module.main()
    assert json.loads(mapping.read_text()) == {"verified-sender": "an"}
    assert not verification.exists()
    result = json.loads(capsys.readouterr().out)
    assert result["message_sent"] is False


def test_missing_bot_token_performs_no_api_operation(onboard, capsys):
    module, client, env, _, _ = onboard
    env.write_text("ZALO_BOT_TOKEN=\n")
    with pytest.raises(SystemExit):
        module.main()
    assert client.calls == []
    assert "ZALO_CONFIG" in capsys.readouterr().err
