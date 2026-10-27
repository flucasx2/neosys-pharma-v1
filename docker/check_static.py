"""Offline safety checks: no Docker engine mutations or database connections."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
from unittest.mock import patch


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    spec = importlib.util.spec_from_file_location("docker_guard", root / "docker/entrypoint.py")
    guard = importlib.util.module_from_spec(spec)
    ast.parse(Path(spec.origin).read_text(encoding="utf-8"))
    spec.loader.exec_module(guard)
    checks = 0
    for role, host, secret in (("app", "db", "dev_db_password"),
                               ("tests", "test-db", "test_db_password")):
        env = {"NEOSYS_DOCKER_ROLE": role,
               "POSTGRES_PASSWORD_FILE": "/run/secrets/" + secret}
        with patch.dict(os.environ, env, clear=True), patch.object(guard.Path, "exists", return_value=False), patch.object(guard.Path, "read_text", return_value="synthetic+check@value"):
            guard.configure()
            assert "@" + host + ":5432/" in os.environ["DATABASE_URL"]
            assert "synthetic%2Bcheck%40value" in os.environ["DATABASE_URL"]
            if role == "tests":
                assert os.environ["TEST_DATABASE_URL"] == "sqlite+pysqlite://"
        checks += 1
        for key in ("DATABASE_URL", "TEST_DATABASE_URL", "TEST_P5C_MIGRATION_URL", "PGHOST", "POSTGRES_PASSWORD"):
            with patch.dict(os.environ, {**env, key: "synthetic-forbidden"}, clear=True), patch.object(guard.Path, "exists", return_value=False), patch.object(guard.Path, "read_text") as read:
                try:
                    guard.configure()
                except ValueError:
                    pass
                else:
                    raise AssertionError("Inherited database configuration accepted")
                read.assert_not_called()
            checks += 1
    for extra, exists, content in (({}, True, "synthetic"),
                                   ({"NEOSYS_DOCKER_ROLE": "unknown"}, False, "synthetic"),
                                   ({"POSTGRES_PASSWORD_FILE": "/unexpected"}, False, "synthetic"),
                                   ({}, False, ""), ({}, False, "REPLACE_placeholder")):
        env = {"NEOSYS_DOCKER_ROLE": "app", "POSTGRES_PASSWORD_FILE": "/run/secrets/dev_db_password", **extra}
        with patch.dict(os.environ, env, clear=True), patch.object(guard.Path, "exists", return_value=exists), patch.object(guard.Path, "read_text", return_value=content):
            try:
                guard.configure()
            except ValueError:
                pass
            else:
                raise AssertionError("Invalid configuration accepted")
        checks += 1
    command = ["docker", "compose", "-p", "neosys-pharma-dev", "--env-file", ".env.docker.example", "--profile", "test", "config", "--format", "json"]
    env = dict(os.environ, DATABASE_URL="synthetic-windows-target", TEST_DATABASE_URL="synthetic-windows-test")
    result = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
    assert "synthetic-windows" not in result.stdout
    model = json.loads(result.stdout)
    services = model["services"]
    assert model["name"] == "neosys-pharma-dev"
    assert set(services["tests"]["networks"]).isdisjoint(services["db"]["networks"])
    for service, secret in (("app", "dev_db_password"), ("db", "dev_db_password"),
                            ("tests", "test_db_password"), ("test-db", "test_db_password")):
        config = services[service]
        assert {s["source"] for s in config["secrets"]} == {secret}
        assert config["platform"] == "linux/amd64"
        assert not any(k.endswith("DATABASE_URL") or k == "POSTGRES_PASSWORD" for k in config["environment"])
        if service != "app":
            assert not config.get("ports")
    assert services["app"]["ports"][0]["host_ip"] == "127.0.0.1"
    assert str(services["app"]["ports"][0]["published"]) == "8001"
    assert model["volumes"]["development_data"]["external"] is True
    assert model["volumes"]["development_data"]["name"] == "neosys_pharma_dev_pgdata"
    assert model["networks"]["development"]["internal"]
    assert model["networks"]["testing"]["internal"]
    assert "frontend" in services["app"]["networks"]
    assert all("frontend" not in services[s]["networks"] for s in ("db", "test-db", "tests"))
    assert services["tests"].get("volumes", []) == []
    locks = []
    for name in ("runtime", "tests"):
        content = (root / f"requirements/{name}.lock").read_text(encoding="utf-8")
        entries = re.split(r"\n(?=[a-zA-Z0-9_-]+==)", content)
        packages = {}
        for entry in entries:
            match = re.match(r"([a-zA-Z0-9_-]+)==([^\s\\]+)", entry)
            if match:
                assert re.search(r"--hash=sha256:[0-9a-f]{64}\b", entry)
                packages[match[1]] = match[2]
        assert packages
        locks.append(packages)
    assert all(locks[1].get(k) == v for k, v in locks[0].items())
    print(f"PASS: {checks} guard cases; Compose isolation/inheritance; external volume; hashed locks ({len(locks[0])}/{len(locks[1])} packages).")


if __name__ == "__main__":
    main()
