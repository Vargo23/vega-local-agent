# VEGA commands

## /file commands

```text
/file
/file list <path>
/file read <path>
/file find <name>
/file search <query>
/file summary <path>
```

The file commands provide safe, read-only access inside the VEGA project root. They
block path traversal, service directories, sensitive files, keys, certificates, and
binary content. Use `/tools list` to display registered tools.


## /patch commands

```text
/patch
/patch list
/patch list pending
/patch list applied
/patch list rolled_back
/patch show <patch_id>
/patch propose <target> <proposal> [reason]
/patch apply <patch_id> CONFIRM
/patch rollback <patch_id> CONFIRM
```

`/patch propose` creates a pending patch without changing the target file.

`/patch apply` requires the exact `CONFIRM` token. VEGA verifies SHA-256 before
applying the patch, blocks stale patches, and creates an exact byte-level backup.

`/patch rollback` also requires `CONFIRM` and restores the original bytes.

Path traversal, sensitive files, service directories, and identical target and
proposal paths are blocked.

## /git commands

Safe read-only Git access:

```text
/git
/git status
/git diff
/git diff --cached
/git log
/git log <limit>
/git branch
```

`/git status` shows the short repository status.

`/git diff` shows unstaged changes. `/git diff --cached` shows staged changes.

`/git log` shows 10 recent commits by default. The optional limit must be an integer from 1 to 100.

`/git branch` shows the current branch.

Git Tools in v1.4.0 are read-only. Commit, tag, push, pull, checkout, reset, merge, rebase, configuration changes, and arbitrary Git command execution are unavailable.
