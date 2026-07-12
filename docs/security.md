\# VEGA Security



\## Security model



VEGA is a local project coding-agent with controlled access to files,

commands, Git, tests, project memory, and the internet.



Tools must use explicit policies and remain inside the project workspace.



\## File access



File Tools provide read-only access to project files.



Blocked operations and targets include:



\- paths outside the project root;

\- parent-directory traversal;

\- service directories such as `.git` and `\_\_pycache\_\_`;

\- environment files;

\- credentials, tokens, passwords, and private keys;

\- binary files;

\- symbolic links used for writable paths.



\## File modifications



Project files must not be modified silently.



Changes are prepared through Patch Tools:



```text

/patch propose <target> <proposal> \[reason]

/patch show <patch\_id>

/patch apply <patch\_id> CONFIRM

/patch rollback <patch\_id> CONFIRM

## Agent Mode enforcement

VEGA Agent Modes are process-local execution policies.

Modes with `allow_code_changes: false` block:

* `/patch apply <patch_id> CONFIRM`
* `/patch rollback <patch_id> CONFIRM`

The restriction applies to:

* `architect`
* `reviewer`
* `teacher`
* `release_manager`

The `coder` and `debugger` modes may perform confirmed patch operations. The exact
`CONFIRM` token, SHA-256 validation, workspace restrictions, and Patch Tools safety
checks remain mandatory in every mode.

Mode instructions added to the model context do not replace command-level safety
enforcement.

<!-- VEGA DOCGEN START: security -->
## Generated security snapshot

Project version: `v2.0.0`

### Documentation Builder policy

- Create missing files automatically: `false`
- Use Patch Tools: `true`
- Apply patches automatically: `false`
- Require confirmation token: `true`

### Limits

- Maximum document characters: `100000`
- Maximum generated documents: `10`

### Active policy files

- `config/allowed_commands.json`
- `config/internet_policy.json`
- `config/documentation_policy.json`
- `config/release_policy.json`

### Enforcement principles

1. Documentation targets must remain inside the project root.
2. Missing managed files are not created automatically.
3. Generated changes become pending patches.
4. Pending patches are never applied by `/docgen build`.
5. Patch application requires a separate explicit command.
<!-- VEGA DOCGEN END: security -->

## Release Manager security

* Release Manager is read-only.
* Automatic commits are disabled.
* Automatic tags are disabled.
* Automatic pushes are disabled.
* Automatic GitHub releases are disabled.
* Validation commands must be predefined.
* Release paths cannot escape the project root.

## Agent Orchestrator security

* Input and slash-command routing are deterministic.
* The model cannot turn ordinary chat text into a command.
* Automatic model-driven tool execution is disabled.
* The orchestrator grants no additional filesystem, shell, Git, or network permissions.
* Existing workspace, terminal, internet, patch, confirmation, and Git policies remain authoritative.
