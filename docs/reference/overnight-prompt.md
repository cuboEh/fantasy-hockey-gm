Complete the bounded overnight development queue for fantasy-hockey-gm.

Read AGENTS.md, docs/reference/prd-workflow.md, docs/reference/overnight-server.md,
docs/PRD-1.1.md (or its activated root location), and
var/overnight/run-plan.md. User requirements in these documents are the handoff
from the originating conversation. Do not assume access to that conversation.

If the stop time or essential execution setup is missing, report exactly what is
missing before starting long work. Do not guess an actual draft slot or fabricate
private input data. Inspect existing code/tests first and implement gaps only.

Activate PRD 1.1 and work through its phases autonomously, recording real acceptance
evidence and local checkpoint commits. Do not ask for routine implementation
choices. Record blockers and continue independent authorized work. Never mark
unverified UI or real-data behavior Done. Keep private data and logs ignored.

After verified PRD 1.1 completion, checkpoint the release and follow its bounded
successor instructions: at most PRD 1.2, read-only post-draft roster audit, on an
isolated branch/worktree. No PRD 1.3 or unrelated expansion. Never tune forecasts
to acceptance examples or run unbounded simulation sweeps.

Do not push, publish, merge, change server services, or modify the actual draft
session. Server copies of real inputs are immutable; create new practice copies.
The public repository is only for the Yahoo API-access request. No Yahoo scraping,
browser automation against Yahoo, or roster writes. Local browser verification is
authorized. Respect the configured permissions and usage limits.

Update var/overnight/progress.md after each increment with FR IDs, changed files,
tests, blockers and next action. Reserve the final 45 minutes for checks and the
morning handoff. End when the defined queue is complete or the deadline is reached.
Write var/overnight/morning-handoff.md with the verified release commit, separate
follow-up work, launch/recovery commands, input freshness, actual verification and
no more than three manager actions. Report incompleteness candidly.
