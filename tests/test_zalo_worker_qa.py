"""Independent bridge checks; synthetic tokens/messages and no model traffic."""

import logging

import httpx

from bee_bot.zalo import ZaloBotClient, ZaloIngress
from bee_bot.zalo_worker import PollingWorker
from test_zalo_worker import Client, event


def test_transport_info_logs_do_not_expose_token(caplog):
    token = "1:synthetic-private-bot-token"
    with caplog.at_level(logging.INFO):
        client = ZaloBotClient(token, transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"ok": True, "result": {"id": "demo-bot"}})))
        client.get_me()
        client.close()
    assert token not in caplog.text


def test_sender_conversations_remain_separate_across_worker_restart(tmp_path):
    class Service:
        def get_my_assignments(self, actor):
            assert actor in {"an", "binh"}
            return []

        def get_my_notifications(self, actor):
            return []

    class Runner:
        def __init__(self):
            self.calls = []

        def reply(self, actor, incoming, session_id):
            self.calls.append((actor, session_id))
            return {"text": "Demo response", "session_id": session_id or f"session-{actor}"}

    def incoming(sender, chat, message_id):
        payload = event(message_id, sender)
        payload["message"]["chat"]["id"] = chat
        return payload

    client, runner = Client(), Runner()
    identities = {"sender-an": "an", "sender-binh": "binh"}
    ingress = ZaloIngress(tmp_path / "inbox.db", identities=identities, webhook_secret="test-secret")
    worker = PollingWorker(client, ingress, runner, Service())
    client.payload = incoming("sender-an", "chat-an", "an-1")
    worker.once()
    client.payload = incoming("sender-binh", "chat-binh", "binh-1")
    worker.once()
    restarted = PollingWorker(client, ZaloIngress(tmp_path / "inbox.db", identities=identities,
                              webhook_secret="test-secret"), runner, Service())
    client.payload = incoming("sender-an", "chat-an", "an-2")
    restarted.once()
    client.payload = incoming("sender-binh", "chat-binh", "binh-2")
    restarted.once()
    assert runner.calls == [("an", None), ("binh", None), ("an", "session-an"), ("binh", "session-binh")]


def test_uncertain_delivery_is_not_repeated_after_restart(tmp_path):
    from test_zalo_worker import worker

    original = worker(tmp_path)
    original.client.failure = True
    original.once()
    assert len(original.client.sent) == 2
    restarted = worker(tmp_path)
    restarted.once()
    assert restarted.runner.calls == []
    assert restarted.client.sent == []


def test_bridge_profile_explicitly_passes_event_id_through_hermes_safe_env(tmp_path):
    import yaml
    from bee_bot.zalo_worker import HermesRunner
    from test_zalo_worker import source_profile

    source_profile(tmp_path)
    HermesRunner(tmp_path).prepare_profile("an")
    config = yaml.safe_load((tmp_path / "bee-zalo-an/config.yaml").read_text())
    # Hermes strips arbitrary parent variables; an explicit interpolation is required.
    assert config["mcp_servers"]["bee_bot"]["env"]["BEE_BOT_EVENT_ID"] == "${BEE_BOT_EVENT_ID}"
    assert config["mcp_servers"]["bee_bot"]["env"]["BEE_BOT_ACTOR_ID"] == "an"
