# Changelog

## Unreleased

- Rename the public repository and project to **LLM Wiki** (`llm-wiki`) to reflect knowledge integration and retrieval together.
- Keep `study-save`, `study-load`, installation paths, and configuration compatible. The original v0.1.0 source archive remains available.

## 0.1.0 — Preview

First sanitized public distribution, derived from a private implementation.

- One Codex-based engine and shared manual-only save/load skills.
- Guarded snapshot promotion, Markdown backups, conflict detection, recovery-file preservation.
- Read-only retrieval and durable Claude job receipts/status recovery.
- Explicit vault selection on first install; conflicting commands/config are preserved.
- Configurable new-note/report language; English default.
- Deletion cleanup is opt-in and rejected before promotion when disabled.
- Read-only local diagnostics and macOS regression workflow.
- No personal learning vault, historical backup, runtime config, or private incident ids included.

Known preview limitation: Claude may stop retrieving a completed job's report. Same-id receipts allow recovery; universal host delivery is not claimed. ChatGPT local Work is experimental; ordinary cloud/web execution is unsupported.
