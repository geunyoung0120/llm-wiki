# LLM Wiki v0.1.0 preview

A local, explicit-only way to turn AI learning sessions into one Obsidian knowledge vault using Codex as the actual organizer.

The project and repository are now named **LLM Wiki** (`llm-wiki`). Both `study-save` and `study-load` are included. Existing commands, skills, configuration paths, and the original `study-save-v0.1.0.zip` asset remain compatible; the v0.1.0 tag and source archive are unchanged.

This public distribution is separate from the author's private deployment. It contains source, shared skills, synthetic regressions, installation instructions, configurable language, opt-in cleanup, diagnostics, and an MIT license. No private notes, backups, runtime configuration, or credentials are included.

macOS and Python 3.11+ are required for the supported setup. Codex must be installed, logged in, and compatible with the documented worker flags. Claude Desktop uses an optional local MCP adapter. Ordinary cloud/web chats cannot run the local CLI.

The regression suite passed locally using already-installed MCP dependencies. Fresh pinned-dependency installation and the synthetic regression suite subsequently passed in GitHub Actions on macOS with Python 3.11 and 3.13 for the original v0.1.0 commit. No new live model integration or native-host end-to-end success is claimed by these results.

Claude result delivery remains preview functionality: acceptance is not completion, and final reports must be retrieved with the same job id. No auto-save, auto-retry, or interrupted-job replay is added.
