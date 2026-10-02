# Architecture and maintenance history

This document describes the public v0.1.0 preview. It is reference material, not permission to run a study operation. Runtime instructions are in `policy.md` and the shared skills.

## Contract and ownership

A fresh explicit user invocation is required for each save. A prior invocation, important concept, long session, completion, quoted command, or goodbye does not authorize another save. Load is read-only. Receipt lookup never invokes Codex. No watcher, scheduled write, automatic retry, or restart replay is installed.

The source GPT/Claude constructs accessible learning evidence. Codex alone performs semantic knowledge organization. Python stages files, executes Codex, validates output, and promotes changes. These boundaries hold even when Codex itself is the study host: its skill calls the common command rather than directly editing the real vault.

Manual-only enforcement uses host instructions and skill metadata, not an independent cryptographic proof of conversational intent. The tools are local single-user interfaces, not authenticated multi-user endpoints.

## Source map

| File/component | Responsibility |
| --- | --- |
| `bin/study-save` | Select operation by invoked name and call `study_save.main()` |
| `study_save.py` | Configuration, input, managed-note snapshot, Codex, validation, backup, promotion, read-only retrieval |
| `policy.md` | Semantic integration, uncertainty, sources, preservation, manual-write authority |
| `chat_bridge.py` | Claude MCP tools/prompts and backend process lifecycle |
| `desktop_jobs.py` | Immediate acceptance, locks, worker thread, durable receipts, bounded status reads |
| `install.py` | Explicit vault selection and conflict-safe shared symlink/config installation |
| `install_desktop.py` | Existing-config-preserving local Claude stdio registration |
| `doctor.py` | Read-only settings, Python, Codex flag and login diagnostics |
| `skills/` | Thin manual-only transport adapters shared across local hosts |
| `tests/` | Synthetic regression fixtures plus explicit opt-in live model tests |

Python 3.11+ is required. The common engine is stdlib-only; the optional MCP SDK is isolated in `.venv`. Keep the checkout path stable because installed commands/skills and Claude config point to it. No private vault or runtime state is part of the repository.

## Configuration and state

`~/.config/study-save/config.json` selects one vault and Codex executable, optional model, timeout, language, and cleanup. Public defaults are English and `cleanup=false`. First install requires an existing `--vault`; it does not create a guessed project vault. Existing config is preserved on reinstall; a conflicting vault selection is rejected.

`_settings()` resolves relative vault paths against the config directory, rejects a symlink/nonexistent root, and detects a parent directly above a child Obsidian root. State must be outside the vault. Timeout is bounded to 0 < seconds <= 3600; normal default is 600. Language is a nonempty short string without control characters; cleanup must be an actual JSON boolean.

The core save-state key is the first 24 hex characters of SHA-256 of the resolved **vault path**. Claude job receipts use a key of the resolved **config path**. This intentionally provides both same-config admission guards and cross-config same-vault write serialization.

## Context fidelity and semantic decisions

The packet should retain definitions, mechanisms, conditions, examples, useful calculations/tables, demonstrated understanding, real misconceptions with corrections/reasons, unresolved questions, dates/uncertainty, and supplied sources. Distinguish learner evidence from assistant assertions. Do not invent mastery, personal errors, missing history, citations, or source verification.

Codex searches synonyms, aliases, and related concepts and reads candidates before choosing an existing note update, a new concept, no-op, or an explicit unresolved conflict. It preserves useful existing content/manual organization, uses actual resolvable wikilinks, and does not archive conversation-shaped logs or enforce a rigid taxonomy. Repeated evidence alone should not manufacture changes. These are agent instructions, not a deterministic guarantee of semantic equivalence or correctness.

## Save pipeline

```text
Explicit invocation
  → main(): file/stdin/clipboard input; nonempty, <= 2 MiB
  → _settings(): selected existing vault and execution preferences
  → _save_lock(): nonblocking advisory same-vault lock
  → _read_notes(): original managed Markdown bytes
  → _attachments(): attachment filenames only
  → _stage(): disposable notes/ copy
  → _prompt(): common policy + explicit operation + untrusted JSON evidence
  → _codex(): one separate Codex worker and final report
  → strict postflight _read_notes() + optional _cleanup_plan()
  → refuse any removal/cleanup declaration when cleanup=false
  → _commit(): declarations, links, original conflict, backup, per-file application
  → _report_for_vault(): real paths and actual changes/backup report
```

Only ordinary UTF-8 `.md` notes are managed. Hidden files/directories, `.obsidian`, and `AGENTS.md`/`CLAUDE.md` are excluded. Managed symlinks/hardlinks/special files, unsafe relative names, and a snapshot exceeding 64 MiB are rejected. Strict worker postflight rejects additional non-Markdown/hidden files inside `notes/`. Attachment bytes are not supplied or parsed.

Codex runs `exec` in the temporary directory with `--ignore-user-config`, `--ignore-rules`, `--ephemeral`, `--skip-git-repo-check`, a workspace-write sandbox for save or read-only sandbox for load, `approval_policy="never"`, `project_doc_max_bytes=0`, output-last-message, and an optional configured model. The prompt travels on stdin. Authentication still uses the installed Codex environment. The task does not load unrelated global instructions/rules. It does not use a dangerous sandbox bypass; actual permissions depend on runtime capabilities.

A separate Codex process group allows SIGTERM/grace/SIGKILL cleanup on timeout/interrupt. Nonzero exit, missing/unsafe final report, or empty report fails before promotion. The temporary directory is removed on normal scope exit. Model/provider logging lies outside this project's local retention control.

## Validation, application, and recovery

`_commit()` requires exact correspondence between removed filenames and cleanup declarations, nonempty removal reasons, and valid surviving destinations for any provided `preserved_in` list. It validates changed-note content and links, then compares actual current Markdown against the original snapshot. External changes cause refusal rather than stale overwrite.

Changed notes must be nonempty, contain no known temporary snapshot references, and link to nonempty staged notes or known attachments without ambiguity. Removed targets are checked even from unchanged notes, including direct relative Markdown links. Code examples are excluded from navigational parsing. Unrelated broken links in untouched notes are not comprehensively repaired; external URLs are not verified.

If no changes exist, no write or backup occurs. Otherwise all managed original Markdown is written into a ZIP before application, flushed/fsynced, with a manifest of vault, changed/created/removed names and reasons. This is a Markdown backup, not a full attachment/settings backup.

`_note_parent()` pins directory descriptors with no-follow traversal. `_atomic_write()`/`_exchange()` replace complete files and inspect displaced originals. `_atomic_remove()` captures expected originals into a hidden holding file and checks actual bytes before deletion; concurrent edits are restored where safe or preserved at a reported path. `_remove_created()` guards rollback against removing later external edits. `RecoveryError` carries preserved locations.

Rollback is attempted safely after application errors. This is not a single all-note transaction; power loss, hard kills, disk failure, or external writes through already-open descriptors can require manual recovery. Preserve captured `.study-save-*` files. Inspect the backup manifest and restore selected notes deliberately rather than blindly replacing an entire vault.

Structural validation does not prove factual correctness or lossless semantic merging.

## Optional cleanup

Public deletion cleanup is off by default. When enabled in config, it is still confined to an explicitly invoked save. Codex may remove truly empty, untouched starter, unnecessary, or redundant notes based on actual content. Preserve unique knowledge, personal annotations, uncertainty, and open questions; merge useful content before deleting redundant files and repair incoming links. Names/dates/orphan status alone are not sufficient justification. Existing-note renames are prohibited.

For every removed note, write `cleanup.json` outside `notes/`, mapping relative filenames to `{ "reason": "...", "preserved_in": ["surviving.md"] }`. `preserved_in` is needed for merges, not pure empty/starter deletion. Reasons and surviving destinations are checked but do not prove content preservation. Disabled cleanup is enforced before `_commit()` even if a worker ignores its instructions and supplies a reason.

## Load pipeline

Load snapshots and stages existing notes, runs Codex read-only, verifies the staged bytes remain identical, translates citations, and returns a standalone continuation packet. It never calls `_commit()`. Empty vault retrieval skips Codex. It is not a write lock that freezes external editors; it reports the snapshot it read.

The packet includes relevant knowledge, recorded corrections, relationships, open questions, and supporting note names. Suggestions are distinguished from records; notes do not prove mastery. No matching knowledge must be disclosed instead of filling gaps with general model assertions presented as vault retrieval.

Default CLI output also goes to the macOS clipboard; connected adapters use `--no-clipboard`. Optional new-file export must be outside the vault, cannot overwrite an existing path, and pins the destination parent before execution.

## Claude asynchronous jobs

The bridge uses stdio, not an HTTP listener. `Backend` calls the common CLI using the base Python interpreter. `worker_environment()` removes known macOS launcher variables (`__PYVENV_LAUNCHER__`, `PYTHONEXECUTABLE`, `_`) that corrupted Korean paths for downstream Rust tools.

Production `JobManager` has `approve=None`: one explicitly requested job runs without an extra native confirmation. Host tool permission remains separate. Legacy optional approval fixture support does not describe the current default.

`start()` acquires a nonblocking operation lock, writes a UUID job id into it, persists an accepted receipt, and launches one daemon thread. Separate save/load locks permit one of each per config; concurrent same-operation requests return busy, not a queued future request. The core also locks saves by vault.

Receipts store id, operation, source, owner pid, creation time, status, final output, and completion time when persisted. Raw input context is not recorded; output can contain private knowledge. Atomic private-permission receipt replacement is used. Pending liveness is checked by held matching operation locks, not PID existence alone. Malformed JSON is skipped.

`study_status` reads an exact id or latest valid receipt and may wait up to 20 seconds. Latest lookup must be matched by operation/source/time. It does not start, approve, retry, or replay a job. Dead pending jobs become unknown. Completed reports survive process restart. Failed final recording cannot be treated as no writes.

| State | Interpretation |
| --- | --- |
| queued/running | Pending; not success |
| done | Successful backend report available; save may have no changes |
| unknown | Completion unclear; inspect real notes/backups, no automatic retry |
| busy | New operation not admitted; retrieve the existing job |
| not_found | Receipt absent/invalid; no conclusion about real note changes |
| awaiting_approval/cancelled | Compatibility fixture path, not default admission |

There is no unsolicited chat push. Claude must pull the completed result and report it. Backend acceptance, successful note application, persisted completion, and host delivery are distinct events.

The outer backend timeout is 3700 seconds; Codex's configured timeout is normally 600 and capped at 3600. Controlled shutdown closes admission and interrupts active CLI processes so they terminate their Codex groups, with escalation where needed. Jobs are not a persistent service guaranteed to survive app closure. Restart never replays them.

## Development history and known issues

The public project originated from a private local deployment. The following preserves reusable lessons without its private paths, job ids, notes, or backups.

| Problem | Root cause / observation | Implemented correction | Evidence and limits |
| --- | --- | --- | --- |
| Ordinary chat could not execute local save | Skill text is not a local execution capability | Shared CLI for local hosts; local stdio MCP for Claude | Supported scopes are explicit; web/cloud-only execution remains unavailable |
| Menu missing after local installation | Account skills, local skills, and MCP registration were confused | Separate account registration instructions from executable installation | Menu observation is not end-to-end model execution |
| Public web setup became too complex | Tunnel/remote OAuth added operational burden | Retired that path; app/local-only architecture | No public listener or OAuth server is included |
| Korean paths broke Rust execution | macOS shell/venv launcher environment propagated invalid path encoding | Sanitize selected environment variables and invoke base Python | Earlier controlled synthetic live tests observed correction |
| Orphan Codex processes on shutdown | Uncontrolled termination did not manage child execution | Track backends; cooperative interrupt; process-group cleanup | Hard crash/power failure is not cooperative shutdown |
| Notes written but source AI lacked result | Long single tool call and missing result recovery | Immediate job id, durable receipts, bounded read-only polling | Actual SDK synthetic timeout/reconnect recovery without another execution |
| Blank duplicates / broken links | Config selected a parent above the actual Obsidian root | Explicit actual root; nested-root guard; changed-note link checks; nonempty targets | Preserved private repair backup; no user notes included here |
| Missing calculations/comparisons | Packet/policy compressed substantive learning too aggressively | Preserve mechanisms, calculations/tables, conditions and unresolved issues; disclose unavailable context | Semantic completeness still requires result review |
| Redundant native confirmation | Named user command already authorized one operation | Remove production native dialog; retain host tool controls | Synthetic no-extra-confirmation tests; no host permission bypass |
| Starter/empty clutter | No declared guarded cleanup path | Optional policy-driven cleanup, reasons, link checks, backup, capture/verify removal | Public fork defaults cleanup off and enforces that choice |
| Filesystem/rollback races | Swapped parents, changed originals, output aliases, external writes during recovery | Pinned descriptors, no-follow operations, guarded exchange/capture and preserved recovery files | Regression coverage; no total power-loss transaction claim |
| Stale pending/corrupt receipts | PID-only liveness and malformed/final-record failure | Matching lock/id liveness, schema validation, unknown states | Regression tests, no replay |
| Claude load menu absent | Local load tool existed but account load skill was missing | Reuse shared load instructions for account registration | Installer does not automate account menu registration |
| Personal setup unsuitable for distribution | Private paths/history and implicit defaults | Source allowlist; explicit vault; configurable language; cleanup off; public docs/license/tests | Private deployment is kept separate |

### Unresolved host result delivery

A real earlier load completed after about 73 seconds and persisted its report. The first three 20-second status calls arrived and returned running; it completed shortly after the third response. Two later checks described by the host did not appear as incoming local requests. A later official SDK same-id lookup returned the existing report without running Codex.

Thus the backend completed and durable recovery worked, but the missing later host dispatch was not diagnosed. There was no established evidence that the app had closed, the Mac slept, or the server hung. A three-poll stop is not the current skill contract. Do not present this as fully fixed. Claude Desktop is a preview adapter; retain ids and explicitly recover the same result if needed.

Future diagnosis should correlate host dispatch attempts, local inbound calls/responses, and receipt timestamps for a deliberately requested test, rather than resubmitting automatically.

### Verification boundaries

Public regressions add configuration, default deletion refusal, explicit installation, and read-only doctor checks to the original storage/protocol tests. They use synthetic data. Earlier live integration evidence belongs to specific prior revisions and one scenario; it is not proof that this public fork has passed new live model or native-host end-to-end checks.

The preparation environment blocked a clean dependency download and GitHub API access, and its browser automation runtime was unavailable. Already-installed SDK dependencies could run the regression suite; that is distinct from a clean pip installation or remote CI. The checked-in macOS workflow needs to run on the public repository before claiming CI success.

## Extension rules

Add candidate search/embeddings, attachment/source extraction, or more adapters without creating a second knowledge engine. Source collection can be automated later; learning-session knowledge writes still require a fresh explicit save. Retain read-only load/status, guarded promotion, outside-vault recovery, no automatic retries/replay, truthful context limitations, and separate backend/host completion states.
