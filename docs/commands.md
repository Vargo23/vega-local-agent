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
