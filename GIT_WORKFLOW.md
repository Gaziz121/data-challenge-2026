# Safe Git collaboration and recovery

## Five different states

1. **Working directory:** current on-disk content, including uncommitted changes.
2. **Local commits/index:** committed history and staged changes; neither implies
   that GitHub has received them. Untracked and ignored files are outside commits.
3. **Remote-tracking refs:** cached observations such as `origin/main`; stale
   until refreshed successfully. An upstream is only a configured comparison ref.
4. **Actual remote:** what GitHub currently stores; verify with actual network
   operations. Even a successful fetch is an observation at that time, not a lock.
5. **Local-only files:** data, evidence/status, outputs, and deliverables excluded
   by policy. They may be newer than committed work and need separate approved
   handoff. Ignoring a file does not stop tracking an already-added file.

The authoritative result is the exact version identified in the evidence ledger,
not automatically the newest file timestamp or newest GitHub commit.

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
name/URL, private visibility, repository existence/access, and the exact proposed
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

After approval and working authentication: create or confirm the private remote,
configure the reviewed URL, push reviewed history, then verify with an actual
`git ls-remote origin refs/heads/main`, successful fetch, and a comparison against
local `main`. Confirm upstream and clean status; API metadata alone does not prove
Git transport works. Record what actually succeeded in `STATUS.md`.

## Data and handoff policy

Raw inputs, derived data, case documents, local status/evidence, and generated
deliverables stay ignored by default. A private repo is not blanket permission.
Review aggregate tables and charts for disclosure before any sharing. Explicitly
approved artifacts can be tracked selectively after review; never force-add a
whole ignored directory. Review already tracked files as well as ignore rules.

Use `STATUS.md` locally as the single integration record. If teammates need it,
agree on an organizer-permitted shared location and one edit owner. It is not
silently synchronized by Git. A sanitized reviewed version may be shared only
with explicit approval; do not create a second competing evidence ledger.
