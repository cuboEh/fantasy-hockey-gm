# Private server development and overnight run

Prepared September 13, 2026. Commands below assume a Linux server reached by SSH;
replace example host/user/path values after confirming the server setup. They are
instructions, not evidence that a remote job has been started.

## Keep the public API-request repository separate

Inspection confirmed `cuboEh/fantasy-hockey-gm` is public and its remote main tree
contains only README.md. The local checkout contains additional commits and
uncommitted development. A clone of public main will not contain the working tool.

Recommended arrangement:

- Public `fantasy-hockey-gm`: keep the Yahoo API-request document unchanged.
- A new private repository, for example `fantasy-hockey-gm-dev`: development source,
  tests and docs only. Create a standalone repository, not a public fork.
- Ignored input bundle: transfer selected private inputs directly to your own server
  over SSH. Do not commit them even to the private development repository.

GitHub private repositories restrict access to their owner and explicitly granted
collaborators. A development branch inside a public repository is still public.
See [GitHub repository visibility](https://docs.github.com/en/repositories/creating-and-managing-repositories/about-repositories).

When creating the private repo, review the staged source changes and commit the
working tree locally first. Use `git add -u` plus explicit new source/doc paths;
review `git diff --cached --stat` and `git diff --cached`. The existing ignore rules
cover `.env`, local configuration, `private/`, `var/`, `snapshots/` and SQLite files.
Ignore rules do not retroactively remove tracked files or historical secrets.
Review the intended source/history before pushing it anywhere.

Example private-remote setup, to execute only after choosing this approach:

```sh
gh repo create cuboEh/fantasy-hockey-gm-dev --private
gh repo view cuboEh/fantasy-hockey-gm-dev --json visibility
git remote add private git@github.com:cuboEh/fantasy-hockey-gm-dev.git
git config remote.pushDefault private
git remote set-url --push origin DISABLED-PUBLIC-PUSH
git push private HEAD:main
```

Verify the new remote reports PRIVATE before the push. Do not push development to
the original public remote. On the server, clone the private repo using a credential
limited to that repo. A read-only credential is sufficient for an overnight run
that saves local commits and returns a bundle instead of pushing.

## Direct SSH alternative

A new hosted repository is not required tonight. A source snapshot can include
the current uncommitted files, excluding Git metadata, private inputs, credentials
and installed environments. Copy the source archive and selected-input archive
to the server separately. Extract only locally prepared archives into a new private
directory, then initialize a local Git repository there and commit the source
snapshot. This gives Codex a repository without giving it a public push target.

Example transfer after the local archives have been prepared:

```sh
ssh USER@SERVER 'umask 077; mkdir -p ~/hockey-overnight'
scp var/server-handoff/source.tar.gz USER@SERVER:~/hockey-overnight/
scp var/server-handoff/inputs-private.tar.gz USER@SERVER:~/hockey-overnight/
```

On the server:

```sh
cd ~/hockey-overnight
umask 077
mkdir checkout
tar -xzf source.tar.gz -C checkout
tar -xzf inputs-private.tar.gz -C checkout
cd checkout
git init
git add -A
git diff --cached --stat
```

Verify that the stage contains only source/docs/tests, then commit the snapshot
using your configured Git identity. Do not add ignored files with `-f`. The input
archive is sensitive and remains on your private machines; never attach it to a
public issue or release. Archive checksums belong beside the handoff.

## Inputs and tools the server needs

This chat and its configured tools do not automatically transfer to another Codex
installation. Supply AGENTS.md, the PRDs, this runbook and the saved acceptance
evidence as part of the handoff. Install/check Python 3.11+, uv, Git and Codex on
the server. Use `uv sync --locked` before the unattended run. Keep Codex credentials
in the server account's authentication storage, outside the repository.

Required selected inputs, preserving relative paths:

- The working board and its CSV under `var/mvp1-2026-09-11-final/`.
- A consistent SQLite backup of `var/draft-mvp1-2026-09-11.sqlite`, treated as an
  immutable input on the server. All rehearsal mutations use new copies.
- `var/schedule-20262027-2026-09-10.json`.
- `private/goalie-workload-review-2026-09-10-v2.json` and
  `var/goalie-start-rates-2026-09-10.json` for the existing coverage calculation.
- Saved practice states/reports referenced by PRD 1.0 and the coverage audit.
- Local league configuration if present, plus any specifically needed review
  inputs. Do not transfer OAuth tokens, browser profiles or unrelated downloads.

Record missing artifacts before launch. Synthetic tests can proceed without all
real inputs, but do not mark real-board acceptance complete from synthetic tests.
Set up a browser tool on the server and exercise one local dashboard page before
leaving it unattended. A successful API response does not replace visual checks.
Keep the dashboard bound to loopback; use SSH forwarding to inspect it remotely:

```sh
ssh -L 8765:127.0.0.1:8765 USER@SERVER
```

In another server terminal start the dashboard against a practice database, then
open `http://127.0.0.1:8765` locally. Do not change its bind address to expose it
publicly; the current app was designed for local access.

## Authenticate and preflight Codex

For a headless server, `codex login --device-auth` opens a device-code login flow
you complete in your browser. Availability depends on account/workspace settings.
See [official authentication guidance](https://learn.chatgpt.com/docs/auth).

```sh
codex login --device-auth
codex login status
codex exec --help
uv sync --locked
uv run python -m unittest discover -s tests -v
```

Check browser and permitted web-research access before starting. Choose the model
and spending/usage allowance explicitly on the server; no model change is implied
by these instructions. A six-hour wall-clock limit is not a token or cost cap.
Do not give the run broad access to unrelated server services or credentials.

## Run one bounded queue

Use a dedicated tmux session so disconnecting SSH does not close the terminal.
Inside it, create `var/overnight/run-plan.md` containing the absolute stop time,
model, input snapshot and permitted PRD 1.1 -> 1.2 chain. The last 45 minutes are
reserved for verification and handoff. The example below permits six hours;
replace the duration and run-plan deadline together if you choose another budget.

```sh
tmux new -s hockey-overnight
```

From the checkout inside tmux:

```sh
umask 077
mkdir -p var/overnight
timeout --signal=INT --kill-after=60s 6h codex exec \
  --sandbox workspace-write \
  -c approval_policy='"never"' \
  --json -o var/overnight/final-message.md \
  - < docs/reference/overnight-prompt.md \
  > var/overnight/events.jsonl 2> var/overnight/stderr.log
```

These flags were checked against the local CLI. Confirm the server CLI supports
them before use. Workspace sandbox settings may need an explicitly configured
writable uv cache or permitted network access for the planned research. Test that
configuration during preflight; an unattended run cannot answer approval prompts.
Do not disable all isolation on a general-purpose server just to bypass a setup
failure. Codex exec supports saved authentication, JSONL events and final-message
output: [official non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode).

The prompt requests completion of the bounded queue, not repeated self-generated
work forever. If the process exits early, read its final message and progress file;
do not blindly auto-restart it. A timeout can interrupt a test or leave uncommitted
work, so progress checkpoints are essential. Do not assume a process exit code of
zero means every PRD requirement passed.

## Return the result

Keep PRD 1.1's verified checkpoint separate from any PRD 1.2 work. The morning
handoff must identify both. Transfer reviewed source commits through the private
repo or a Git bundle; transfer ignored reports/exports separately over SSH. Review
and validate the changes locally before switching the draft launcher to them.
Never overwrite the real draft database with a server rehearsal database.

For a server-only snapshot repository, `git bundle create result.bundle --all`
packages local commits for private transfer; uncommitted changes are not included.
Preserve or explicitly report such changes before finishing. Retain the currently
verified local draft tool until its replacement passes acceptance.
