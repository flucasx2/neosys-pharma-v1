"""Explicit future setup only; never display secrets or overwrite existing files."""
import os
from pathlib import Path
import secrets


def main():
    root = Path(__file__).resolve().parents[1] / ".secrets"
    paths = [root / "dev-db-password.txt", root / "test-db-password.txt"]
    if any(p.exists() for p in paths):
        raise SystemExit("Existing secret files preserved; no change made.")
    root.mkdir(mode=0o700, exist_ok=True)
    values = [secrets.token_urlsafe(48), secrets.token_urlsafe(48)]
    while values[0] == values[1]:
        values[1] = secrets.token_urlsafe(48)
    for path, value in zip(paths, values):
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
    print("Two distinct Docker-only secrets created; values not displayed.")


if __name__ == "__main__":
    main()
