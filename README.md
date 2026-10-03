# LLM Wiki

Build and maintain a personal knowledge wiki from AI learning conversations, with **Codex as the knowledge-management agent** and Obsidian as the initial Markdown store.

LLM Wiki includes both `study-save` and `study-load`. Knowledge organization runs automatically after an explicit user command; saving is never triggered automatically. The repository was previously named `study-save`. Existing command names, skill names, and configuration paths remain compatible.

Study with GPT or Claude. Invoke `study-save` when you choose to preserve the lesson. Codex reads existing notes, updates or creates concepts, connects related knowledge, and retains corrections and open questions. Invoke `study-load` to retrieve knowledge for the next conversation.

**No automatic saves. No conversation watchers. No scheduled writes. No automatic retries.** The source AI forwards context; it does not directly edit the vault.

> **v0.1.0 preview · macOS first.** The local engine and synthetic protocol tests are covered by regression tests. Claude Desktop result delivery is experimental; a completed job can require an explicit same-id status check. Ordinary cloud/web chats cannot run this local CLI.

```text
Codex / Claude Code / local GPT tools ── manual skill ──┐
Claude Desktop ── manual skill + local stdio MCP ────────┤
                                                       ▼
                                                Shared Python CLI
                                                       ▼
                                               Codex + staged notes
                                                       ▼
                                              Validate → backup → apply
                                                       ▼
                                                One Obsidian vault
```

## What gets stored

Reusable concept explanations, mechanisms, examples, calculations, real corrections, unresolved questions, and links to related notes. This is not a transcript archive or a diary of chat sessions. Codex chooses note granularity and integration from the existing vault.

New notes and agent reports default to **English**, configurable per installation. **Deletion cleanup is disabled by default and enforced before promotion.** Existing useful notes and their language are preserved. Structural checks do not guarantee semantic accuracy; inspect important results.

## Requirements

- macOS; other operating systems are not supported by this preview.
- Python **3.11 or newer** available as `python3` for the installed command.
- Installed, logged-in [Codex CLI](https://learn.chatgpt.com/docs/developer-commands?surface=cli).
- A Codex CLI supporting the flags checked by `doctor.py`, including `--ignore-user-config` and `--ignore-rules`. Upgrade if diagnostics report missing flags.
- An existing Obsidian vault folder. Select the actual folder containing `.obsidian`, not a parent above it.
- For Claude Desktop only: its Mac app plus the pinned MCP SDK dependencies.

Codex/model service access is required. Provider access and usage limits depend on your own account. This project does not supply credentials or make model inference fully offline.

## Install the common local engine

Clone/download this repository and keep it at a stable path:

```sh
git clone https://github.com/geunyoung0120/llm-wiki.git
cd llm-wiki
```

Run from its root:

```sh
python3 --version
codex login status
python3 install.py --vault "$HOME/Documents/My Knowledge" --language English
python3 doctor.py
```

Replace the example with your existing vault. First installation requires `--vault`; it never guesses a user's knowledge folder. The core is stdlib-only, so Codex/Claude Code do not need the MCP dependency installation.

The installer links `study-save` and `study-load` into `~/.local/bin` and shared manual-only skills into `~/.codex/skills`, `~/.agents/skills`, and `~/.claude/skills`. Add `~/.local/bin` to your shell PATH if it is not already there. Start a fresh host session to discover skills.

It refuses to overwrite conflicting commands/skills and preserves existing config. If you already have a different personal Study Save installation, **do not replace its links or config to try this preview**. Use a separate OS account/home for isolated evaluation. `--home` exists for installation tests; normal runtime defaults still refer to the current user's config unless explicitly overridden.

### Use from Codex or Claude Code

```text
Codex:       $study-save
             $study-load cache invalidation
Claude Code: /study-save
             /study-load cache invalidation
```

The skill forwards accessible context to the protected common command. It does not require a manually attached Markdown file. If the host no longer has earlier conversation context, the packet must disclose the gap rather than invent it.

### Optional Claude Desktop connection

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-chat.lock
python3 install_desktop.py
```

Fully quit and reopen Claude. The registered **local stdio** tools are `study_save`, `study_load`, and `study_status`. No public server, tunnel, or OAuth setup is needed. Existing Claude configuration is preserved and backed up when changed.

Local MCP registration is not the same as installing a chat/account skill. See [Claude Desktop setup](integrations/claude-desktop.md) for manual skill instructions and result handling. Availability of account skill menus depends on your host/account. Tool permissions remain controlled by Claude; this project does not bypass them.

### ChatGPT and other study environments

A host with local command execution can use the same shared skills/CLI. ChatGPT local Work is an **experimental integration path**, not a promise that every ChatGPT app/chat exposes local tools. Ordinary ChatGPT Chat and web-only environments cannot directly invoke this Mac installation. Do not claim a save occurred when local tools are unavailable.

## Configuration

Created at `~/.config/study-save/config.json`:

```json
{
  "vault": "/absolute/path/to/your/Obsidian-vault",
  "codex": "/absolute/path/to/codex",
  "timeout_seconds": 600,
  "language": "English",
  "cleanup": false
}
```

Optional `model` selects your Codex model; initial installation preserves an existing Codex model selection where present. There is no hardcoded paid model requirement. Optional `state_dir` must point outside the vault. CLI `--config` and `--vault` allow deliberate overrides. Existing config is not silently rewritten by reinstalling; change it deliberately.

`language` may be another short language name such as `Korean`, `Japanese`, or `Spanish`. New material and final agent reports use it; operational CLI/status messages remain English.

To opt into deletion of genuinely unnecessary notes, deliberately set the JSON boolean `"cleanup": true`. Cleanup then occurs **only within your explicitly requested save**. Each removal requires a reason, valid remaining links, and a prior Markdown backup. Source skills must never enable it on your behalf. There is no cleanup timer or load-time cleanup.

## CLI usage

```sh
# Explicit save with a prepared learning packet:
study-save --input /absolute/path/session.txt --source other

# Explicit save using stdin (pass text as data, not shell code):
study-save --input - --source codex

# Read-only continuation packet:
study-load --no-clipboard -- 'cache invalidation'
```

Without `--input`, save reads the current macOS clipboard. Load normally copies its continuation packet to the clipboard; connected skills use `--no-clipboard`. `--output /outside-vault/new-file.md` can export a new load packet without overwriting an existing file or writing knowledge notes.

## Claude job results

Save/load return a `job_id` immediately; **accepted is not completed**. The host must retrieve the final output using the same id:

```text
study_status(job_id="the original job id", wait_seconds=20)
```

This is a Claude MCP tool call, not a shell command. It never executes Codex or changes notes. `queued`/`running` means pending; `done` has the actual report; `unknown` means completion cannot be established. A lost response does not prove no writes. Never resubmit a save/load automatically to check its result.

The server does not push unsolicited messages into the chat. If the host stops polling, ask it to **check the same job's result**. See [known issues and development history](docs/ARCHITECTURE.md#development-history-and-known-issues).

## Storage, privacy, and recovery

- Your vault holds reusable knowledge Markdown; no default raw conversation archive is created.
- Codex edits a temporary snapshot. Validated changes alone are promoted to the real vault.
- Pre-change managed Markdown is backed up under `~/.config/study-save/state/<vault-key>/backups/`.
- Claude status/final reports are retained under `~/.config/study-save/desktop-jobs/<config-key>/`; raw input context is not persisted there, but output may contain knowledge excerpts.
- `.obsidian` settings and attachment contents are outside managed note changes. Attachments are inventoried by filename, not parsed/OCR'd.
- Context and note data may be sent to the AI model service. Temporary execution does not promise that provider/app logs never exist.
- Multiple note changes are not one power-loss-safe filesystem transaction. Review backup manifests and recovery paths before manually restoring selected files.

Do not publish your vault, backups, state, receipts, credentials, or private local paths. They do not belong in source-control history. The repository includes synthetic fixtures only.

## Tests and contributing

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-chat.lock
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -q
```

Regression tests use temporary synthetic vaults and stub/model-free backend output. They exercise storage, configuration, concurrent edits, cleanup, and actual SDK stdio recovery without saving real user sessions. GitHub Actions is configured for macOS Python 3.11 and 3.13; a checked-in workflow is not proof that a remote run has passed.

Real model tests are opt-in: inspect `tests/live_smoke.py` or `tests/live_bridge_smoke.py`, then use their `--run` option only when deliberately requested. No automatic model execution is part of CI.

Contributions should preserve explicit-only writes, read-only load/status, one common Codex engine, and outside-vault recovery data. Read [the architecture and history](docs/ARCHITECTURE.md), [runtime policy](policy.md), [contribution guide](CONTRIBUTING.md), and [security guidance](SECURITY.md).

## License

[MIT](LICENSE). This is a community tool, not an official OpenAI, Anthropic, or Obsidian product.
