# Claude Desktop adapter setup

1. Install the common engine and run `doctor.py` as described in the [README](../README.md).
2. Create the project `.venv`, install `requirements-chat.lock`, and run `install_desktop.py`.
3. Fully quit/reopen Claude. Verify local tools `study_save`, `study_load`, `study_status` are available.
4. If your account supports chat skills, create/import the **same** [Study Save](../skills/study-save/SKILL.md) and [Study Load](../skills/study-load/SKILL.md) instructions. These are transport instructions, not copies of the knowledge engine. Local CLI skill discovery and account skill registration are separate.

A host without an account skill menu can follow these instructions in a dedicated study project's instructions and invoke the named commands explicitly. This supplies instructions, not missing local tools. Do not pretend that slash-menu installation was automated by this repository.

## Host contract

- Only a fresh explicit `study-save` invocation calls `study_save` once with a faithful nonempty context packet and `source="claude"`.
- Only a fresh explicit `study-load <topic>` invocation calls `study_load` once. If the topic is missing, ask for the topic only.
- Long conversations, important ideas, a goodbye, or a prior invocation do not authorize new work.
- Capture the returned `job_id`. Call `study_status` with that same id and `wait_seconds=20` until terminal, unless the user stops the wait or the host cannot continue.
- If polling stops, report pending with the id. Do not invent results or resubmit the operation. A later result-check request only reads `study_status`.
- If the initial id is lost, latest-receipt lookup is available, but verify operation, source, and creation time before treating it as the request.
- Only `done` supplies a completed report. `unknown`, disconnect, or timeout does not establish failure/no changes.
- The account skill does not directly read or edit the vault. Codex does the actual knowledge work through the common command.
- Cleanup is off by default. Do not enable it by changing configuration on the user's behalf.

Host tool permission is distinct from manual operation authorization. Always-allow settings do not authorize unsolicited saves. There is no additional native dialog in the bridge and no bypass of Claude's own approval controls.

## Known limitation

Final output must be pulled; the bridge cannot post an unsolicited chat message. A real earlier retrieval completed while Claude stopped delivering later status calls. The durable report was recoverable, but the exact host-side dispatch failure was not resolved. Treat this adapter as preview functionality and retain job ids.

Official context: [MCP server development](https://modelcontextprotocol.io/docs/develop/build-server) and [Python MCP SDK](https://pypi.org/project/mcp/2.2.0/).
