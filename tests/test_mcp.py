import asyncio
import json
import os
import sys
from datetime import datetime, timezone

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from bee_bot.errors import BeeBotError
from bee_bot.mcp_server import create_server


def tool_payload(result):
    if result.structuredContent is not None:
        return result.structuredContent
    return json.loads(next(item.text for item in result.content if item.type == "text"))


def test_all_mcp_tool_schemas_hide_trusted_identity_and_event_id(env):
    async def inspect():
        server = create_server(env.service, "an")
        tools = await server.list_tools()
        names = {tool.name for tool in tools}
        assert {"get_my_assignments", "create_change_request", "add_substitute", "approve_leave_request",
                "respond_to_invitation", "create_issue", "get_request_status", "get_my_notifications"} <= names
        for tool in tools:
            properties = tool.inputSchema.get("properties", {})
            assert not {"actor_id", "event_id", "role", "sheet_range", "cells"} & properties.keys()
        unconfirmed = await server.call_tool("create_change_request", {"kind": "replacement", "assignment_id": "a1", "substitute_id": "binh"})
        content = unconfirmed[1] if isinstance(unconfirmed, tuple) else unconfirmed
        assert "CONFIRMATION_REQUIRED" in str(content)
        assert env.service.list_my_requests("an") == []

    asyncio.run(inspect())


@pytest.mark.parametrize("actor", ["unknown", "inactive"])
def test_mcp_cannot_start_with_invalid_demo_actor(env, actor):
    with pytest.raises(BeeBotError):
        create_server(env.service, actor)


def test_real_stdio_transport_fixed_actor_tools_and_permission_errors(env):
    # This starts actual MCP subprocesses; no model, Hermes, Paseo or live integrations.
    # The subprocess uses its real clock; move fixture dates into its future.
    actual_now = datetime.now(timezone.utc)
    delta = actual_now - env.clock.now
    for row in env.payload["assignments"]:
        env.edit(row["assignment_id"],
                 starts_at=(datetime.fromisoformat(row["starts_at"]) + delta).isoformat(),
                 ends_at=(datetime.fromisoformat(row["ends_at"]) + delta).isoformat())
    async def round_trip(actor, operation):
        params = StdioServerParameters(command=sys.executable, args=["-m", "bee_bot.mcp_server"],
            env={**os.environ, "BEE_BOT_ACTOR_ID": actor, "BEE_BOT_DB": str(env.db), "BEE_BOT_SCHEDULE": str(env.path)})
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert "get_my_assignments" in {tool.name for tool in tools.tools}
                context = tool_payload(await session.call_tool("get_bot_context", {}))
                assert context["result"]["actor"]["person_id"] == actor
                assert context["result"]["live_integrations"] is False
                return await operation(session)

    async def scenario():
        async def make(session):
            own = tool_payload(await session.call_tool("get_my_assignments", {}))
            assert own["ok"] and all(row["coach_id"] == "an" for row in own["result"])
            created = tool_payload(await session.call_tool("create_change_request", {
                "kind": "replacement", "assignment_id": "a1", "substitute_id": "binh", "sender_confirmed": True}))
            assert created["ok"]
            return created["result"]["request_id"]

        request_id = await round_trip("an", make)

        async def guessed(session):
            denied = tool_payload(await session.call_tool("get_request_status", {"request_id": request_id}))
            assert denied["ok"] is False

        await round_trip("chi", guessed)

        async def recipient(session):
            items = tool_payload(await session.call_tool("get_my_invitations", {}))["result"]
            item = next(item for item in items if item["request_id"] == request_id)
            result = tool_payload(await session.call_tool("respond_to_invitation", {
                "invitation_id": item["invitation_id"], "accept": True, "no_other_busy": True}))
            assert result["ok"] and result["result"]["status"] == "completed"

        await round_trip("binh", recipient)

    asyncio.run(scenario())
    assert env.schedule.get_assignment("a1")["coach_id"] == "binh"
