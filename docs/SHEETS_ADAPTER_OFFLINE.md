# Sheets adapter — offline synthetic increment

- Date: 11/10/2026. Status: **offline engineering candidate**, synthetic data only. **Not production-ready.**
- Code: `src/bee_bot/sheets_adapter.py` (`SheetsScheduleAdapter`), `src/bee_bot/sheets_copy_transport.py` (`SyntheticSheetTransport`).
- Tests: `tests/test_sheets_adapter_core.py`.
- Basis: [decisions Q4](DECISIONS_TO_START_V1.md), [contract](IMPLEMENTATION_CONTRACT_V1.md), [mapping draft](SHEETS_MAPPING_V1_DRAFT.md).

`JsonSchedule` remains the default schedule for the service, CLI and MCP. This adapter is not wired into any of them. It uses no network, no Google SDK and no credentials. It never reads or writes `.bee-bot/source/schedule.xlsx`, and the transport refuses any backing file that isn't `.json` or that lives under `.bee-bot/source/`.

## 1. Interface

`SheetsScheduleAdapter(transport, people, allowed_spreadsheet_ids, denied_source_ids=())` implements the contract's schedule interface unchanged: `list_people`, `list_assignments`, `get_assignment` and `apply_updates(updates, expected)`. It also adds `coverage()`, which reports writable scope explicitly.

The transport boundary is deliberately narrow:

| Call | Meaning |
| --- | --- |
| `provenance()` | Self-described origin: `kind`, `spreadsheet_id`, `tab`, `copy_of`, `contains_real_data` |
| `read_tab()` | One tab: rows with cells A–J, a row `anchor`, and merge ranges |
| `write_d(anchor, value, spreadsheet_id, tab)` | Writes ONE column-D cell, addressed by anchor and pinned workbook/tab, **with no expected-value precondition** |

No call can write J or any column other than D. The fake's ops-edit helpers (`set_cell`, `insert_row`, `move_row`, `set_provenance`) and its per-call `script` (before/after hooks and the faults `timeout_before`, `timeout_after`, `reject`) exist only for tests.

## 2. Synthetic layout

The synthetic tab mirrors the observed layout:
- a title row;
- day blocks headed in A (`Thứ 2 - dd/mm/yyyy`) with a header row;
- numeric-STT data rows with B Track, C Session, D Lab Coach, E Key Coach, F Room, G Sáng/Chiều, H capacity, I notes and J status;
- one merged B/C/F/G block covering two positions of the same class;
- one vacant D slot.

All names are placeholders (`Synthetic An`, …).

Parsing rules:
- The date comes from A, and canonical data comes from B–J.
- Merges resolve only inside their own day block.
- K–P are ignored.
- Times follow the settled rule: Sáng 09:00–13:00, Chiều 14:00–18:00, Asia/Ho_Chi_Minh.

## 3. Invariants and how they are enforced

- **D is authoritative and J is never written.** The adapter writes the roster's sheet name into D only. A J edit by ops before or during a write survives and does not block the write. `revision` excludes J.
- **Trusted people.** `people` is an explicit roster with `sheet_names` aliases. Names in D never create identities. Duplicate ids or aliases make construction fail (`ROSTER_AMBIGUOUS`). A write target must be an active labcoach in the roster.
- **Stable assignment IDs.** `assignment_id = digest(spreadsheet_id, tab, row anchor)`. The ID survives row insertion, moves within a block, STT renumbering and name edits on other rows. Writes are addressed by anchor, so a write after an insertion lands on the relocated row, and the row now at the old coordinate is untouched.
- **Row classification.** Every row is classified. A row is a data row when its STT is a positive integer, given either as a number or as an integer-valued string (`'3'`, `'3.0'`). Rows before the first recognised day header are preamble, so a title containing dates is allowed. A recognised day header must have empty B–J. A column-header row must have no assignment anchor and the declared A/B/C/D/F/G labels (`STT`, `Khóa`, `Session`, `Lab Coach`, `Phòng`, `Buổi`). `STT` alone never exempts a populated assignment. An A-only note row is allowed. Anything else that has content in B–J is `UNCLASSIFIED_ROW`. After the first day header, any A text that looks like a date or weekday but does not parse is `INVALID_DATE_HEADER`, and the date is reset so the next block never inherits the previous day.
- **Fail-closed writable coverage.** These diagnostics are surfaced by `coverage()` and carry only a row and a code, never names:
  - `MISSING_ANCHOR`
  - `DUPLICATE_ANCHOR`
  - `INVALID_CANONICAL_ROW`, for example a row moved out of its day block or a missing room
  - `UNKNOWN_ROSTER_NAME`
  - `INVALID_DATE_HEADER`
  - `UNCLASSIFIED_ROW`
  - `MERGED_KEY_CELL`, a merge over A or D

  Any one of them makes the tab non-writable, and `apply_updates` raises `SCHEDULE_SCOPE_INCOMPLETE` before any write. The reasoning: a hidden row could hide an overlap. Reads still return the valid rows. Structurally malformed transport output (rows, cells, anchors or merges) raises a controlled `SCHEDULE_MALFORMED` and causes no write.
- **Fresh validation before EACH D write.** Before every individual `write_d`, `apply_updates` re-reads the tab and re-validates five things:
  1. scope;
  2. pinned identity;
  3. every remaining target, which must exist, be unique and match `expected` on the service `SIGNATURE`;
  4. targets already written, which must still show the recipient and their confirmed details;
  5. the resulting recipient overlaps on this tab.

  Before the first write, a failure raises its own code (`SCHEDULE_CHANGED`, `SCHEDULE_CONFLICT`, …). After a write has landed it raises `WRITE_UNCERTAIN`, and the earlier write is kept, not rolled back.
- **Pinned identity.** `(kind, spreadsheet_id, tab, copy_of, owner_confirmed_copy, sheet_id)` is pinned at construction and must still match on every read and before each write. A supplied `sheet_id` must be a non-negative integer (0 is valid; booleans and numeric strings are rejected). Synthetic/legacy provenance may omit it; the real Google transport must validate it against metadata on read/write. Switching to another allowlisted workbook, tab, numeric sheet ID or owner-confirmation state is refused. The transport call itself is also bound to `(spreadsheet_id, tab)`, the way a REST URL and quoted range would be, so a switch inside the call is refused too.
- **Verify after writing.** Readback re-runs the same validation over all targets: recipient present, confirmed details unchanged, scope clean, no recipient overlap. Any failure raises `WRITE_UNCERTAIN`. `verify_applied(updates, expected)` exposes the same check as a read-only call for reconciliation (see §9).
- **No retry and no rollback.** Error mapping:
  - A clear refusal before anything was written → `WRITE_FAILED`, or the gate's own code.
  - Any timeout, a failure after one cell was written, or a failed verification → `WRITE_UNCERTAIN`.
  - The service then reconciles by reading only. It keeps the reservation while results are partial or unclear, and completes only when every planned D matches, confirmed details match, all planned coaches have no overlap, and adapter verification succeeds. Restart maintenance never rewrites.

## 4. Provenance gate

Writes and reads are accepted only when all of these hold:
- `spreadsheet_id` is in `allowed_spreadsheet_ids`;
- it is **not** in `denied_source_ids`, because the denylist wins over the allowlist;
- a `tab` is named;
- and one of:
  - `kind == 'synthetic'` with `contains_real_data is False`, or
  - `kind == 'test_copy'` with explicit trusted `owner_confirmed_copy is True`. The original source ID may be unknown or absent. If `copy_of` is supplied, a self-copy is still rejected. No original source ID is invented; or
  - legacy `kind == 'test_copy'` with a `copy_of` that is non-empty, differs from `spreadsheet_id`, and is not itself allowlisted. This compatibility path is not enough to enable the real Google backend.

**Self-described provenance is not proof of a copy.** Anyone can label a spreadsheet `test_copy`, so the label alone is never trusted. Which workbook is the authorized test copy is decided by the owner, and configuration (outside Git) must follow that decision: put the authorized test workbook on the allowlist, and put any known production source on the denylist. The denylist always wins, even over explicit owner confirmation. The supplied workbook's owner authorization is already recorded privately; the former source-collision note is superseded. Missing source ID is not a reason to request another URL or invent an ID. Git contains no real or private IDs: tests use placeholders such as `placeholder-source-id`.

## 5. Limitations (demonstrated, not solved)

- **No compare-and-set.** Google Sheets value writes have no expected-value precondition, and this fake deliberately gives none either. An ops edit to D that lands between the adapter's last read and its write is **overwritten without detection**. Verification still passes because D holds the bot's value. `test_LIMITATION_no_compare_and_set_lost_update_between_read_and_write` asserts this outcome. It is a limitation, not a safety success. Reading before and after narrows the window but does not close it.
- **`revision` is a content hash** of date, B, C, D, F and G, not a version counter. Rewriting the same value, or an A→B→A edit, is invisible (`test_LIMITATION_revision_is_content_hash_aba_invisible`).
- **Single tab.** Roster coverage, the overlap re-check and writable scope cover one tab. Other tabs or periods are not checked, and the service's overlap check is equally limited to what the adapter lists.
- **Row anchors are a synthetic transport identity.** The fake moves an anchor with its row. Whether real Sheets **developer metadata** (written with `values.batchUpdateByDataFilter`) or a **hidden ID column** behaves this way under insertion, moves, sorting, copy-paste and filters is **unverified**. Both are pilot alternatives, not claimed guarantees. Copy-paste duplicating an anchor is detected (`DUPLICATE_ANCHOR`) and blocks writes.
- **Partial writes.** Swap writes are two separate single-cell calls, and batch atomicity is not assumed. A partial swap stays `reconciliation_required` until ops fixes D by hand or decides otherwise.
- **Strictness.** A single unknown name or unclassified row anywhere on the tab blocks all writes on that tab. This is intentional for safety, but it may be too strict for a real sheet.
- **Cell typing assumption.** The transport is assumed to return unformatted values. A real transport that returns date serials in A would see them as numeric STT rows, which then fail as canonical rows (fail-closed, but noisy).
- **Moves.** The fake's `move_row` only moves unmerged rows.

## 6. Reproducible synthetic end-to-end demo

This runs the real `BeeBotService` on top of the adapter: a successful replacement, then a swap whose second D write times out, then closing and reopening the service objects, `run_maintenance`, an ops fix by hand, and `reconcile_request`.

```bash
.venv/bin/python -m bee_bot.sheets_adapter "$(mktemp -d)/demo"
```

Expected output, in summary:
- `replacement_status: completed`
- `swap_status_after_partial: reconciliation_required`
- `swap_status_after_restart_maintenance: reconciliation_required`
- `bot_writes_after_restart == bot_writes_final == 2` (one replacement plus one half of the swap, with no re-write after restart)
- `swap_status_after_ops_fix: completed`
- the J column unchanged
- `compare_and_set: false`

`test_offline_end_to_end_demo` runs the same scenario.

Tests: `.venv/bin/python -m pytest -q tests/test_sheets_adapter_core.py`.

## 7. Blocked only for the real pilot

- Access to the authorized test workbook is established for the observed tab. Runtime configuration still needs the approved full tab catalogue, trusted roster, anchor map and allowlist before the bot can use it.
- The real anchor mechanism (developer metadata or an ID column) and consent from the Sheets owner, verified on the copy.
- Roster details: a mapping from D names to verified person IDs, ops/roles and active status, and the policy for people with the same name.
- The catalogue of tabs and schedule periods for cross-tab overlap checks.
- An ops coordination policy for the lost-update window (the Q4 follow-up), for example a protected range during writes or an edit window.
- Quota and latency behaviour, and the semantics of real timeouts.
- The travel buffer rule.

## 8. Admin probe: one D cell on the owner-authorized test copy

`scripts/sheets_copy_probe.py` is a bounded admin probe that uses the official REST endpoints `GET` and `PUT https://sheets.googleapis.com/v4/spreadsheets/{spreadsheetId}/values/{range}` (`spreadsheets.values/get` and `spreadsheets.values/update`). It is **not** wired to the bot, the MCP server, the CLI or the default schedule. Development tests used `httpx.MockTransport` (`tests/test_sheets_copy_probe.py`). Lead ran the probe live on the authorized copy on 11/10/2026; see [`GOOGLE_SHEETS_SETUP.md`](GOOGLE_SHEETS_SETUP.md) for the bounded result.

**Inputs.**
- **Config:** the private config `.bee-bot/pilot-inputs.json` (ignored by Git), fields under `sheets`.
- **Spreadsheet:** the target is exactly `candidate_copy_id`. The owner confirmation is `verification_status == "owner_confirmed_test_copy"`. `known_source_ids` acts as a denylist and always wins.
- **Write limits:**
  - `allowed_tabs` and `allowed_cells` are required.
  - `test_probe.cell` must be a single D cell listed in `allowed_cells`.
  - `guard_cell` must be J on the same row.
  - `expected_d`, `expected_j` and `test_value` are required. The test value must differ from the original and must not start with `=`.
- **Read range:** an optional `test_probe.read_range`, default `A1:T1000`, must start at A1, include J and the probe row, and span at most 5000 rows.
- **Evidence directory:** `evidence_dir` must be under `.bee-bot/` and not under `.bee-bot/source/`.
- **Context fields:** `date`, `starts_at` and `ends_at` are recorded as context only and are not verified.
- **Credential:** the OAuth access token comes **only** from the environment variable `BEE_BOT_SHEETS_ACCESS_TOKEN`. Writes need the `spreadsheets`, `drive.file` or `drive` scope. There is no token argument, and the token is never printed or saved. A missing token, or one that looks like a placeholder, is a clean blocker.

**Modes.**

```bash
.venv/bin/python scripts/sheets_copy_probe.py .bee-bot/pilot-inputs.json              # preflight: config + credential presence, NO network
.venv/bin/python scripts/sheets_copy_probe.py .bee-bot/pilot-inputs.json --read-only  # 1 GET + preconditions, no write
.venv/bin/python scripts/sheets_copy_probe.py .bee-bot/pilot-inputs.json --execute    # guarded one-cell write (Lead only)
```

These conditions block before any request is sent: `write_enabled: false` (for `--execute`), a missing or placeholder credential, and any config violation.

**`--execute` sequence.**
1. `GET` the bounded range with `valueRenderOption=FORMULA`. The raw "before" read is saved privately first.
2. Check the current D and J. If either is a formula, stop with `FORMULA_TARGET`. If either differs from `expected_d`/`expected_j`, stop with `EXPECTED_SNAPSHOT_MISMATCH`. Both stops happen before any PUT, and a row shift caused by insertion is caught here.
3. `PUT` the quoted-tab D cell with `valueInputOption=RAW`, body `{"range", "majorDimension": "ROWS", "values": [[test_value]]}`. The response must report `updatedCells == 1`.
4. `GET` the whole range again. Exactly one cell may differ: the selected D, now holding `test_value`. J must be unchanged.
5. Only if step 4 verified and `restore_original` is true: `PUT` the original D, then `GET` and confirm the entire range equals the "before" read.

**Result states.**

| State | Meaning |
| --- | --- |
| `preflight_ok`, `read_ok` | Checks passed; nothing written |
| `missing_credential`, `precondition_failed`, `read_failed` | Stopped before any write |
| `write_rejected` | The PUT got a 4xx, so it was clearly not applied |
| `write_uncertain` | Timeout, 5xx, `updatedCells != 1`, or a readback mismatch |
| `unexpected_concurrent_diff` | Another cell (or J) changed between reads |
| `verified` | The test value was written and verified; no restore was requested |
| `restored` | The original value was put back and the whole range confirmed |
| `restore_uncertain`, `restore_rejected`, `restore_unverified` | The restore step did not complete cleanly |

After any uncertain, rejected or unexpected outcome the probe does **not** restore or retry. Ops reconciles by hand, using the private evidence.

**Output.**
- **Public output** (stdout, exit code 0 on success and 2 otherwise) lists the state, the code, HTTP statuses and counts, changed cell references, whether the guard is unchanged, and the names of the evidence files. It never includes the token, request URLs, the spreadsheet ID, the tab name or any cell values.
- **Private evidence** (mode 0600) is written to `evidence_dir`: the raw `before`, `after-write` and `after-restore` reads, `scoped-changes` with before/after values, and a summary copy.

**Limits.**
- **No compare-and-set.** An edit by ops between the last GET and the PUT is overwritten without detection (`test_LIMITATION_no_cas_edit_between_get_and_put_is_overwritten`).
- **Self-healing between reads.** A concurrent edit that reverts itself between two GETs is not seen.
- **Scope of proof.** A single-cell test does not verify stable anchors, roster mapping, merged-cell semantics or multi-cell (swap) behaviour. It shows only that one RAW D write on the copy works and stays scoped.
- **Real error behaviour unverified.** Normal GET/PUT/restore succeeded on the copy; quotas, timeouts and error responses are still covered only by mocks.

## 9. QA-SHEETS repair (S1–S8), pending Lead acceptance

The repair covers the QA findings in `docs/QA_REVIEW_2026-10-11.md`:

| Finding | Fix |
| --- | --- |
| S1 | Integer-valued STT strings are data rows. Populated non-data rows are `UNCLASSIFIED_ROW`, which blocks writes. |
| S2 | An unrecognised date or weekday header gives `INVALID_DATE_HEADER` and resets the date. |
| S3 | Pinned identity, plus a transport write bound to the workbook and tab. |
| S4 | Readback re-validates details, scope and overlaps. |
| S5 | Re-read and re-validate before each write. |
| S6 | `SCHEDULE_MALFORMED` is raised for malformed rows or merges, and `MERGED_KEY_CELL` for merges over A or D. |
| S7 | IDs are compared after whitespace normalisation, a non-canonical provenance ID is rejected, and the denylist still wins. |

**S8 completion guard.** `service._reconcile` now checks the current full assignment list for every planned coach (both swap sides), validates each target's presence/uniqueness and confirmed details on that read, and requires explicit `True` from `verify_applied` when the adapter exposes it. The adapter hook validates coverage, pinned identity, details and overlaps on another fresh read. Read failures and failed verification keep `reconciliation_required`; detected overlaps use `APPLIED_SCHEDULE_CONFLICT`, other guard failures use `APPLIED_VERIFICATION_FAILED`. Target mismatch retains `WRITE_NOT_VERIFIED`. Reservation and applied cells remain unchanged. Unchanged failures produce one ops alert across repeated reconciliation and restart maintenance. `JsonSchedule` also receives the full-schedule overlap guard without requiring an adapter hook.

Proof is in `tests/test_reconcile_guard.py` and the S8 tests in `tests/test_sheets_adapter_core.py`: post-write success/uncertain paths, both swap coaches, coverage loss, pinned tab change, room/daypart drift, ops reconciliation, cancel/withdraw while locked, and restart maintenance. Ops can resolve a conflict manually and reconcile to completion without another bot write. The recovery audit additionally reproduced and repaired an S1 edge: changing A to `STT` must not hide a populated assignment or a post-write overlap. QA-owned tests and reports remain untouched.

Unchanged accepted limits: there is no compare-and-set, so an edit between the last read and a write is lost; ABA edits are invisible through the content-hash revision; writes are not atomic; and all checks cover a single tab.

## 10. Factory backend selection — constructed, but not live-proven

`schedule_factory.create_schedule(json_path=None, *, environ=None)` selects the backend from trusted local configuration only; neither the model nor a sheet name can choose it.

**JSON stays the default.** With no `BEE_BOT_SCHEDULE_BACKEND`, or with `=json`, the factory returns `JsonSchedule` from the explicit path, `BEE_BOT_SCHEDULE`, or `BEE_BOT_DATA_DIR/schedule.json`. A Sheets config present in the environment never enables a backend by itself, and an unknown backend value fails closed with `SCHEDULE_BACKEND_INVALID` instead of falling back to JSON.

**The Google backend is now constructed, not disabled.** This supersedes the earlier `SHEETS_BACKEND_NOT_READY` preparation note in this section: `BEE_BOT_SCHEDULE_BACKEND=google_sheets_test_copy` with `BEE_BOT_SHEETS_CONFIG` pointing at an absolute private JSON object outside Git now builds the Data-owned `GoogleSheetsTransport(config, credentials=None, http_client=None)` and wraps it in `SheetsScheduleAdapter`, setting `backend_name`. The config contract, credential handling, anchor modes and cell representation are specified in [`GOOGLE_SHEETS_SETUP.md`](GOOGLE_SHEETS_SETUP.md); this document does not restate or extend them.

The owner gate `_check_google_copy` runs twice, first on the config-derived provenance **before** any credential or transport is constructed, and again on `transport.provenance()`. It requires `kind == "test_copy"`, `owner_confirmed_copy is True`, a tab listed in `allowed_tabs`, and an allowlisted destination; `denied_source_ids` is a denylist that always wins, and a legacy `copy_of` alone never enables the backend. The roster comes from trusted config, never from column D. If the gate or the adapter rejects the result, the transport is closed and the error carries no private path or content.

**Runtime callers read the same environment.** `mcp_server.create_server()` builds its service through the factory, and `get_bot_context` reports `schedule_backend`, the provenance kind, `owner_confirmed_copy`, scope, writability and `compare_and_set`, with `live_integrations: true` and `actor_is_demo_persona: false` on the Google backend, while redacting the workbook ID, tab and config path. `zalo_worker` reads the same two variables, requires the config path for the Google backend, and selects a matching managed SOUL so the shared Zalo profile states that schedule data comes from the test copy.

**A profile switch requires explicit migration.** Changing an existing Hermes profile between the JSON and test-copy backends is accepted only as a recognised backend switch with a clean managed SOUL, and only when the operator passes `--migrate-profile`, which backs up the managed files and exits without any Zalo or model call. Any other drift stays a conflict. See [`WORKER_OPERATIONS.md`](WORKER_OPERATIONS.md).

**Mock tests are not live acceptance.** `tests/test_schedule_factory.py` covers JSON selection, the fail-closed backend and config checks, the owner gate, and a Google construction path with a substituted transport. `tests/test_google_sheets_transport.py` and the Google MCP test in `tests/test_mcp.py` drive the real transport class with injected credentials and `httpx.MockTransport`, so every HTTP response is fabricated locally. None of this is live acceptance:

- A dedicated service-account credential is now present outside Git. Lead ran bounded live GET/PUT checks on the authorized copy, separate from these mock tests.
- The developer-metadata anchor key and its per-row values are not ops-approved, so stable identity on the real copy is unverified.
- One live A–J read covered the 390 observed positions and took about 0.65 seconds. Quota, sustained latency, real error behaviour and full program coverage remain unproven; `production_ready` stays false.

Live acceptance additionally needs approved stable anchors, a trusted roster,
full schedule scope and ops acceptance. Section 8's completed admin probe is a
separate, narrow single-cell proof with its own token environment variable; it
is not the runtime path.
