# Safe Git collaboration and recovery

## Four-person daily workflow

Use the [onboarding ownership table](TEAM_START_HERE.md#8-four-workstreams-and-file-ownership):
A owns evaluation semantics, B frontend, C backend/integration, D independent
QA/labels/submission. C coordinates shared contracts; D maintains shared docs.
These are team conventions, not GitHub access restrictions.

1. **Claim scope and a base commit.** Agree owned paths and expected output before
   editing. Read status/inventory, inspect your own dirty/untracked work, and fetch.
   Use a new branch and your own clone/worktree; never operate another person's
   checkout. For example, from a confirmed repository:

   ```sh
   git fetch origin
   git worktree add -b codex/frontend-topic ../cqa-frontend-topic origin/codex/local-mvp-integration
   ```

   Choose unique names/paths. AI sessions follow the same rule: one owner per
   branch/worktree, explicit files, base SHA and handoff. Another agent's local
   commit is not shared code until that owner publishes it.
2. **Keep one deliverable per PR.** Commit only named reviewed files; inspect
   `git diff --cached` and every outgoing commit. Exclude credentials, original
   PDFs/full DEV, real calls, control input, human exports and generated outputs.
   Push only your feature branch to the approved destination after content review.
3. **Test before requesting review.** Follow [exact onboarding commands](TEAM_START_HERE.md#4-tests-and-reproducibility).
   A/C run the application suite; B runs both Node suites plus affected backend
   tests; D runs independent QA against an explicit engine snapshot. Record base
   and head SHAs, commands, passed/failed/skipped counts and limitations. For
   docs-only changes check links, current source references, whitespace and
   confidentiality; no paid evaluation is a routine PR check.
4. **Ask one teammate to review.** App/docs PRs target `codex/local-mvp-integration`,
   not default `main`. QA-only PRs may target `feature/cqa-independent-qa` until C
   agrees integration. Include behavior, owned paths, contract changes, evidence
   and missing checks. A reviews semantics, C integration/contracts, D independent
   validation; author approval alone is not peer review. Wait for one peer approval
   and successful manual checks before C deliberately merges. No automatic merge.
5. **Resolve overlap with both owners.** Fetch and compare branch histories and
   changed paths first. Pause edits to colliding files; agree which behavior and
   evidence survive. Preserve dirty/untracked/ignored work before any recovery.
   Reconcile in the PR author's isolated worktree, review the final diff and rerun
   affected checks. Never use blanket ours/theirs, reset/clean/stash someone else's
   work, force-push, or rewrite shared history. C separately approves any merge or
   rebase plan; the recovery table below is not automatic authorization.

## Safeguards actually observed — November 7, 2026

Authenticated GitHub API reads and a successful fetch found the following.
Recheck before publication: visibility, branch tips and access can change.

| Safeguard | Observed enforcement |
| --- | --- |
| Repository confidentiality | **PUBLIC by explicit owner decision**; reviewed public-safe documentation publication is authorized. This audit changes no visibility, permissions or settings. |
| `main` / `codex/local-mvp-integration` protection | Both `protected=false`; classic protection endpoints say “Branch not protected.” Repository/inherited ruleset list and applicable branch rules are empty. |
| PR review, required tests, force-push prevention | No branch rules enforce them. The workflow above is documentation-only policy; write access can bypass it. |
| Automated PR CI | Actions service enabled, but zero registered workflows, zero recorded PR workflow runs and no workflow files on the audited main/integration/docs trees. No statuses/check runs on remote integration `6481390`. Existing Python/Node/QA commands are manual tests. |
| Four-person access | Owner plus one accepted collaborator have write capability; two write invitations are pending. Invitees must accept and verify their own clone/feature-branch/PR access. No permissions changed. |

The docs branch started at `f4599f0`. Latest fetched integration `6481390`
includes the engine owner's `5d256ac` and `6481390` (0.6.1 / opt-in atomic path).
README/status are reconciled with those published docs inside this isolated
branch, without merging/rebasing branches or copying engine code. Refresh the
comparison again before accepting the PR; C owns integration. No merge or settings
change is authorized by this guide itself. Adding CI/protection is a separate
owner decision; this audit only records their absence.

### Public-content audit boundary

The initial history scan covered 19 reachable commits / 223 unique blobs: no
obvious credentials, signed access URLs, real-call passages, raw DEV or reviewer
export files were found. The only dataset envelope is the approved synthetic 60;
three team-safe PDFs have no detected annotations/actions. Documentation commits
are scanned separately before upload. This is an obvious-exposure check, not a
complete security audit or proof of organizer public-redistribution permission.
The already-tracked synthetic data/PDF derivatives and public Git author metadata
are separate existing exposures; the owner decides redistribution/visibility.
Never add confidential inputs, actual reviewer outputs, keys or generated runs.

## Five different states

1. **Working directory:** current on-disk content, including uncommitted changes.
2. **Local commits/index:** committed history and staged changes; neither implies
   that GitHub has received them. Untracked and ignored files are outside commits.
3. **Remote-tracking refs:** cached observations such as `origin/main`; stale
   until refreshed successfully. An upstream is only a configured comparison ref.
4. **Actual remote:** what GitHub currently stores; verify with actual network
   operations. Even a successful fetch is an observation at that time, not a lock.
5. **Local-only files:** non-allowlisted data, evidence/status, outputs, and deliverables excluded
   by policy. They may be newer than committed work and need separate approved
   handoff. Ignoring a file does not stop tracking an already-added file.

The authoritative result is the exact version identified in the evidence ledger,
not automatically the newest file timestamp or newest GitHub commit.

Before Git preflight or a material-dependent task, read `PROJECT_FILE_MAP.md` and
inspect actual relevant directories including ignored files. Git and default
ignore-aware searches cannot establish material absence. A fresh clone includes
team-safe PDFs and the 60-chat subset, not original PDFs, full 65-record DEV,
real calls, signed API/audio access or local `STATUS.md`. Check disk first, then
obtain missing LOCAL ONLY inputs through the integration owner's approved handoff.

## Session preflight

From the project root, run:

```sh
python3 -B src/git_preflight.py
```

This does not fetch, stage, commit, modify files, or recover anything. It shows
local status, branch, configured remotes with credentials redacted, upstream,
untracked files, local/cached-remote commit differences, and conflicts. A warning
does not prohibit independent analytical work. Treat unexpected tool errors as
unknown state, not a clean bill of health.

When the configured remote is approved and network access is permitted, inspect
its destination and run `git fetch origin` (substitute the confirmed remote name).
A fetch updates cached refs but does not integrate or overwrite working files.
If it fails, record that freshness is unknown. Do not blindly retry with pull.
After a successful fetch, rerun preflight; if an upstream is configured, compare:

```sh
git rev-list --left-right --count HEAD...@{upstream}
git log --oneline --left-right HEAD...@{upstream}
```

Left is local-only; right is upstream-only. Compare the intended branch, not an
unrelated default branch. Inspect dirty/untracked work and conflicts separately.
Never interpret an old `origin/main` comparison as a fresh GitHub comparison.

## Recovery decisions

Read-only status/diff/log checks are safe in every state. Inspect sensitive file
content locally; do not post raw diffs or credential-bearing remotes to services.

| Situation | Safe next step | Approval / caution |
| --- | --- | --- |
| Clean and equal after fetch | Continue on intended branch | Equality is only as of that fetch; uploads still follow approval |
| Uncommitted changes | Inspect diffs, owner, and intent; preserve files | Do not stash, discard, or switch over work automatically; stage/commit only reviewed intended files |
| Ahead only | Review local-only commits and their complete file contents | Push only to the approved destination with approved content; reject force push |
| Behind only | Inspect incoming commits and potential path conflicts | After owner agreement and a clean tree/no colliding untracked files, explicit `git merge --ff-only` against the confirmed upstream is acceptable; do not run automatically |
| Diverged | Inspect both histories; identify owners and a reconciliation plan | No automatic merge, rebase, reset, or force push; obtain approval for a specific plan |
| Untracked files | Identify purpose and sensitivity; list exact intended additions | Do not assume disposable; avoid blanket staging and never run automatic `git clean` |
| Merge conflicts | Inspect `git status` and unresolved paths; preserve content | Integration owner resolves against evidence; no blanket "ours/theirs", automatic abort, or automatic continuation |
| Teammate changes | Fetch; inspect incoming diffs, shared definitions, and file ownership | Integrate deliberately; rerun affected analysis and stale downstream evidence |
| Missing/wrong upstream | Inspect local branch, remote branch names, and intended destination | Set `git branch --set-upstream-to=origin/main main` only after confirming those exact branches; no assumed upstream |
| No GitHub access | Preserve local work; inspect local snapshots and continue unrelated analysis | Label remote freshness/access unknown; restore authentication through official login, never tokens in chat |

If recovery requires a safety copy, create an explicit local copy or reviewed
checkpoint commit on an agreed branch first. A patch alone does not preserve
untracked/ignored files. Do not overwrite backup paths. Never silently discard
work. Do not make safe read-only investigation depend on resolving Git first.

## Small-team workflow

Confirm one integration owner, authoritative `main`, one owner per notebook or
workstream, shared metric definitions/input version, and a submission owner with
backup. For two people, one can lead analysis and one integration/verification;
with three or four, separate data preparation, analysis, validation, and synthesis
only where useful. Exchange findings throughout rather than at the end.

Use short feature branches for concurrent code work, descriptive commits, and PR
review for consequential cleaning/definition/validation changes where practical.
Do not edit the same notebook concurrently. Teammates fetch first, inspect state,
then fast-forward an eligible clean branch or agree on another integration plan.
Each accepted change identifies any evidence and artifacts needing revalidation.

Parallel human/AI assignments need distinct scope, shared definitions and inputs,
an owner, expected output, verification, and integration checkpoint. Compare
conflicting definitions, evidence, and calculations; retain unresolved uncertainty.
AI use must be permitted; no orchestration platform is needed.

## Remote creation and upload gate

Before any creation or initial upload, confirm authenticated owner, exact repo
name/URL, approved visibility, repository existence/access, and the exact proposed
files and complete commit history. A 404 can mean missing **or inaccessible**.
Inspect `git ls-files`, `git ls-files -ci --exclude-standard`, staged diff, and
all commits being uploaded for secrets, restricted material, or notebook outputs.
An empty ignored-file check does not itself prove content is safe.

Show the destination and upload manifest and obtain explicit approval. Do not
create the remote or push before approval. If creation conflicts with an existing
repo, stop and inspect; do not overwrite its history. Do not put tokens in URLs.
For CLI authentication use `gh auth login --hostname github.com --web` interactively
on the user's machine; never ask for secrets in chat or expose stored credentials.
Connector authentication and CLI/Git authentication are separate capabilities.

After approval and working authentication: confirm the exact remote/approved visibility,
configure the reviewed URL, push reviewed history, then verify with an actual
`git ls-remote origin refs/heads/codex/team-handoff-docs-20261107` for this
documentation publication, successful fetch and comparison against that exact
branch. Confirm upstream and clean status; API metadata alone does not prove
Git transport works. Record what actually succeeded in `STATUS.md`.

## Data and handoff policy

Full raw DEV, original case PDFs, real-call data, local status/evidence and generated
deliverables stay ignored. Named requirements/specifications, reviewed team-safe
PDFs and the synthetic-only 60-chat derivative are explicitly allowed for this
PRIVATE repository. Other material remains excluded; no broad directory exceptions.
A private repo is not blanket permission.
Review aggregate tables and charts for disclosure before any sharing. Explicitly
approved artifacts can be tracked selectively after review; never force-add a
whole ignored directory. Review already tracked files as well as ignore rules.

Use `STATUS.md` locally as the detailed integration/evidence record. Shared
`TEAM_STATUS.md` is its sanitized snapshot, not a competing evidence ledger; it
must not contain real-call evidence or signed URLs. Keep `PROJECT_FILE_MAP.md`
current when file availability/sharing changes. Review exact staged paths/content,
including decoded PDF objects and dataset membership, before an authorized push.
Earlier reviewed material sharing was private-team scoped. The owner now
explicitly authorizes this public-safe documentation branch in the existing public
repository. That does not grant organizer redistribution rights or authorize new
sensitive data. Do not change settings or rewrite history in this workflow.
