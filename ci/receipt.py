"""Publish an explicit status on the tested HEAD, never on an implicit merge SHA."""
import json
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request
from policy import CONTEXT, SHA, verdict


def api(path, data=None):
    url = os.environ.get("GITHUB_API_URL", "https://api.github.com") + path
    headers = {"Authorization": "Bearer " + os.environ["GH_TOKEN"],
               "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    request = urllib.request.Request(url, headers=headers,
                                    data=json.dumps(data).encode() if data is not None else None)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def current_head(event, payload, repo):
    if event == "pull_request":
        return api(f"/repos/{repo}/pulls/{payload['number']}")["head"]["sha"]
    ref = os.environ["GITHUB_REF"]
    if not ref.startswith("refs/heads/"):
        raise ValueError("La recette doit sélectionner une branche, pas un tag")
    return api(f"/repos/{repo}/git/ref/heads/{urllib.parse.quote(ref[11:], safe='/')}")["object"]["sha"]


def status(repo, sha, state, description):
    api(f"/repos/{repo}/statuses/{sha}", {
        "state": state, "context": CONTEXT, "description": description[:140],
        "target_url": os.environ["GITHUB_SERVER_URL"] + "/" + repo + "/actions/runs/" + os.environ["GITHUB_RUN_ID"],
    })


def main():
    event = os.environ["GITHUB_EVENT_NAME"]
    payload = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    repo, sha = os.environ["GITHUB_REPOSITORY"], os.environ["TESTED_SHA"]
    if not SHA.fullmatch(sha):
        raise ValueError("SHA de recette invalide")
    # Fork tokens cannot publish statuses; never report their gate as successful.
    if event == "pull_request" and payload["pull_request"]["head"]["repo"]["full_name"] != repo:
        raise ValueError("Recette finale sur branche interne nécessaire pour cette PR externe")
    if sys.argv[1] == "start":
        status(repo, sha, "pending", "Validation complète de ce commit en attente")
        return
    actual = os.environ["ACTUAL_SHA"]
    results = json.loads(os.environ["JOB_RESULTS"])
    try:
        state, message = verdict(os.environ["FULL"] == "true", results, sha,
                                 current_head(event, payload, repo), actual)
    except Exception:
        # A failed lookup must revoke the pending status, never produce success.
        status(repo, sha, "failure", "Impossible de vérifier le commit courant")
        raise
    status(repo, sha, state, message)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
        out.write(f"## Recette `{sha}`\n\nÉtat : **{state}** — {message}.\n\n")
        out.write("```json\n" + json.dumps(results, indent=2) + "\n```\n")
    if state == "failure":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
