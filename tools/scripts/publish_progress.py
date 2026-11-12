#!/usr/bin/env python3
"""Regenerate progress from the current remote tip, retrying concurrent pushes."""
import argparse
from pathlib import Path
import subprocess
import sys


MAIN = "main"


def publish(root, remote="origin", branch=MAIN, attempts=4, generate=None):
    root = Path(root)
    if attempts < 1:
        raise ValueError("attempts must be positive")

    def git(*args, check=True):
        return subprocess.run(["git", *args], cwd=root, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=check)

    if git("status", "--porcelain").stdout.strip():
        raise RuntimeError("Progress publisher requires a clean checkout")
    generate = generate or [sys.executable, "tools/scripts/update_progress.py"]
    for attempt in range(attempts):
        git("fetch", "--no-tags", remote, "refs/heads/" + branch)
        base = git("rev-parse", "FETCH_HEAD").stdout.strip()
        git("checkout", "--detach", base)
        subprocess.run(generate, cwd=root, check=True)
        if git("rev-parse", "HEAD").stdout.strip() != base:
            raise RuntimeError("Progress generator changed HEAD")
        changed = (git("diff", "--name-only", "-z").stdout +
                   git("diff", "--cached", "--name-only", "-z").stdout +
                   git("ls-files", "--others", "--exclude-standard", "-z").stdout).split("\0")
        if any(name and not name.startswith("docs/progress/") for name in changed):
            raise RuntimeError("Progress generator modified files outside docs/progress")
        git("add", "--", "docs/progress")
        diff = git("diff", "--cached", "--quiet", check=False)
        if diff.returncode == 0:
            git("fetch", "--no-tags", remote, "refs/heads/" + branch)
            if git("rev-parse", "FETCH_HEAD").stdout.strip() == base:
                return
            print("Remote advanced during no-op; regenerating progress", flush=True)
            continue
        if diff.returncode != 1:
            diff.check_returncode()
        git("commit", "-m", "progress: update [skip ci]")
        pushed = git("push", remote, "HEAD:refs/heads/" + branch, check=False)
        if pushed.returncode == 0:
            return
        # Retry only if someone actually moved the branch. Authentication,
        # permissions and server errors at the same tip must remain failures.
        git("fetch", "--no-tags", remote, "refs/heads/" + branch)
        current = git("rev-parse", "FETCH_HEAD").stdout.strip()
        if current == base:
            raise RuntimeError("Progress push failed: " + pushed.stderr.strip())
        print("Remote advanced; regenerating progress (%d/%d)" %
              (attempt + 1, attempts), flush=True)
    raise RuntimeError("Remote kept advancing; progress publication exhausted retries")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempts", type=int, default=4)
    args = parser.parse_args()
    publish(Path(__file__).resolve().parents[2], attempts=args.attempts)
