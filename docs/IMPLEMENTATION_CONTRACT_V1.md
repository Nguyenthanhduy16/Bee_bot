# Implementation contract — local Bee Bot prototype

Approved 10/10/2026: user confirmed outstanding decisions and authorized Lead + Peer implementation. Deliver actual Hermes through Paseo, fake schedule/Zalo only. No live Sheets/Zalo writes or deployment. Preserve existing Hermes/Paseo personal configuration. Python package `bee_bot` under `src/bee_bot`; pytest under `tests`.

## Shared interfaces and ownership

- Core Peer owns `src/bee_bot/service.py`, `src/bee_bot/store.py`, and core-specific helpers. All state is durable SQLite. Return JSON-serializable dictionaries/lists. Raise `BeeBotError(code, message)` from `bee_bot.errors` (Lead owns this file). HTTP/stdio identity is never a model-supplied parameter.
- Data/integration Peer owns `src/bee_bot/schedule.py`, `src/bee_bot/fixtures.py`, `src/bee_bot/mcp_server.py`, `examples/*`, and `docs/HERMES_LOCAL_SETUP.md`. Do not modify live Hermes/Paseo config without Lead coordination. Use official MCP Python SDK FastMCP. Lead owns install/profile setup, CLI, packaging and review.
- QA Peer owns `tests/*` and `docs/ACCEPTANCE_REPORT_V1.md`; test public service and MCP surfaces, do not edit implementation except by reporting findings to owners.
- Lead owns `pyproject.toml`, `src/bee_bot/__init__.py`, `src/bee_bot/errors.py`, `src/bee_bot/cli.py`, scripts, root docs and integration. Changes to this contract must be broadcast to all peers.

## Schedule interface (data Peer)

Use JSON-backed fake sheet, with file locking for the local emulator only. Real Sheets do not inherit that lock. `JsonSchedule(path)` methods:

- `list_people() -> list[dict]`: `person_id`, `display_name`, `role` (`labcoach`/`ops`), `active` boolean.
- `list_assignments() -> list[dict]`; `get_assignment(assignment_id) -> dict`: `assignment_id`, `shift_id`, `coach_id`, `starts_at`, `ends_at` (offset-aware ISO 8601), `room`, `site`, `class_name`, `j`, `revision` (integer).
- `apply_updates(updates: dict[str,str], expected: dict[str,dict]) -> None`: assignment_id -> new coach_id. Check relevant fields/revision against expected; raise `BeeBotError('SCHEDULE_CHANGED', ...)` before overwrite if different. Modify only coach_id and revision; preserve J and unrelated data. `expected` is a mapping to the original assignment dicts.
- `next_write_fault` optional property for tests: `None`, `'timeout_before'`, `'timeout_after'`, `'partial'` (swap writes first only), `'failure'`. Faults raise `BeeBotError('WRITE_UNCERTAIN', ...)` for timeouts/partial and `'WRITE_FAILED'` for clear failure. Clock/snapshot logic stays in service. After any uncertain write service must read and reconcile, not blindly retry or roll back.
- Demo fake data relative to initialization date, future shifts with morning/afternoon, multiple assignments per shift, users `an`, `binh`, `chi`, `dung`, `ops`. Tests may provide explicit timestamps.

## Service interface (core Peer)

`BeeBotService(db_path, schedule, clock=None)`; clock callable returns aware datetime (default Asia/Ho_Chi_Minh now). Each call validates trusted actor through schedule people. Mutations require external event_id (SQLite unique dedup). Return dictionaries with ids/status/reason and relevant details; never expose others' private requests or personal schedules. In-service writes serialized via SQLite transaction and account for reservations in overlap checks.

- `get_my_assignments(actor_id)` -> list.
- `create_change_request(actor_id, kind, assignment_id, event_id, substitute_id=None, target_assignment_id=None, sender_confirmed=False, sender_no_other_busy=False)` -> request dict. kinds `replacement`, `leave`, `swap`. `replacement` requires substitute; `swap` requires target, sender confirmation/no_other_busy. Ownership of original assignment always checked.
- `get_request_status(actor_id, request_id)` -> dict; owner/ops/invited recipient limited view.
- `list_my_requests(actor_id)` -> list (ops may see all).
- `add_substitute(actor_id, request_id, substitute_id, event_id)` -> dict; owner adds while waiting ops approval: same id, notify ops, move to replacement without approval; invalidate stale invitation(s). Don't replace reserved/updating/completed requests.
- `approve_leave_request(actor_id, request_id, event_id)` -> dict; ops only, invites all eligible labcoaches, excluding owner; no invitation broadcast before approval.
- `nominate_replacement(actor_id, request_id, substitute_id, event_id)` -> dict; ops only, still requires direct recipient confirmation, do not bypass unapproved leave unless explicitly approving first.
- `get_my_invitations(actor_id)` -> list.
- `respond_to_invitation(actor_id, invitation_id, accept, no_other_busy, event_id)` -> request/result dict; require both affirmative for allocation, incomplete confirmation must not reserve. Ordered full confirmations under durable transactions; only first eligible gets position. Invitation deadline min(creation+24h, earliest shift start), strictly reject at/after deadline.
- `cancel_request(actor_id, request_id, reason, event_id)` -> dict; owner/ops before update only, ops reason required; no reversal of completed writes.
- `withdraw_leave_approval(actor_id, request_id, reason, event_id)` -> dict; ops only, stop invitations before write; reconcile reserved/updating first; completed cannot revert.
- `reconcile_request(actor_id, request_id)` -> dict; ops only for uncertain/update exceptions, read actual values; complete only if all expected results match; keep reservation when partial/unclear, do not repeat write/rollback. Clear failure stays awaiting ops/reserved, never auto reassign.
- `create_issue(actor_id, room, description, detected_at, event_id, photo=None, related_issue_id=None)` -> dict (no photo required).
- `get_issue_status(actor_id, issue_id)` -> dict; owner/ops.
- `update_issue(actor_id, issue_id, status, event_id, result=None)` -> dict; ops only, resolved requires outcome/actor/time, no automatic merging; allow recorder cancel before processing, ops cancel later with reason in result.
- `get_my_notifications(actor_id)` -> list; durable fake delivery outbox limited to recipient, includes ops alerts/events. No actual messaging.
- `run_maintenance(actor_id)` -> dict; ops only, expire invitations, flag start/past-start and <=2h pending, produce 08:00/16:00 local summaries once per slot. Reconcile uncertain writes safely on explicit/restart maintenance, no automatic repeated writes.

Overlap: startA < endB and startB < endA; 0-minute travel buffer in prototype. Swap validates resulting schedules (remove each donated assignment first). Snapshot signature ignores J but includes assignment identity, original coach and confirmed shift details; changed relevant schedule stops writes. Read/verify both swap entries; single request id. All writes keep J.

## MCP transport (data/integration Peer)

`python -m bee_bot.mcp_server` (or console entry). Fixed authenticated demo actor through `BEE_BOT_ACTOR_ID` environment, DB/schedule paths through `BEE_BOT_DB`/`BEE_BOT_SCHEDULE`. The model cannot set actor_id/role or unrestricted sheet cells. Trusted local test personas, explicitly not production identity. Tool names above; mutation wrapper injects fresh event UUID independently of model; service also supports durable external event ids for future adapter/test replay. State changes return authoritative structured results, no model decides successful write. Configure separate Hermes profile/session for each actor, no in-chat switch_role tool. MCP schema argument names align service except actor_id/event_id omitted. `create_change_request` should require sender_confirmed=true for user intent confirmation across all kinds; core may enforce that parameter too.

Core may defer machinery that cannot finish to a clearly reported limitation, but must implement all five user flows and critical concurrency/permission/reconciliation invariants. Coordinate uncertainty with Lead promptly.
