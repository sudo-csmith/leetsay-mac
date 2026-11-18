"""Stops personal details from reaching GitHub.

Checks commit messages, the names of changed files and the lines they add for:
  - home folder paths (/Users/<name>/, /home/<name>/), except GitHub's runner;
  - private notes and handoff files, recordings, logs, local settings and
    signing files, by file name;
  - words listed in .push-guard.local (one per line; e-mail, real name, user
    and machine names). That file is never uploaded (.gitignore); without it
    only the general rules apply, as in the GitHub tests.

  python3 tools/push_guard.py --pre-push      (from .git/hooks/pre-push)
  python3 tools/push_guard.py --all           (every commit, used in CI)
"""
import os, re, subprocess, sys

sys.dont_write_bytecode = True
ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                      text=True).stdout.strip() or "."
SELF = "tools/push_guard.py"
SKIP_CONTENT = ("licenses/",)        # third-party licence texts (their authors' names)
HOME_PATH = re.compile(r"/(?:Users|home)/(?!runner\b|Shared\b)[A-Za-z0-9._-]+/")
BAD_FILE = re.compile(
    r"(^|/)(CLAUDE[^/]*\.md|[^/]*handoff[^/]*|START-HERE[^/]*|NOTES[^/]*|[^/]*\.notes\.md|"
    r"settings\.json(\.[^/]*)?|\.push-guard\.local|tests-private/.*|windows-reference/.*|"
    r"\.claude/.*|[^/]*\.(log|wav|aiff|m4a|mp3|p12|p8|cer|certSigningRequest))$", re.I)


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          errors="replace").stdout


def private_words():
    path = os.path.join(ROOT, ".push-guard.local")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [w.strip() for w in fh if w.strip() and not w.startswith("#")]


def check_commits(commits):
    words = [w.lower() for w in private_words()]
    problems = []

    def scan(where, text):
        low = text.lower()
        for w in words:
            if w in low:
                problems.append(f"{where}: a blocked word (from .push-guard.local)")
        if HOME_PATH.search(text):
            problems.append(f"{where}: a home folder path ({HOME_PATH.search(text).group(0)})")

    for c in commits:
        short = c[:7]
        scan(f"{short} message", git("log", "-1", "--format=%an %ae %cn %ce%n%B", c))
        for name in git("diff-tree", "--no-commit-id", "-r", "--name-only", "--root", c).split("\n"):
            if not name:
                continue
            scan(f"{short} file name {name}", name)
            if BAD_FILE.search(name) and git("cat-file", "-t", f"{c}:{name}").strip():
                problems.append(f"{short}: private file type {name}")
            if name == SELF or name.startswith(SKIP_CONTENT):
                continue
            added = [line[1:] for line in git("show", "--format=", c, "--", name).split("\n")
                     if line.startswith("+") and not line.startswith("+++")]
            scan(f"{short} {name}", "\n".join(added))
    return problems


def pushed_commits():
    commits = []
    for line in sys.stdin:
        parts = line.split()
        if len(parts) != 4 or set(parts[1]) == {"0"}:
            continue                                  # a deletion: nothing uploaded
        local, remote = parts[1], parts[3]
        rng = [local, "--not", "--remotes"] if set(remote) == {"0"} else [f"{remote}..{local}"]
        commits += git("rev-list", *rng).split()
    return commits


def main():
    if "--all" in sys.argv:
        commits = git("rev-list", "HEAD").split()
    else:
        commits = pushed_commits()
    problems = check_commits(commits)
    if problems:
        print("push guard: NOT pushed. Found:", file=sys.stderr)
        for p in dict.fromkeys(problems):
            print("  - " + p, file=sys.stderr)
        sys.exit(1)
    print(f"push guard: {len(commits)} commit(s) checked, nothing personal found"
          + ("" if private_words() else " (general rules only)"))


if __name__ == "__main__":
    main()
