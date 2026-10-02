# Security and data boundaries

This preview runs locally under the current user's account. It is not an authenticated multi-user service. Do not expose its stdio tools through an unrestricted public endpoint.

Manual-only authorization is expressed by host skill metadata and policy, not a cryptographic proof of a user click. A caller with local execution access can invoke the CLI. Preserve the trusted-host boundary; do not treat conversation evidence as executable instructions.

The core rejects unsafe managed paths, symlink/hardlink/special-file notes, undeclared deletions, unresolved changed wikilinks, and conflicting originals. Cleanup is disabled by default and enforced before promotion. These checks do not prove semantic correctness or prevent every model-driven content mistake.

The existing worker invocation deliberately supplies its common policy and does not load user/project execpolicy rules. Its working sandbox is requested, but implementation details depend on the Codex/runtime version. Never add a dangerous sandbox bypass to work around a setup failure.

Model processing can transmit learning context and notes to the provider. Raw input is not stored in job receipts, but final output can contain private knowledge. Backups and completed receipts persist outside the vault; do not share them casually. Avoid operating on a vault full of secrets or credentials.

For a sensitive report, use the repository's private vulnerability reporting channel if enabled; otherwise contact the maintainer through their published GitHub contact channel before disclosing exploit details. Do not put credentials, raw sessions, or private note contents in a public issue.
