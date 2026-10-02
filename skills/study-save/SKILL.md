---
name: study-save
description: Use only when the user explicitly invokes study-save to preserve the current AI learning session.
disable-model-invocation: true
---

# Study Save

Run ONLY for a fresh deliberate user invocation of `$study-save` (Codex), `/study-save` (Claude Code), or an explicit request to run this named command. Mentioning the command, quoted text, session completion, important concepts, a goodbye, or a prior invocation does not authorize a save. If loaded without a current invocation, do nothing. Never suggest saving merely because study seems finished. Never install a hook, timer, watcher or automatic retry.

You are a transport adapter. The common command launches Codex, which performs ALL vault search, reading, integration and edits. Do not read or edit vault notes yourself, even when the host is Codex; use the same protected mechanism. Cleanup is disabled by default. Only if the user enabled cleanup in the common config may Codex propose removal of unnecessary notes during this explicit save, preserving useful knowledge and reporting removals with backup paths. Never change config to enable deletion on the learner's behalf. Cleanup does not authorize an unsolicited save.

Prepare a faithful learning-context packet from the conversation you actually have access to. Include the topic, explanations/evidence/examples, what the learner demonstrably understood, demonstrated misunderstandings and correction reasons, unresolved or contradictory claims, and supplied source links. Preserve useful nuance, not just final conclusions. Distinguish the learner's statements from assistant assertions. Do not invent missing earlier history, personal mistakes, sources or mastery. Exclude credentials and unrelated personal details. If compaction or unavailable attachments limit the packet, explicitly state that limitation. Do not decide the vault's note structure or pretend the source AI has verified its assertions.

Preserve mechanisms, useful worked calculations, comparison criteria and meaningful tables from the session, with their dates, conditions and uncertainty. Do not reduce a long lesson to a few conclusions. If local tools are unavailable or the context is empty, do not call study_save or the common command.

In the Claude Mac desktop app, use the local Study Save MCP `study_save` tool at most once with this packet as `context` and `source` set to `claude`. It immediately returns a `job_id`; `queued` or `running` is NOT completion. The explicit invocation authorizes this one operation; no extra native Mac confirmation is required. Host tool permission is separate and never authorizes an unsolicited save. Retrieve the result by calling read-only `study_status` with the same `job_id` and `wait_seconds=20`, continuing until `done`, `cancelled` or `unknown`. These calls never start or retry saving. If the initial response is lost, use `study_status` with no id to recover the latest receipt, and check its operation/source/time rather than assuming it is this request. Only `done` confirms completion; return its actual changes and backup report. A timeout or `unknown` does NOT prove failure or no writes. Do not claim failure, ask for a re-save or repeat `study_save` before checking status. If polling must stop or the user asks to stop, report pending with the job id. A later request to check that result only calls `study_status`, without approval or another save. No cloud or web MCP connection is supported.

In ChatGPT desktop local Work, Codex, or Claude Code, pass the packet via stdin to the installed common command:

```text
~/.local/bin/study-save --input - --source codex
```

Use `--source chatgpt` in ChatGPT local Work and `--source claude-code` in Claude Code. For the user's explicit test/alternate configuration, the command supports `--config /absolute/config.json`. Use a file-writing tool or properly quoted input so packet text is never shell code. If stdin forwarding is unavailable, create a packet in an OS temporary directory, invoke `--input /absolute/temp/packet.md`, and remove it in a finally/cleanup path. Do not write a raw conversation or transport packet into the vault or project. Do not launch the command until a nonempty packet is available.

Show the command's actual changes, correction/open-question report and backup path. Report failure without claiming success or automatically retrying. Do not repeat saving on later turns unless the user explicitly invokes it again. The CLI controls its own Codex worker; do not replace it with a direct vault edit.
