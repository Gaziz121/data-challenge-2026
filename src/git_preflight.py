"""Read local Git state without network access, recovery, or optional Git locks."""

from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(ROOT), *args],
        capture_output=True, text=True, check=False,
    )


def redact(value):
    # Git URLs can embed passwords/tokens in userinfo, paths, or query strings.
    value = re.sub(r"(https?://)[^/\s@]+@", r"\1[REDACTED]@", value)
    value = re.sub(r"[?#].*$", "[REDACTED query/fragment]", value)
    return re.sub(
        r"\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)\b",
        "[REDACTED]", value,
    )


def main():
    print("LOCAL GIT PREFLIGHT — no fetch or working-file changes")
    print("Cached refs do not establish current GitHub state.")
    try:
        root = git("rev-parse", "--show-toplevel")
    except FileNotFoundError:
        print("Git is unavailable; repository state is unknown.")
        return 1
    if root.returncode:
        print("No readable Git root found; preserve files and inspect locally.")
        return 1
    if Path(root.stdout.strip()).resolve() != ROOT:
        print("Unexpected parent Git repository; stop Git mutations.")
        return 1

    status = git("status", "--short", "--branch", "--untracked-files=all")
    if status.returncode:
        print("Status check failed; repository state is unknown.")
        return 1
    print("\nWorking/staged changes and untracked files:")
    print(status.stdout.strip() or "(clean)")
    print("Ignored data, evidence, and outputs are not included above.")
    tracked_ignored = git("ls-files", "-ci", "--exclude-standard")
    if tracked_ignored.returncode:
        print("Tracked/ignored-file policy check failed; state is unknown.")
        return 1
    if tracked_ignored.stdout.strip():
        print("WARNING: tracked files now matching ignore rules (not protected by ignoring):")
        print(tracked_ignored.stdout.strip())

    branch = git("symbolic-ref", "--quiet", "--short", "HEAD")
    print("\nBranch:", branch.stdout.strip() if branch.returncode == 0 else "detached HEAD")
    remotes = git("remote")
    if remotes.returncode:
        print("Remote configuration could not be inspected.")
        return 1
    print("Remotes:")
    for remote in remotes.stdout.splitlines():
        for option, label in (((), "fetch"), (("--push",), "push")):
            urls = git("remote", "get-url", *option, "--all", remote)
            if urls.returncode:
                print(f"  {remote} ({label}): unreadable")
                return 1
            for url in urls.stdout.splitlines():
                print(f"  {remote} ({label}): {redact(url)}")
    if not remotes.stdout.strip():
        print("  (none)")

    conflicts = git("diff", "--name-only", "--diff-filter=U")
    if conflicts.returncode:
        print("Conflict check failed; state is unknown.")
        return 1
    print("Unresolved conflicts:", conflicts.stdout.strip() or "none detected")
    head = git("rev-parse", "--verify", "HEAD")
    if head.returncode:
        print("No local commit yet; ahead/behind comparison unavailable.")
        return 0
    print("Local HEAD:", head.stdout.strip())
    upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    if upstream.returncode:
        print("No resolvable upstream; ahead/behind comparison unavailable.")
        return 0
    name = upstream.stdout.strip()
    counts = git("rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if counts.returncode:
        print("Upstream comparison failed; state is unknown.")
        return 1
    ahead, behind = counts.stdout.split()
    print(f"Cached upstream: {name}; local-only commits: {ahead}; upstream-only commits: {behind}")
    history = git("log", "-10", "--oneline", "--left-right", "HEAD...@{upstream}")
    if history.returncode:
        print("History comparison failed; state is unknown.")
        return 1
    if history.stdout.strip():
        print("Latest differing commits (< local, > upstream; at most 10):")
        print(history.stdout.strip())
    print("Next: follow GIT_WORKFLOW.md; divergence never triggers automatic recovery.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
