"""Build the static demo and publish it to the gh-pages branch (served by GitHub Pages).

    python scripts/publish_site.py

Adds one normal commit on gh-pages each time (no force-push), using your own git login.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_site  # noqa: E402


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True, encoding="utf-8")


def main() -> None:
    build_site.main()
    remote = git("remote", "get-url", "origin", cwd=ROOT).stdout.strip()
    email = git("config", "user.email", cwd=ROOT).stdout.strip()   # keep the repo's (private) commit email
    name = git("config", "user.name", cwd=ROOT).stdout.strip()
    source = git("rev-parse", "--short", "HEAD", cwd=ROOT).stdout.strip()

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "pages"
        if git("clone", "--quiet", "--depth", "1", "--branch", "gh-pages", remote, str(work), cwd=ROOT, check=False).returncode:
            work.mkdir()
            git("init", "--quiet", "-b", "gh-pages", cwd=work)
            git("remote", "add", "origin", remote, cwd=work)
        for item in work.iterdir():                      # replace everything except git's own folder
            if item.name != ".git":
                shutil.rmtree(item) if item.is_dir() else item.unlink()
        shutil.copytree(build_site.OUT, work, dirs_exist_ok=True)
        git("config", "user.email", email, cwd=work)
        git("config", "user.name", name, cwd=work)
        git("add", "-A", cwd=work)
        if not git("status", "--porcelain", cwd=work).stdout.strip():
            print("gh-pages is already up to date")
            return
        git("commit", "--quiet", "-m", f"Publish demo from {source}", cwd=work)
        git("push", "--quiet", "origin", "gh-pages", cwd=work)
    print(f"published demo from {source} to gh-pages")


if __name__ == "__main__":
    main()
