"""Run Playwright against a disposable migrated PostgreSQL database."""

import argparse
import os
import shutil
import subprocess
import sys
from uuid import uuid4

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


COMMAND_TIMEOUT_SECONDS = 600


def _run(command: list[str], env: dict[str, str]) -> None:
    process = subprocess.Popen(  # noqa: S603
        command,
        cwd=ROOT,
        env=env,
        start_new_session=os.name != "nt",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    try:
        return_code = process.wait(timeout=COMMAND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        _terminate_process_tree(process)
        raise RuntimeError(
            f"Command exceeded {COMMAND_TIMEOUT_SECONDS} seconds: {command[0]}"
        ) from None
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, command)


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        taskkill = shutil.which("taskkill")
        if taskkill is not None:
            subprocess.run(  # noqa: S603
                [taskkill, "/PID", str(process.pid), "/T", "/F"],
                check=False,
                capture_output=True,
            )
            return
        process.kill()
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("COEUS_TEST_DATABASE_URL"))
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("--database-url or COEUS_TEST_DATABASE_URL is required")

    base_url = make_url(args.database_url)
    database_name = f"coeus_playwright_{uuid4().hex}"
    admin_url = base_url.set(drivername="postgresql", database="postgres")
    admin_dsn = admin_url.render_as_string(hide_password=False)
    test_url = base_url.set(database=database_name).render_as_string(hide_password=False)
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    env = os.environ.copy()
    env["COEUS_DATABASE_URL"] = test_url
    env["COEUS_PLAYWRIGHT_DATABASE_URL"] = test_url
    try:
        _run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                "apps/api/alembic.ini",
                "upgrade",
                "head",
            ],
            env,
        )
        _run(
            [
                "pnpm.cmd" if os.name == "nt" else "pnpm",
                "--filter",
                "@coeus/web",
                "exec",
                "playwright",
                "test",
                "--config=playwright.postgres.config.ts",
            ],
            env,
        )
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database_name,),
            )
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
