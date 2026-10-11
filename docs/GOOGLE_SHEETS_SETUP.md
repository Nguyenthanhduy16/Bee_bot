# Google Sheets test-copy transport

This is a Python backend behind `SheetsScheduleAdapter`. Bee Bot MCP remains
the only model-facing business interface. There is no generic Sheets tool,
Workspace skill/toolset, ChatGPT connector dependency, or shell-based write.
`schedule_factory.py` now constructs this transport and the business adapter
from an explicit private config. The Zalo worker and its Hermes MCP profile
select the same backend; switching an installed profile requires an explicit
`--migrate-profile` backup/migration. This transport does not start the worker.
The original source XLSX remains read-only.

## Constructor and private config contract

```python
GoogleSheetsTransport(config, credentials=None, http_client=None)
```

`config` is a mapping, not a filename. `BEE_BOT_SHEETS_CONFIG` is an absolute
path to a private JSON file containing this mapping. The existing
`pilot-inputs.json` is not implicitly accepted as this schema.
The transport copies the mapping at construction and pins one workbook,
exact tab title and numeric `sheet_id` (gid, not tab position). No environment,
root/profile token fallback or discovery of another workbook is performed.

Synthetic example; replace placeholders privately, never paste secrets in chat:

```json
{
  "spreadsheet_id": "owner-confirmed-copy-placeholder",
  "tab": "Synthetic schedule",
  "sheet_id": 42,
  "owner_confirmed_copy": true,
  "allowed_spreadsheet_ids": ["owner-confirmed-copy-placeholder"],
  "denied_source_ids": [],
  "allowed_tabs": ["Synthetic schedule"],
  "people": [
    {"person_id": "sample-person", "display_name": "Sample Person",
     "role": "labcoach", "active": true, "sheet_names": ["Sample Person"]}
  ],
  "credential_path": "/absolute/private/bee-bot/google_credentials.json",
  "expected_anchor_count": 6,
  "anchor_mode": "metadata",
  "metadata_key": "existing-approved-position-id-key",
  "write_enabled": false,
  "allowed_write_anchors": [],
  "copy_of": null,
  "max_rows": 10000,
  "timeout_seconds": 20
}
```

Required keys: `spreadsheet_id`, `tab`, `sheet_id`,
`owner_confirmed_copy` (exactly true), `allowed_spreadsheet_ids`,
`denied_source_ids` (explicit list, possibly empty), `allowed_tabs`, `people`
(trusted roster, never inferred from column D), `expected_anchor_count`
(positive ops-approved count), `anchor_mode`, and its mode-specific key.
`credential_path` is required unless a credentials object is injected.
The Core factory additionally owns `allowed_tabs` and `people` (the explicit
trusted roster) in its private config; these may be supplied in the same mapping
and are not interpreted or inferred by this transport.
Unknown/missing credentials mean unavailable authentication, not lack of copy
permission. The copy's owner authorization is already resolved; do not request
it again. Missing source identity is represented by `copy_of=null`, never an
invented ID. Known source IDs belong on the denylist; deny overrides allow.

Optional defaults: `write_enabled=false`, `allowed_write_anchors=[]`,
`copy_of=null`, `max_rows=10000`, `timeout_seconds=20`. Writes require both
enabled writes and a separately approved anchor allowlist. Core should preserve
any narrower assignment/cell authorizations when constructing that allowlist.
Neither an approved tab nor an approved copy alone authorizes all D cells.
`max_rows` must cover the tab's entire grid row count, including blank rows;
larger tabs fail closed rather than being truncated. Changing pins or approvals
requires a new transport instance; editing a config file does not repoint it.

`credentials` and `http_client` are injection seams for offline tests. A supplied
credential must be scoped to Sheets; a supplied client must disable retries and
redirects, and must not log payloads. The transport owns/closes only clients it
creates; callers close injected clients. `close()` releases its own HTTP client.

| Method | Contract |
| --- | --- |
| `provenance()` | New dict with `kind=test_copy`, `spreadsheet_id`, `tab`, `sheet_id`, optional `copy_of`, `owner_confirmed_copy=true`, `contains_real_data=true`; no network call. |
| `read_tab()` | Fresh pinned GET; `{"rows": [{"row": 1, "anchor": null, "cells": {"A": null, ... "J": null}}], "merges": [{"start": 4, "end": 5, "columns": ["B", "C"]}]}`. Rows and merge bounds are 1-based/inclusive. |
| `write_d(anchor, value, spreadsheet_id, tab)` | Matching pins, enabled/allowlisted anchor, nonblank string; fresh read/anchor resolution; exactly one D cell via PUT `values.update` with `RAW`. Returns `None`; successful receipt alone is not business completion. |

## Credentials: recommended persistent-bot setup

At offline acceptance, credentials had not yet been supplied. The owner has
since supplied a dedicated service-account key and enabled Sheets API on the
test project. Lead completed the bounded live checks recorded below. The setup
steps for another deployment remain:

1. In an owner-controlled Google Cloud project, enable **Google Sheets API**.
2. Create a dedicated service account for the persistent bot. Grant no broad
   project roles or domain-wide delegation for this workbook use case.
3. Share **only the authorized test-copy workbook** with the service account's
   email as **Editor**. Do not share the original source workbook.
4. If a JSON key is the chosen deployment credential, download it directly into
   an explicit private location outside Git. Use directory mode `0700` and file
   mode `0600`; never send the key, token or client secret through chat. Point
   `credential_path` at the absolute filename. Keep config/roster/sidecar/evidence
   with workbook IDs and names outside Git too.

   The transport enforces this location contract before reading anything and
   fails closed, without naming the path, if it is not met:

   | Requirement | Rejected with |
   | --- | --- |
   | Absolute path, present | `SHEETS_AUTH_REQUIRED` |
   | Outside this repository, literally and after resolving `..`/symlinks | `SHEETS_AUTH_LOCATION` |
   | Not reached through a symlink (final component or parent directory) | `SHEETS_AUTH_LOCATION` |
   | A regular file, not a directory or device | `SHEETS_AUTH_LOCATION` |
   | Not readable or writable by group or others (`0600`) | `SHEETS_AUTH_INSECURE` |

   Permission and regular-file checks run on the opened descriptor, so the file
   cannot be swapped between the check and the read. A credential inside the
   checkout is refused by path even if `.gitignore` would cover it, because an
   ignore rule is not a guarantee against committing it. Keep the credential
   directory owner-only (`0700`): a replaceable parent directory creates a
   check-to-open race, and a hardlink has no path relationship to its other name.
5. Runtime `google-auth[requests]` obtains/refreshes tokens with only
   `https://www.googleapis.com/auth/spreadsheets`, and the credential must
   already be a **Sheets-only grant**: an authorized-user token recording any
   additional scope is refused before any Google call, and so is a service-account
   key file that declares broader scopes. File sharing and transport
   guards restrict the destination; OAuth scope itself is not D-only or
   workbook-specific. Keep writes disabled until Lead/QA accepts the candidate
   and ops validates live reads, anchors and coverage in the approved copy.

No private key is read by the model or copied into the Hermes profile. Credential
objects stay in the service backend. Refresh is before each dispatch as needed,
in memory only; this transport does not rewrite token/profile files. Key rotation
or refreshed configuration requires an admin-controlled restart/new instance.
An environment that forbids service-account keys can supply an equivalent
Sheets-scoped credential object through the backend integration; ADC discovery
is deliberately not automatic here.

## Existing Hermes authorized-user tokens and actual helper evaluation

The installed skill at
`/home/duy/.hermes/profiles/bee-zalo/skills/productivity/google-workspace`
exists. Lead's managed-Python `setup.py --check` returned exit 1,
`NOT_AUTHENTICATED`; bee-zalo has no `google_token.json` or client secret.
Root/profile client credentials are absent, and `gws` was not found.

The actual installed `scripts/setup.py` supports `--check`, `--check-live`,
`--client-secret`, `--auth-url`, `--auth-code`, `--revoke`, `--install-deps`.
It **does not support `--services sheets` or `--format json`**: argparse rejects
these despite the skill prose. Its default `SCOPES` includes Gmail, Calendar,
Drive, Contacts and Docs as well as Sheets. The inspected root and Hermes source
copies have the same broad scope list and no service-selection flag. PM provides
dependency/environment management, not a discovered Sheets-only consent CLI.
Do not run the unmodified helper to request broad Workspace consent.

**The shared Hermes Workspace token must not be reused here.** A token carrying
Gmail, Calendar, Drive, Contacts or Docs scopes alongside Sheets is refused with
`SHEETS_AUTH_SCOPE` before any Google API call, including before any refresh.
Narrowing a broad grant at refresh time is not attempted: the refresh token
would still carry the broader authorization, so one leaked credential or one
coding mistake would reach mailbox and Drive data. Revoking or re-consenting the
shared token is the owner's decision and is out of scope here.

What *is* supported is a **dedicated Sheets-only token in the same
authorized-user format** Hermes writes, pointed at by `credential_path`. That
file's grant must be exactly `https://www.googleapis.com/auth/spreadsheets`.
The `type` key may be absent, as Hermes sometimes omits it, and the transport
normalizes that in memory; `scopes` may be a list or a space-separated string,
and the legacy `scope` string is accepted. Missing, readonly-only, unrelated or
broader grants all fail closed. There is no missing-file fallback to the profile
or root, and no broad-consent fallback. The private file is only ever read, never
rewritten, and a refresh that comes back without exactly the Sheets scope blocks
dispatch.

Obtaining such a dedicated token needs its own consent, because the installed
helper requests the broad list. If authorized-user OAuth is chosen later instead
of the recommended service account, the least-duplication option is an
**ops-only private wrapper** around
the installed helper. Load `scripts/setup.py` with `importlib`, replace `SCOPES`
with the single Sheets scope **before invoking any auth function**, and override
`TOKEN_PATH`, `CLIENT_SECRET_PATH`, `PENDING_AUTH_PATH` to an isolated private
directory. Then reuse its `get_auth_url()` and `exchange_auth_code()` functions
and its saved state/PKCE verifier. Use Hermes' managed Python discovered through
`hermes --print-runtime-command`; `pm.ensure_import("google")` remains owned by
that environment. Feed the callback locally from a private file/input, not a
chat message or command argument. The same wrapper/scopes/private pending path
must be used for both steps. Do not patch the installed helper, copy/reimplement
the PKCE flow, or fall back to broad consent. No wrapper has been installed or
OAuth performed by this candidate.

`scripts/google_api.py` is useful as token-format reference but is not a runtime
dependency: its generic update defaults to `USER_ENTERED`, supports arbitrary
ranges/append/create, and lacks our pins/metadata/coverage guards. Do not shell
out to its writes or expose the skill to the worker/model.

## Anchors, cell representation and coverage

Metadata mode reads **existing** developer metadata with the configured trusted
key and a nonblank opaque `metadataValue` for each canonical assignment row.
Locations must identify exactly one ROW on the pinned gid. Duplicate values,
multiple anchors per row, wrong dimension, missing coverage or count drift
fail closed. No metadata, hidden ID column or other identity data is created or
changed. Ops must independently establish that this key/value scheme is stable;
the transport does not derive IDs from STT, row numbers or names.

The alternative `anchor_mode="test_sidecar"` requires an absolute private
`anchor_sidecar_path` and this trusted snapshot shape:

```json
{
  "spreadsheet_id": "owner-confirmed-copy-placeholder",
  "tab": "Synthetic schedule",
  "sheet_id": 42,
  "structure_fingerprint": "<sha256 from structure_fingerprint(rows, merges)>",
  "anchors": [
    {"row": 4, "anchor": "ops-approved-opaque-id",
     "fingerprint": "<sha256 from row_fingerprint(cells)>"}
  ]
}
```

Fingerprint helpers are offline utilities. Ops supplies/approves IDs; hashes
validate placement and are not IDs. The structure hash includes row positions,
all A–J cells except mutable D/J, headers and merges; each entry also checks
its row fingerprint. D/J edits do not invalidate it. Insertion, sorting, row
movement, date/header changes, grid-size or merge changes require a separately
reviewed sidecar. No fuzzy matching or automatic ID relocation is attempted.
This is a test-only sidecar, not production-safe movable identity.

The [spreadsheet GET](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/get)
requests one quoted A–J grid range and a field mask for ID/gid/title, merges,
`data.rowMetadata.developerMetadata`, `effectiveValue` and `userEnteredValue`.
Row-attached metadata is returned in `GridData.rowMetadata`, not in the
spreadsheet- or sheet-level metadata arrays. One response avoids
joining separate metadata/value snapshots. Effective values preserve numbers,
strings, booleans and blanks, instead of the values API's default formatted
strings. A–I formulas and error values block scope; J formulas remain literal
expressions and are never evaluated or written by the bot. No merged values
are filled in here: the adapter applies its canonical merge/date mapping.
Anchor coverage conservatively includes numeric/STT data rows, populated D and
B–G content. Anchored data rows need positive integer STT (numeric or numeric
string); blank/text/invalid STT fails closed, never creates or selects an ID.
Adapter/service still validate full dates, roster and overlaps.

## Failure handling and limits

Read 429 is surfaced as `SHEETS_RATE_LIMITED`; other read failures use structured,
sanitized errors. There are no automatic read retries in this candidate.
Refresh failures happen before Sheets dispatch. Write 400/401/403/404 is a
`TransportRejected`; write 429/5xx, redirects, timeouts, connection errors and
invalid/mismatching receipts are `TransportTimeout` (unknown outcome).
There is **no write retry**, append, batch update, metadata write, rollback or
automatic restore. Adapter/service owns readback and read-only reconciliation.

PUT uses [values.update](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/update)
with `valueInputOption=RAW`, one row containing one value, and exactly `D<n>`.
J and every other column are absent from the write. Sheets has no value-level
compare-and-set in this protocol: an edit/row move/tab rename between the final
GET and PUT remains a race. Swap is not atomic; partial writes remain uncertain.
Full program coverage, roster identity, metadata behavior after real insertion,
live quota/error handling and service recovery remain unverified. The bounded
live checks below establish only their stated scope; do not claim pilot acceptance.

Errors never include raw exception text, Google bodies, URLs, IDs, cell names or
values. HTTP/auth library request logging is suppressed only during private I/O
in the current context. There is no diagnostic payload logging. Test injected
clients/credentials must not introduce their own unsanitized logging.

## Bounded live check on the authorized copy — 11/10/2026

Lead stored the service-account credential outside Git in an owner-only directory
(`0700`) with file mode `0600`. Authentication and a Sheets metadata GET
succeeded. The pinned tab has 1000 grid rows and 20 columns. A backend-shaped
read of A–J normalized 390 numeric-STT positions and 434 relevant merges in
about 0.65 seconds; transport coverage found exactly those 390 positions and
no extra candidate rows. No row developer metadata exists yet.

The separate admin probe confirmed D278/J278 against the private snapshot,
temporarily wrote only D278, verified J278 was unchanged, restored D278 and
confirmed the bounded range matched its original state. A prior read-only
check made one GET; the execute phase made three GETs and two PUTs. A subsequent
same-value D278 PUT returned HTTP 200, `updatedCells`, `updatedRows` and
`updatedColumns` all equal to 1, and a quoted `updatedRange` accepted by the
runtime transport for this Vietnamese tab title. D278/J278 were unchanged on
readback. Private values and request evidence remain outside Git. Runtime
`write_enabled` remains false; the worker remains stopped.

This does not establish anchor stability, trusted roster coverage, concurrent
edit handling, swap recovery, quota tolerance or the second Zalo account's
acceptance. Do not enable the runtime Google backend for write until those gates
are accepted.

## Row metadata trial and copy setup — 12/10/2026

The owner chose row-attached developer metadata on the test copy. Lead created
a temporary synthetic tab, attached one `PROJECT`-visible row ID, inserted and
moved the row, verified the ID followed it, then deleted the tab and confirmed
the ID was gone. A first trial on the actual schedule row exposed a transport
bug: `spreadsheets.get` puts row IDs under `GridData.rowMetadata`, while the
transport only read workbook/sheet metadata arrays. The trial ID was removed.
The transport and mock tests now read and validate the row-level location; a
second one-row live trial resolved row 278 and removed its trial ID.

After a fresh structure/coverage check, Lead attached 390 opaque IDs with key
`bee_bot_pos_v1` to exactly the 390 observed assignment rows in one atomic
`batchUpdate`. A private plan outside Git records the planned row fingerprints,
IDs and returned metadata IDs. Readback found all 390 at the planned rows and
the runtime `read_tab()` passed. The metadata uses about 18,720 characters of
the sheet's 30,000-character metadata allocation. A bounded live transport
`write_d` call targeted only the approved D278 anchor with its existing value;
the transport accepted Google's receipt and a subsequent full A–J read was
identical, including J. Runtime configuration remains write-disabled and the
worker stopped.

The 346 named positions yield 51 distinct column-D names. A private CSV of
candidate names was prepared for ops to verify; it is **not** a trusted roster
and contains no accepted person ID or Zalo mapping. Google metadata follows
insert/move in the synthetic trial; sort/copy-paste, concurrent edits, full
schedule coverage and business acceptance remain unverified.

## Offline verification

From `/home/duy/VinAI/Bee_Bot`:

```bash
.venv/bin/python -m pytest -q tests/test_google_sheets_transport.py
```

The tests use `httpx.MockTransport`, synthetic tab data and mocked refresh. No
real Sheets/Zalo/model calls or runtime/profile/inbox edits are required.
Factory and worker wiring have separate offline tests in
`tests/test_schedule_factory.py` and `tests/test_zalo_worker.py`. These checks
do not establish live Sheets acceptance. An ops-verified roster, full schedule
scope, approved runtime write anchors and the second Zalo account's test window remain inputs
for a controlled end-to-end trial.
