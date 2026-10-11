"""Small fail-closed CI policy; no application imports or third-party dependencies."""
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath

SHA = re.compile(r"^[0-9a-f]{40}$")
REQUIRED = ("sqlite", "postgres", "browser")
CONTEXT = "neosys/recette-complete"


def documentation(path):
    p = PurePosixPath(path)
    if ".." in p.parts:
        return False
    return path in {"README.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE"} or (
        len(p.parts) > 1 and p.parts[0] == "docs" and p.suffix in {".md", ".rst", ".txt"}
    )


def classify(paths):
    # Empty/unknown changes are never treated as documentation.
    return not paths or not all(documentation(p) for p in paths)


def plan(event, payload, sha, paths):
    if not SHA.fullmatch(sha):
        raise ValueError("SHA complet obligatoire")
    code = classify(paths)
    pr = payload.get("pull_request", {})
    if event not in {"pull_request", "push", "workflow_dispatch"}:
        raise ValueError("Événement non pris en charge")
    full = event == "workflow_dispatch" or (
        event == "pull_request" and not pr.get("draft", True) and code
    )
    return {"sha": sha, "code": code, "sqlite": code or full, "full": full}


def verdict(full, results, tested_sha, current_sha, actual_sha):
    if tested_sha != current_sha or tested_sha != actual_sha:
        return "failure", "Commit obsolète ou checkout différent du commit demandé"
    if not full:
        return "pending", "Recette complète requise ; SQLite seul ou documentation ne la valide pas"
    if any(results.get(job) != "success" for job in REQUIRED):
        return "failure", "Recette incomplète : SQLite, PostgreSQL/migrations et Chromium doivent réussir"
    return "success", "Recette complète réussie sur ce commit exact"


def changed_paths(before, after):
    if not SHA.fullmatch(before) or not SHA.fullmatch(after):
        raise ValueError("Bornes du diff invalides")
    # --no-renames includes BOTH old and new paths: code renamed into docs is still code.
    raw = subprocess.check_output(["git", "diff", "--name-only", "--no-renames", "-z", before, after])
    return [p.decode("utf-8", errors="strict") for p in raw.split(b"\0") if p]


def main():
    payload = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    event = os.environ["GITHUB_EVENT_NAME"]
    sha = payload["pull_request"]["head"]["sha"] if event == "pull_request" else os.environ["GITHUB_SHA"]
    paths = []
    if event == "pull_request":
        before = payload.get("before") if payload.get("action") == "synchronize" else None
        before = before or payload["pull_request"]["base"]["sha"]
        try:
            paths = changed_paths(before, sha)
        except (subprocess.CalledProcessError, ValueError, UnicodeError):
            # Force-push may make the previous head unreachable: inspect the whole PR.
            try:
                paths = changed_paths(payload["pull_request"]["base"]["sha"], sha)
            except (subprocess.CalledProcessError, ValueError, UnicodeError):
                paths = []  # Unknown => application checks, never documentation exemption.
    elif event == "push":
        before = payload.get("before", "")
        if before and before != "0" * 40:
            try:
                paths = changed_paths(before, sha)
            except (subprocess.CalledProcessError, ValueError, UnicodeError):
                paths = []
    result = plan(event, payload, sha, paths)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
        for k, v in result.items():
            out.write(f"{k}={str(v).lower() if isinstance(v, bool) else v}\n")
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
        out.write(f"Commit : `{sha}`\n\nModifications applicatives : {result['code']}. "
                  f"Suite complète : {result['full']}.\n\n")
        if not result["full"]:
            out.write("**Ce contrôle léger ne constitue pas une recette complète.**\n")


if __name__ == "__main__":
    main()
