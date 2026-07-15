# VEGA

VEGA is a local agent for working with software projects. It uses local models
through Ollama, accepts tasks in natural language, builds bounded execution
plans, selects registered tools, analyzes project content, runs configured
checks, and prepares controlled changes.

VEGA is designed for supervised local development. It is not an unrestricted
shell or an autonomous publishing service: state-changing operations remain
subject to workspace, permission, and confirmation policies.

**Current stable release: v3.0.0**

## Capabilities

- Inspect project structure and read or search text files.
- Maintain project context, task state, notes, and local project memory.
- Plan multi-step requests and select tools from the production registry.
- Analyze local documents and use a local keyword-based RAG index.
- Inspect Git status, diffs, branches, and recent history.
- Run predefined terminal commands, tests, diagnostics, and smoke checks.
- Review changes and execute controlled bug-fix, feature, refactor, test, and
  review workflows.
- Create pending patches, apply approved changes, and recover workflows from
  checkpoints.
- Check documentation consistency and release readiness.
- Select Ollama model profiles for fast, coding, document, or deep-analysis
  requests.
- Display request-local plans, progress, confirmation waits, and completion
  metrics in the Operator Console.

## Requirements

- Windows or Linux. The CI matrix tests both platforms.
- Python 3.12, 3.13, or 3.14.
- Git for cloning the repository and using Git/release inspection commands.
- [Ollama](https://ollama.com/) for model-backed requests.
- `qwen2.5-coder:14b` for the default `code` and `docs` profiles.

Python dependencies are listed in [`requirements.txt`](requirements.txt).
Plain-text, Markdown, Python, JSON, and CSV document support is built in;
PDF and DOCX reading use the included `pypdf` and `python-docx` dependencies.

## Installation

Clone the repository and enter its directory:

```console
git clone https://github.com/n0dflt/vega-local-agent.git
cd vega-local-agent
```

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
ollama pull qwen2.5-coder:14b
python scripts\install_windows_launcher.py
```

The launcher installer creates `%USERPROFILE%\vega-bin\vega.cmd` and adds that
directory to the user `PATH` if needed. Restart the terminal after the first
installation when the installer reports a `PATH` change.

### Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
ollama pull qwen2.5-coder:14b
```

Start the Ollama service using the method provided for your operating system
before sending model-backed requests.

## Running VEGA

After installing the Windows launcher, start VEGA from any directory:

```console
vega
```

From the repository root on Windows, the project launcher is also available:

```powershell
.\vega.cmd
```

The supported Python entry point works from the repository root on Windows and
Linux:

```console
python scripts/vega.py
```

VEGA starts in the current repository workspace and displays the selected
model, runtime readiness, and the `vega ›` prompt.

## Using VEGA

Natural-language tasks are the main interface. For example:

```text
Check whether this project is ready for release.
Review the current changes and identify risks.
Find the cause of the failing test.
Analyze the project structure.
Check the documentation for inconsistencies.
```

VEGA classifies the request, builds a bounded plan, and selects tools that are
available under the current production policies. A request may produce a
read-only result, a preview, a pending patch, or a confirmation prompt. VEGA
does not promise to modify or publish a project without the required evidence
and approvals.

Slash commands are primarily for inspecting runtime state and explicitly
selecting controlled operations. Run `/help` in the CLI for the authoritative
command list and detailed subcommands.

## Main commands

| Command | Purpose |
| --- | --- |
| `/help` | Show the current CLI help. |
| `/status` | Show runtime, model, project, and internet status. |
| `/workspace` | Show the current workspace and task state. |
| `/model` | Inspect or select `fast`, `code`, `docs`, and `deep` model profiles. |
| `/file` | Use safe file listing, reading, finding, searching, and summaries. |
| `/git` | Inspect status, diffs, branch, and recent history. |
| `/test` | List or run predefined test groups. |
| `/release` | Inspect readiness, run release checks, or build release notes. |
| `/exit` | End the VEGA session. |

The complete command and subcommand reference is available in
[`docs/commands.md`](docs/commands.md).

## Safety model

- Tools are invoked through an explicit registry; arbitrary tool names and
  generated shell commands are disabled by production policy.
- Tool arguments are validated before execution, and filesystem operations are
  restricted to the active workspace and allowed paths.
- The permission policy is deny-by-default and fails closed when configuration,
  routing, or permission metadata is missing or inconsistent.
- `READ` and `DRAFT` operations may run automatically. `WRITE`, `EXECUTE`,
  `SEND`, `DELETE`, and `ADMIN` operations can require explicit confirmation.
- Terminal commands and test groups come from allowlisted configuration rather
  than model-generated command lines.
- Internet access is off by default. Enabling it and fetching a resource are
  separate controlled actions.
- Git commands exposed by the CLI are read-only. Commits, pushes, tags, and
  releases are not automatic CLI side effects.
- Managed patches, coding workflows, tests, recovery, documentation builds, and
  release checks retain their own confirmation and review gates.
- Bounded diagnostics omit raw prompts, tool payloads, results, confirmation
  tokens, and tracebacks. Session interactions are logged locally, so do not
  place secrets in prompts or project tasks.

See [`docs/security.md`](docs/security.md) for the complete security model and
its documented limits.

## Project structure

```text
scripts/       CLI entry points and project checks
core/          runtime, routing, planning, and orchestration
domains/       built-in domain definitions
tools/         registered project tools
workflows/     controlled coding and recovery workflows
permissions/   permission evaluation and session grants
config/        runtime policies and allowlists
rag/           local document indexing and analysis
ui/            terminal interface and progress rendering
tests/         automated test suite
docs/          technical documentation
```

Runtime data and local logs are stored under `data/` and `logs/` and are
governed by repository hygiene and diagnostics policies.

## Documentation

- [Architecture](docs/architecture.md)
- [Commands](docs/commands.md)
- [Roadmap](docs/roadmap.md)
- [Security](docs/security.md)
- [Changelog](CHANGELOG.md)
- [v3.0.0 release notes](docs/releases/v3.0.0.md)
- [Release notes](RELEASE_NOTES.md)

Version history and release-specific implementation details belong in the
Changelog and release notes rather than this README.

## License

VEGA is licensed under the Apache License 2.0. See [`LICENSE`](LICENSE) and
[`NOTICE`](NOTICE).
