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
