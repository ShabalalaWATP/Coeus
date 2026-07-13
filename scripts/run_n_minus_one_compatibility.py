"""Run the real N-1 ticket compatibility gate in a detached worktree."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_N_MINUS_ONE_REVISION = "3e27c82d4b62efb683b3fbb81d2486bccafd8fb0"
ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=ROOT, env=env, check=True)  # noqa: S603


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default=DEFAULT_N_MINUS_ONE_REVISION)
    parser.add_argument(
        "--database-url",
        default=os.getenv("COEUS_TEST_DATABASE_URL"),
        help="Base PostgreSQL URL used only to create a disposable test database.",
    )
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("--database-url or COEUS_TEST_DATABASE_URL is required")
    git = shutil.which("git")
    if git is None:
        parser.error("git is required")

    revision = subprocess.run(  # noqa: S603
        [git, "rev-parse", "--verify", f"{args.revision}^{{commit}}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="coeus-n-minus-one-") as temporary:
        worktree = Path(temporary) / "source"
        _run([git, "worktree", "add", "--detach", str(worktree), revision])
        try:
            env = os.environ.copy()
            env["COEUS_TEST_DATABASE_URL"] = args.database_url
            env["COEUS_N_MINUS_ONE_SOURCE"] = str(worktree)
            _run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "apps/api/tests/postgres/test_n_minus_one_compatibility.py",
                    "--no-cov",
                    "-q",
                ],
                env=env,
            )
        finally:
            _run([git, "worktree", "remove", "--force", str(worktree)])
    sys.stdout.write(json.dumps({"result": "passed", "revision": revision}, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
