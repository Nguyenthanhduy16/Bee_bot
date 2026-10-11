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


def test_shared_profile_actor_context_is_fixed_per_mcp_process(env, monkeypatch):
    async def context(server):
        result = await server.call_tool("get_bot_context", {})
        payload = result[1] if isinstance(result, tuple) else result
        return json.loads(payload[0].text)["result"]["actor"]["person_id"]

    monkeypatch.setenv("BEE_BOT_ACTOR_ID", "an")
    an_server = create_server(env.service)
    monkeypatch.setenv("BEE_BOT_ACTOR_ID", "binh")
    binh_server = create_server(env.service)
    assert asyncio.run(context(an_server)) == "an"
    assert asyncio.run(context(binh_server)) == "binh"
    assert asyncio.run(context(an_server)) == "an"
    monkeypatch.setenv("BEE_BOT_ACTOR_ID", "${BEE_BOT_ACTOR_ID}")
    with pytest.raises(BeeBotError):
        create_server(env.service)


def test_zalo_display_name_is_separate_from_demo_actor(env, monkeypatch):
    monkeypatch.setenv("BEE_BOT_ACTOR_ID", "an")
    monkeypatch.setenv("BEE_BOT_ZALO_DISPLAY_NAME", "Duy Nguyễn")
    server = create_server(env.service)
    async def context():
        result = await server.call_tool("get_bot_context", {})
        payload = result[1] if isinstance(result, tuple) else result
        return json.loads(payload[0].text)["result"]
    value = asyncio.run(context())
    assert value["actor"]["person_id"] == "an"
    assert value["zalo_display_name"] == "Duy Nguyễn"
    assert value["actor_is_demo_persona"] is True


@pytest.mark.parametrize("tool,args", [("reconcile_request", {"request_id": "request"}),
                                       ("run_maintenance", {})])
@pytest.mark.parametrize("event", [None, "", "${BEE_BOT_EVENT_ID}", "zalo:bad", "adapter:untrusted"])
def test_recovery_tools_reject_invalid_zalo_context_before_service(env, monkeypatch, tool, args, event):
    monkeypatch.setenv("BEE_BOT_CHANNEL", "zalo")
    if event is None:
        monkeypatch.delenv("BEE_BOT_EVENT_ID", raising=False)
    else:
        monkeypatch.setenv("BEE_BOT_EVENT_ID", event)
    calls = []
    monkeypatch.setattr(env.service, tool, lambda *a, **kw: calls.append((a, kw)))

    async def invoke():
        result = await create_server(env.service, "ops").call_tool(tool, args)
        content = result[1] if isinstance(result, tuple) else result
        return json.loads(content[0].text)

    assert asyncio.run(invoke())["error"] == "EVENT_CONTEXT_REQUIRED"
    assert calls == []


@pytest.mark.parametrize("channel", ["zalo", "local"])
@pytest.mark.parametrize("tool,args", [("reconcile_request", {"request_id": "request"}),
                                       ("run_maintenance", {})])
def test_recovery_tools_forward_without_injecting_event_id(env, monkeypatch, channel, tool, args):
    monkeypatch.setenv("BEE_BOT_CHANNEL", channel)
    if channel == "zalo":
        monkeypatch.setenv("BEE_BOT_EVENT_ID", "zalo:" + "a" * 64)
    else:
        monkeypatch.delenv("BEE_BOT_EVENT_ID", raising=False)
    calls = []

    def recover(actor, **kwargs):
        calls.append((actor, kwargs))
        return {"status": "checked"}

    monkeypatch.setattr(env.service, tool, recover)

    async def invoke():
        result = await create_server(env.service, "ops").call_tool(tool, args)
        content = result[1] if isinstance(result, tuple) else result
        return json.loads(content[0].text)

    assert asyncio.run(invoke()) == {"ok": True, "result": {"status": "checked"}}
    assert calls == [("ops", args)]


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


def mcp_payload(response):
    payload = response[1] if isinstance(response, tuple) else response
    if isinstance(payload, dict):
        return payload
    return json.loads(payload[0].text)


@pytest.fixture
def default_servers(env, monkeypatch):
    """Exercise actual default construction with isolated DB/JSON and a fixed clock."""
    import bee_bot.service as service_module
    original = service_module.BeeBotService
    services = []

    def open_service(db_path, schedule):
        service = original(db_path, schedule, clock=lambda: env.clock.now)
        services.append(service)
        return service

    monkeypatch.setattr(service_module, "BeeBotService", open_service)
    monkeypatch.setenv("BEE_BOT_SCHEDULE", str(env.path))
    monkeypatch.setenv("BEE_BOT_DB", str(env.db))
    monkeypatch.delenv("BEE_BOT_SCHEDULE_BACKEND", raising=False)
    monkeypatch.delenv("BEE_BOT_SHEETS_CONFIG", raising=False)
    yield services
    for service in services:
        service.close()


def test_default_mcp_routes_through_factory_and_reports_json(env, monkeypatch, default_servers):
    import bee_bot.mcp_server as mcp_module
    factory = mcp_module.create_schedule
    calls = []

    def selected():
        schedule = factory()
        calls.append(schedule)
        return schedule

    monkeypatch.setattr(mcp_module, "create_schedule", selected)
    monkeypatch.setenv("BEE_BOT_ACTOR_ID", "an")
    server = create_server()
    assert len(calls) == 1 and default_servers[0].schedule is calls[0]

    async def read():
        context = mcp_payload(await server.call_tool("get_bot_context", {}))["result"]
        assert context["schedule"] == "fake_json"
        assert context["schedule_backend"] == "json"
        assert context["provenance"] == {"kind": "synthetic"}
        assert context["notifications"] == "durable_fake_outbox"
        assert context["live_integrations"] is False
        assert context["actor_is_demo_persona"] is True
        assignments = mcp_payload(await server.call_tool("get_my_assignments", {}))
        assert assignments["ok"] and [a["assignment_id"] for a in assignments["result"]] == ["a1"]

    asyncio.run(read())


def test_default_factory_service_mcp_replacement_preserves_actor_and_event_gates(env, monkeypatch, default_servers):
    monkeypatch.setenv("BEE_BOT_CHANNEL", "zalo")
    monkeypatch.setenv("BEE_BOT_ACTOR_ID", "an")
    monkeypatch.delenv("BEE_BOT_EVENT_ID", raising=False)
    owner = create_server()

    async def workflow():
        options = {"kind": "replacement", "assignment_id": "a1", "substitute_id": "binh",
                   "sender_confirmed": True}
        assert mcp_payload(await owner.call_tool("create_change_request", options))["error"] == "EVENT_CONTEXT_REQUIRED"
        assert env.service.list_my_requests("an") == []
        monkeypatch.setenv("BEE_BOT_EVENT_ID", "zalo:" + "a" * 64)
        request = mcp_payload(await owner.call_tool("create_change_request", options))["result"]
        duplicate = mcp_payload(await owner.call_tool("create_change_request", options))["result"]
        assert duplicate["id"] == request["id"]
        monkeypatch.setenv("BEE_BOT_ACTOR_ID", "binh")
        recipient = create_server()
        owner_context = mcp_payload(await owner.call_tool("get_bot_context", {}))["result"]
        assert owner_context["actor"]["person_id"] == "an"
        invites = mcp_payload(await recipient.call_tool("get_my_invitations", {}))["result"]
        invite = next(i for i in invites if i["request_id"] == request["id"])
        monkeypatch.setenv("BEE_BOT_EVENT_ID", "zalo:" + "b" * 64)
        result = mcp_payload(await recipient.call_tool("respond_to_invitation", {
            "invitation_id": invite["id"], "accept": True, "no_other_busy": True}))
        assert result["ok"] and result["result"]["status"] == "completed"
        repeated = mcp_payload(await recipient.call_tool("respond_to_invitation", {
            "invitation_id": invite["id"], "accept": True, "no_other_busy": True}))
        assert repeated["result"]["id"] == request["id"]

    before = env.schedule.get_assignment("a1")
    asyncio.run(workflow())
    after = env.schedule.get_assignment("a1")
    assert after == {**before, "coach_id": "binh", "revision": before["revision"] + 1}


@pytest.mark.parametrize("backend,code", [("unknown", "SCHEDULE_BACKEND_INVALID"),
                                          ("google_sheets_test_copy", "SHEETS_CONFIG_REQUIRED")])
def test_default_mcp_backend_failure_never_falls_back_to_json(env, monkeypatch, tmp_path, backend, code):
    db = tmp_path / "not-created.db"
    monkeypatch.setenv("BEE_BOT_ACTOR_ID", "an")
    monkeypatch.setenv("BEE_BOT_SCHEDULE", str(env.path))
    monkeypatch.setenv("BEE_BOT_DB", str(db))
    monkeypatch.setenv("BEE_BOT_SCHEDULE_BACKEND", backend)
    monkeypatch.delenv("BEE_BOT_SHEETS_CONFIG", raising=False)
    with pytest.raises(BeeBotError) as error:
        create_server()
    assert error.value.code == code and not db.exists()


def test_injected_json_context_uses_instance_even_with_ambient_google_backend(env, monkeypatch):
    monkeypatch.setenv("BEE_BOT_SCHEDULE_BACKEND", "google_sheets_test_copy")

    async def read():
        context = mcp_payload(await create_server(env.service, "an").call_tool("get_bot_context", {}))["result"]
        assert context["schedule_backend"] == "json" and context["schedule"] == "fake_json"
        assert context["actor_is_demo_persona"] is True

    asyncio.run(read())


@pytest.fixture
def copy_service(tmp_path, env):
    from bee_bot.service import BeeBotService
    from bee_bot.sheets_adapter import SheetsScheduleAdapter
    from bee_bot.sheets_copy_transport import synthetic_roster, write_synthetic_tab

    transport = write_synthetic_tab(tmp_path / "tab.json", datetime.fromisoformat(env.payload["assignments"][0]["starts_at"]).date())
    transport.set_provenance({"kind": "test_copy", "spreadsheet_id": "placeholder-private-copy",
                              "tab": "Private synthetic tab", "owner_confirmed_copy": True, "sheet_id": 0})
    schedule = SheetsScheduleAdapter(transport, synthetic_roster(), {"placeholder-private-copy"})
    service = BeeBotService(tmp_path / "copy-state.db", schedule, clock=lambda: env.clock.now)
    yield service, transport
    service.close()


def test_test_copy_context_is_trusted_redacted_and_not_json_demo(copy_service, monkeypatch):
    service, transport = copy_service
    monkeypatch.setenv("BEE_BOT_SCHEDULE_BACKEND", "json")

    async def read():
        server = create_server(service, "an")
        context = mcp_payload(await server.call_tool("get_bot_context", {}))["result"]
        assert context["schedule"] == "sheets_test_copy" and context["schedule_backend"] == "sheets_adapter"
        assert context["actor_is_demo_persona"] is False
        assert context["live_integrations"] is None  # Synthetic transport does not establish Google connectivity.
        assert context["provenance"] == {"kind": "test_copy", "owner_confirmed_copy": True,
                                          "scope": "single_tab", "writable": True, "compare_and_set": False}
        assert "placeholder-private-copy" not in json.dumps(context)
        assert "Private synthetic tab" not in json.dumps(context)
        assert "Fake schedule" not in server.instructions
        tools = await server.list_tools()
        assert not any("sheet" in tool.name for tool in tools)
        for tool in tools:
            assert not {"schedule_backend", "owner_confirmed_copy", "allowed_tabs", "known_source_ids",
                        "spreadsheet_id", "sheet_id", "actor_id", "event_id"} & tool.inputSchema.get("properties", {}).keys()

    asyncio.run(read())


def test_context_refuses_changed_copy_provenance(copy_service):
    service, transport = copy_service
    server = create_server(service, "an")
    transport.set_provenance({**transport.provenance(), "tab": "Changed tab"})

    async def read():
        result = mcp_payload(await server.call_tool("get_bot_context", {}))
        assert result["ok"] is False and result["error"] == "SHEETS_PROVENANCE_REJECTED"
        assert "Changed tab" not in json.dumps(result)

    asyncio.run(read())


@pytest.fixture
def google_mcp(env, monkeypatch, tmp_path, default_servers):
    """Actual default factory, adapter and Google transport with mock HTTP only."""
    import re
    import httpx
    import bee_bot.google_sheets_transport as google
    from bee_bot.sheets_copy_transport import synthetic_roster, write_synthetic_tab

    tab = write_synthetic_tab(tmp_path / "google-grid.json",
                              datetime.fromisoformat(env.payload["assignments"][0]["starts_at"]).date()).read_tab()
    state = {"tab": tab, "requests": [], "writes": [], "after_write": None, "reject_row": None}
    title, sid = "Private test tab", "approved-test-copy-placeholder"

    def cell(value):
        if value is None:
            return {}
        kind = "numberValue" if isinstance(value, (int, float)) else "stringValue"
        return {"userEnteredValue": {kind: value}, "effectiveValue": {kind: value}}

    def payload():
        rows = state["tab"]["rows"]
        return {"spreadsheetId": sid, "sheets": [{
            "properties": {"sheetId": 0, "title": title,
                           "gridProperties": {"rowCount": len(rows), "columnCount": 10}},
            "data": [{"startRow": 0, "startColumn": 0, "rowData": [
                {"values": [cell(row["cells"].get(c)) for c in "ABCDEFGHIJ"]} for row in rows]}],
            "merges": [{"sheetId": 0, "startRowIndex": merge["start"] - 1,
                        "endRowIndex": merge["end"], "startColumnIndex": "ABCDEFGHIJ".index(c),
                        "endColumnIndex": "ABCDEFGHIJ".index(c) + 1}
                       for merge in state["tab"]["merges"] for c in merge["columns"]],
            "developerMetadata": [{"metadataId": index, "metadataKey": "approved-anchor-key",
                                    "metadataValue": row["anchor"], "location": {"dimensionRange": {
                                        "sheetId": 0, "dimension": "ROWS", "startIndex": row["row"] - 1,
                                        "endIndex": row["row"]}}}
                                   for index, row in enumerate(rows, 1) if row["anchor"]],
        }]}

    def handler(request):
        state["requests"].append(request.method)
        assert request.headers["Authorization"] == "Bearer offline-test-token"
        assert request.url.path.startswith("/v4/spreadsheets/" + sid)
        if request.method == "GET":
            return httpx.Response(200, json=payload())
        assert request.method == "PUT"
        match = re.search(r"!D(\d+)$", request.url.path)
        assert match and request.url.params["valueInputOption"] == "RAW"
        row = int(match.group(1))
        body = json.loads(request.content)
        assert body["range"] == f"'{title}'!D{row}"
        assert body["majorDimension"] == "ROWS" and len(body["values"]) == len(body["values"][0]) == 1
        state["writes"].append(row)
        if state["reject_row"] == row:
            return httpx.Response(503, json={"error": "synthetic uncertain write"})
        state["tab"]["rows"][row - 1]["cells"]["D"] = body["values"][0][0]
        if state["after_write"]:
            state["after_write"]()
        return httpx.Response(200, json={"spreadsheetId": sid, "updatedCells": 1})

    class Credentials:
        valid, token = True, "offline-test-token"
        scopes = [google.SHEETS_SCOPE]
        granted_scopes = [google.SHEETS_SCOPE]

        def has_scopes(self, scopes):
            return scopes == [google.SHEETS_SCOPE]

    real_transport = google.GoogleSheetsTransport
    transports = []
    client = httpx.Client(transport=httpx.MockTransport(handler))

    def construct(config, credentials=None, http_client=None):
        transport = real_transport(config, credentials=Credentials(), http_client=client)
        transports.append(transport)
        return transport

    # Only credential/HTTP injection is intercepted. The real Data class runs
    # its config, pin, metadata, read, anchor, write and response validation.
    monkeypatch.setattr(google, "GoogleSheetsTransport", construct)
    config = {"spreadsheet_id": sid, "tab": title, "sheet_id": 0, "owner_confirmed_copy": True,
              "allowed_spreadsheet_ids": [sid], "denied_source_ids": [], "allowed_tabs": [title],
              "people": synthetic_roster(), "expected_anchor_count": 6, "max_rows": len(tab["rows"]),
              "anchor_mode": "metadata", "metadata_key": "approved-anchor-key", "write_enabled": True,
              "allowed_write_anchors": ["anc-001", "anc-004", "anc-005"]}
    config_path = tmp_path / "private-config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("BEE_BOT_SCHEDULE_BACKEND", "google_sheets_test_copy")
    monkeypatch.setenv("BEE_BOT_SHEETS_CONFIG", str(config_path))
    monkeypatch.setenv("BEE_BOT_CHANNEL", "local")
    monkeypatch.delenv("BEE_BOT_EVENT_ID", raising=False)
    state["transports"], state["config"] = transports, config
    yield state
    for transport in transports:
        transport.close()
    client.close()


@pytest.mark.parametrize("write_enabled,anchors", [(False, ["anc-001"]), (True, [])])
def test_google_context_reports_transport_write_gate(google_mcp, monkeypatch, default_servers, write_enabled, anchors):
    config = {**google_mcp["config"], "write_enabled": write_enabled, "allowed_write_anchors": anchors}
    with open(os.environ["BEE_BOT_SHEETS_CONFIG"], "w", encoding="utf-8") as handle:
        json.dump(config, handle)
    monkeypatch.setenv("BEE_BOT_ACTOR_ID", "chi")
    server = create_server()

    async def read():
        context = mcp_payload(await server.call_tool("get_bot_context", {}))["result"]
        assert context["schedule_backend"] == "google_sheets_test_copy"
        assert context["provenance"]["writable"] is False
        assert context["live_integrations"] is True

    asyncio.run(read())
    assert google_mcp["writes"] == []


@pytest.mark.parametrize("overlap", [False, True])
def test_actual_google_factory_service_default_mcp_replacement(google_mcp, monkeypatch, default_servers, overlap):
    state = google_mcp
    before = json.loads(json.dumps(state["tab"]))
    monkeypatch.setenv("BEE_BOT_ACTOR_ID", "chi")
    owner = create_server()
    assert type(default_servers[-1].schedule.transport).__name__ == "GoogleSheetsTransport"

    async def scenario():
        context = mcp_payload(await owner.call_tool("get_bot_context", {}))["result"]
        assert context["schedule_backend"] == context["schedule"] == "google_sheets_test_copy"
        assert context["actor_is_demo_persona"] is False
        assert context["provenance"]["owner_confirmed_copy"] is True
        assert state["config"]["spreadsheet_id"] not in json.dumps(context)
        assignments = mcp_payload(await owner.call_tool("get_my_assignments", {}))["result"]
        assignment = next(a for a in assignments if a["source_locator"]["row"] == 9)
        request = mcp_payload(await owner.call_tool("create_change_request", {
            "kind": "replacement", "assignment_id": assignment["assignment_id"],
            "substitute_id": "binh", "sender_confirmed": True}))["result"]
        monkeypatch.setenv("BEE_BOT_ACTOR_ID", "binh")
        recipient = create_server()
        invite = next(i for i in mcp_payload(await recipient.call_tool("get_my_invitations", {}))["result"]
                      if i["request_id"] == request["id"])
        if overlap:
            state["after_write"] = lambda: state["tab"]["rows"][10]["cells"].update(D="Synthetic Binh")
        result = mcp_payload(await recipient.call_tool("respond_to_invitation", {
            "invitation_id": invite["id"], "accept": True, "no_other_busy": True}))
        assert result["ok"]
        if overlap:
            assert result["result"]["status"] == "reconciliation_required"
            assert result["result"]["reserved_for"] == "binh"
            monkeypatch.setenv("BEE_BOT_ACTOR_ID", "ops")
            ops = create_server()  # Reopen through actual factory/transport/service.
            for _ in range(2):
                await ops.call_tool("run_maintenance", {})
                checked = mcp_payload(await ops.call_tool("reconcile_request", {"request_id": request["id"]}))
                assert checked["result"]["status"] == "reconciliation_required"
            alerts = mcp_payload(await ops.call_tool("get_my_notifications", {}))["result"]
            assert len([n for n in alerts if n["event"] == "reconciliation_required"
                        and n["request_id"] == request["id"]]) == 1
        else:
            assert result["result"]["status"] == "completed"

    asyncio.run(scenario())
    assert state["writes"] == [9]
    assert state["tab"]["rows"][8]["cells"]["D"] == "Synthetic Binh"
    for old, new in zip(before["rows"], state["tab"]["rows"]):
        assert {k: v for k, v in old["cells"].items() if k != "D"} == {
            k: v for k, v in new["cells"].items() if k != "D"}
