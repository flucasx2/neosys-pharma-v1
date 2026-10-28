"""Fail closed before importing application code; never load the Windows .env."""
import os
from pathlib import Path
import sys
from urllib.parse import quote


def configure():
    role = os.environ.get("NEOSYS_DOCKER_ROLE")
    if role == "tests-native":
        database = os.environ.get("P4P5_CONFIRM_DATABASE", "")
        if (not database.startswith("neosys_p4p5_")
                or os.environ.get("CI", "").lower() != "true"
                or os.environ.get("P5C2_DISPOSABLE_EMISSION") != "1"):
            raise ValueError("An explicit isolated native-test target is required")
        host, user = "localhost", "neosys_test"
        port = 55432
    elif role == "app":
        host, user, database, port = "db", "neosys_dev", "neosys_docker_dev", 5432
    elif role == "tests":
        host, user, database, port = "test-db", "neosys_test", "neosys_docker_test", 5432
    else:
        raise ValueError("Unknown Docker role")
    if Path(".env").exists():
        raise ValueError("Docker role required; application .env forbidden")
    # No inherited connection URL is trusted, even if it appears to match.
    for key, value in os.environ.items():
        if value and (key.endswith(("DATABASE_URL", "MIGRATION_URL", "ADMIN_URL"))
                      or (key.startswith("TEST_") and key.endswith("URL"))
                      or key.startswith("PG") or key == "POSTGRES_PASSWORD"):
            raise ValueError("Inherited database configuration refused")
    secret_name = "dev_db_password" if role == "app" else "test_db_password"
    secret_path = "/run/secrets/" + secret_name
    if os.environ.get("POSTGRES_PASSWORD_FILE") != secret_path:
        raise ValueError("Unexpected secret path refused")
    password = Path(secret_path).read_text(encoding="utf-8").rstrip("\r\n")
    if not password or password.startswith("REPLACE_") or any(c in password for c in "\r\n\x00"):
        raise ValueError("A local Docker-only password is required")
    url = f"postgresql+psycopg://{user}:{quote(password, safe='')}@{host}:{port}/{database}"
    os.environ["DATABASE_URL"] = url
    if role == "tests":
        # Phase 1 runs SQLite fixtures only. Native migration variables are not set.
        if any(k.startswith("TEST_") and k.endswith(("URL", "DATABASE_URL"))
               and v for k, v in os.environ.items()):
            raise ValueError("Native database tests require a dedicated future runner")
        os.environ["TEST_DATABASE_URL"] = "sqlite+pysqlite://"
    elif role == "tests-native":
        os.environ["TEST_DATABASE_URL"] = url


def main():
    try:
        configure()
    except (ValueError, TypeError, OSError, UnicodeError):
        print("Docker configuration refused: check role, local password and database targets.", file=sys.stderr)
        return 2
    if sys.argv[1:] == ["check-target"]:
        print("Docker target configuration accepted (no database connection made).")
        return 0
    if len(sys.argv) < 2:
        return 2
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
