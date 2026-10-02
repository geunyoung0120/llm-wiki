# Contributing

Use Python 3.11+. Keep the common CLI stdlib-only; the optional Claude adapter uses the pinned MCP SDK. Use a separate temporary vault/config/home when testing installation. Do not install a development checkout over an existing personal deployment or use real learning notes as fixtures.

Before proposing a change, read `docs/ARCHITECTURE.md` and `policy.md`. Add regressions for changed storage/protocol behavior and run the complete suite. Never introduce automatic saving, retries, interrupted-job replay, or load-time writes. Do not bypass sandbox/host permission restrictions to obtain a green live test.

A fixture/protocol test is not a live model semantic test; document validation scope honestly. User-reported output should be sanitized before it enters an issue or test. Keep private vaults, backups, job outputs, credentials, and local absolute paths out of commits.

Changes to installation paths must preserve existing config and conflicting destinations. Avoid reorganizing runtime files without adjusting symlinks and MCP registration. New adapters should reuse the common core rather than implement a second knowledge organizer.
