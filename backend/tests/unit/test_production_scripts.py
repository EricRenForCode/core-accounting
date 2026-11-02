"""Deployment regressions; Docker commands are mocked except config rendering."""

import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]


def deployment_env():
    # Do not let the developer's active deployment select the test project.
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("COMPOSE_", "DB_"))
        and key not in {"NGINX_PORT", "BACKEND_PORT", "POSTGRES_USER", "POSTGRES_DB"}
    }


@pytest.mark.parametrize("project_name", [None, "existing-production"])
def test_production_keeps_legacy_volume_names(tmp_path, project_name):
    if not shutil.which("docker") or subprocess.run(
        ["docker", "compose", "version"], capture_output=True
    ).returncode:
        pytest.skip("Docker Compose is needed for config rendering (no daemon required)")

    checkout = tmp_path / "company-books"
    checkout.mkdir()
    (checkout / ".env").write_text(
        "DB_PASSWORD=test_only_db_password\nDB_RO_PASSWORD=test_only_ro_password\n"
    )
    production = checkout / "docker-compose.prod.yml"
    shutil.copyfile(ROOT / "docker-compose.prod.yml", production)
    # Before the installer, production used directory/CLI/environment project
    # names and these two logical volumes. Compare resolved names, not YAML text.
    legacy = checkout / "legacy.yml"
    legacy.write_text(
        "services:\n"
        "  db:\n"
        "    image: postgres:15-alpine\n"
        "    volumes: [pgdata:/var/lib/postgresql/data]\n"
        "  redis:\n"
        "    image: redis:7-alpine\n"
        "    volumes: [redisdata:/data]\n"
        "volumes:\n"
        "  pgdata: {}\n"
        "  redisdata: {}\n"
    )
    env = deployment_env()
    if project_name:
        env["COMPOSE_PROJECT_NAME"] = project_name

    def config(path):
        return json.loads(subprocess.check_output(
            ["docker", "compose", "-f", str(path), "config", "--format", "json"],
            cwd=checkout, env=env, text=True,
        ))

    before, after = config(legacy), config(production)
    assert after["name"] == before["name"] == (project_name or checkout.name)
    for volume in ("pgdata", "redisdata"):
        assert after["volumes"][volume]["name"] == before["volumes"][volume]["name"]


@pytest.mark.parametrize("restore", [False, True])
@pytest.mark.parametrize("legacy_container", [False, True])
@pytest.mark.parametrize("override", [False, True])
def test_backup_and_restore_use_container_identifiers(
    tmp_path, restore, legacy_container, override,
):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    capture = tmp_path / "command.json"

    # Execute the actual shell command supplied to docker, with the environment
    # the database container would have received from Compose/.env. No daemon,
    # host .env sourcing, or real database is involved.
    docker = bin_dir / "docker"
    docker.write_text(f"#!{sys.executable}\n" + '''
import os, subprocess, sys
args = sys.argv[1:]
if args[0] == "compose":
    assert args[3:6] == ["exec", "-T", "db"], args
else:
    assert args[:3] == ["exec", "-i", "legacy-db"], args
env = os.environ.copy()
env["POSTGRES_USER"] = "Finance_Owner"
env["POSTGRES_DB"] = "Finance_Books"
sys.exit(subprocess.run(args[args.index("sh"):], env=env).returncode)
''')
    docker.chmod(0o755)

    for program in ("pg_dump", "psql"):
        tool = bin_dir / program
        tool.write_text(f"#!{sys.executable}\n" + '''
import json, os, pathlib, sys
program = pathlib.Path(sys.argv[0]).name
payload = {"program": program, "args": sys.argv[1:]}
if program == "psql":
    payload["sql"] = sys.stdin.read()
pathlib.Path(os.environ["CAPTURE_ARGS"]).write_text(json.dumps(payload))
if program == "pg_dump":
    print("-- test database dump")
''')
        tool.chmod(0o755)

    env = deployment_env()
    env.update(
        PATH=str(bin_dir) + os.pathsep + env["PATH"],
        CAPTURE_ARGS=str(capture), BACKUP_DIR=str(tmp_path / "dumps"),
    )
    if legacy_container:
        env["DB_CONTAINER"] = "legacy-db"
    if override:
        env.update(DB_USER="Override_Owner", DB_NAME="Override_Books")

    command = ["bash", str(ROOT / "backups" / "backup.sh")]
    if restore:
        archive = tmp_path / "restore.sql.gz"
        archive.write_bytes(gzip.compress(b"-- test restore\n"))
        command.extend(["--restore", str(archive)])
    subprocess.run(command, env=env, input="y\n", text=True, check=True, capture_output=True)
    actual = json.loads(capture.read_text())
    expected_user = "Override_Owner" if override else "Finance_Owner"
    expected_db = "Override_Books" if override else "Finance_Books"
    assert actual["args"][:4] == ["-U", expected_user, "-d", expected_db]
    assert actual["program"] == ("psql" if restore else "pg_dump")
    if restore:
        assert actual["sql"] == "-- test restore\n"
    else:
        assert actual["args"][4:] == ["--no-owner", "--no-acl", "--clean", "--if-exists"]
        archives = list((tmp_path / "dumps").glob("*.sql.gz"))
        assert len(archives) == 1
        assert gzip.decompress(archives[0].read_bytes()) == b"-- test database dump\n"
