"""Resolve a manual recipe target independently of the selected control workflow."""
import subprocess
import urllib.parse
from policy import SHA
from receipt import api


def resolve(repo, branch, expected_sha):
    if not SHA.fullmatch(expected_sha):
        raise ValueError('Le SHA attendu doit contenir exactement 40 caractères hexadécimaux')
    if not branch or branch.startswith('-'):
        raise ValueError('Branche cible obligatoire')
    subprocess.run(['git', 'check-ref-format', '--branch', branch], check=True, capture_output=True)
    current = api(f'/repos/{repo}/git/ref/heads/{urllib.parse.quote(branch, safe="/")}')['object']['sha']
    if current != expected_sha:
        raise ValueError('Le HEAD cible a changé : actualiser explicitement le SHA attendu')
    return current
