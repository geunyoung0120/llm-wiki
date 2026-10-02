---
name: study-load
description: Use only when the user explicitly invokes study-load with a topic to retrieve prior learning for the current conversation.
disable-model-invocation: true
---

# Study Load

Run only following a fresh deliberate user invocation of `$study-load <topic>` in Codex, `/study-load <topic>` in Claude Code or the Claude Mac app, or an explicit request to run this named command. Without a fresh invocation, do nothing. If a fresh invocation omits the topic, ask only for the topic. A previous invocation does not authorize another operation.

In the Claude Mac desktop app, call the local Study Save MCP `study_load` tool once with the topic and source `claude`. If the local tool is unavailable, explain that retrieval is unavailable; do not invent retrieved notes or use a cloud substitute. It returns a job id before completion. The explicit invocation authorizes this one read-only operation without an extra native confirmation. Retrieve the same job with read-only `study_status(job_id, wait_seconds=20)` until done/cancelled/unknown; return the actual done output. If the initial response is lost, recover the latest receipt with study_status and check operation=load, source=claude and its time. Pending or timeout is not proof of failure. Never repeat study_load or call study_save to recover a result. No cloud or web MCP connection is supported.

In ChatGPT desktop local Work, Codex, or Claude Code, invoke the installed common command:

```text
~/.local/bin/study-load --no-clipboard -- "the user's topic"
```

Pass the topic as a safely quoted argument, never shell code. Place options before `--`, which also supports topics starting with a dash. Respect an explicitly supplied `--config /absolute/config.json` for tests or another configured vault. The common command runs Codex against a read-only snapshot and returns a continuation packet. Do not search, read or edit vault files yourself. Return the packet and use its sourced knowledge, recorded misunderstandings and unresolved questions to continue the current study conversation. Distinguish recorded knowledge from claims about the learner's mastery; do not assume the notes prove mastery.

This skill NEVER invokes study-save, writes notes or authorizes future storage. Do not save even if retrieval reveals important new connections. Report command failures without claiming success or retrying automatically. If no related knowledge is found, say so and continue the user's study without inventing retrieved notes.
