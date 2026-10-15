"""Reuse existing journeys in their seed order on a disposable browser database."""
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

JOURNEYS = (
    ("seed_browser.py", "browser_p1.py"),
    ("seed_browser_p2.py", "browser_p2.py"),
    (None, "browser_p2_complete.py"),
    ("seed_browser_p3.py", "browser_p3.py"),
    (None, "browser_etats_p3.py"),
    ("seed_browser_p4.py", "browser_p4.py"),
    (None, "browser_proforma.py"),
    ("seed_browser_caisse.py", "browser_caisse.py"),
    ("seed_browser_regularisation.py", "browser_regularisation.py"),
    ("seed_browser_clients.py", "browser_clients.py"),
)


def commands(root):
    present = {p.name for p in (root / "tests").glob("browser_*.py")}
    unknown = present - {journey for _, journey in JOURNEYS}
    if unknown:
        raise ValueError(f"Parcours non enregistré : {sorted(unknown)}")
    required_count = 5  # P1/P2/P3 already on main.
    for marker, count in (("vente", 6), ("proforma", 7), ("caisse", 8), ("regularisation", 9)):
        if (root / f"src/neosys_pharma/application/{marker}_service.py").is_file():
            required_count = max(required_count, count)
    if list((root / "migrations/versions").glob("f22f6abb13c5_*.py")):
        required_count = 9
    if list((root / "migrations/versions").glob("20261015_01_*.py")):
        required_count = 10
    missing = {journey for _, journey in JOURNEYS[:required_count]} - present
    if missing:
        raise ValueError(f"Parcours obligatoires absents : {sorted(missing)}")
    result = []
    for seed, journey in JOURNEYS:
        if journey not in present:
            continue
        if seed:
            if not (root / "tests" / seed).is_file():
                raise ValueError(f"Jeu de données absent : {seed}")
            result.append([sys.executable, "tests/" + seed])
        result.append([sys.executable, "tests/" + journey])
    if not result:
        raise ValueError("Aucun parcours navigateur disponible")
    return result


def main():
    root = Path.cwd()
    journeys = commands(root)
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    # Keep the first seed before server startup, as in the existing workflow.
    subprocess.run(journeys.pop(0), check=True, env=os.environ.copy())
    with open("/tmp/neosys-ci-server.log", "w") as log:
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "neosys_pharma.presentation.app:app",
                                   "--host", "127.0.0.1", "--port", "8000"], stdout=log, stderr=log)
        try:
            for _ in range(50):
                try:
                    urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1).close()
                    break
                except OSError:
                    time.sleep(0.2)
            else:
                raise RuntimeError("Serveur de test non disponible")
            for command in journeys:
                subprocess.run(command, check=True, env=os.environ.copy())
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
