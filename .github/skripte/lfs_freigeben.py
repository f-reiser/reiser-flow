#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gibt Git-LFS-Sperren frei, sobald der Pull Request, der sie hielt, nach
main gemergt ist (f-reiser/reiser-flow#78).

Ersetzt den manuellen "git lfs unlock nach dem Merge"-Schritt aus
repo-hygiene: zum Merge-Zeitpunkt laeuft in aller Regel keine Sitzung mehr,
die ihn nachholen koennte.
"""
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timezone


def _als_zeit(iso):
    """ISO-8601 mit optionalem 'Z' zu einem vergleichbaren datetime."""
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def dateien_freizugeben(gemergte_dateien, sperren, merge_zeit):
    """IDs der Sperren, die nach diesem Merge freigegeben werden duerfen.

    'sperren': [{"id": str, "path": str, "locked_at": ISO-8601-str}, ...],
    wie 'git lfs locks --json' sie liefert.

    Eine Sperre wird nur freigegeben, wenn ihr Pfad zu den vom Merge
    geaenderten Dateien gehoert UND sie schon VOR dem Merge bestand. Die
    zweite Bedingung schliesst die Luecke zwischen Merge und diesem Lauf:
    Ohne sie wuerde eine ganz neue, unabhaengige Sperre auf demselben Pfad
    (von jemandem, der sofort nach dem sichtbaren Merge weiterarbeitet)
    versehentlich mit aufgehoben. Da GitHub eine Sperre serverseitig
    durchsetzt (`lockable` in .gitattributes), kann zum Merge-Zeitpunkt
    ohnehin nur die Sperre bestehen, die der Merge selbst gehalten hat -
    niemand sonst haette in der Zwischenzeit pushen koennen.
    """
    merge_dt = _als_zeit(merge_zeit)
    dateien = set(gemergte_dateien)
    return [s["id"] for s in sperren
            if s["path"] in dateien and _als_zeit(s["locked_at"]) <= merge_dt]


#  --------------------------------------------------------------------- main

def _pr_dateien(repo, nr):
    lauf = subprocess.run(
        ["gh", "api", "--paginate", "repos/%s/pulls/%s/files" % (repo, nr),
         "--jq", ".[].filename"],
        capture_output=True, text=True, check=True,
    )
    return [z for z in lauf.stdout.splitlines() if z.strip()]


def _aktuelle_sperren(arbeitsverzeichnis):
    lauf = subprocess.run(
        ["git", "-C", arbeitsverzeichnis, "lfs", "locks", "--json"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(lauf.stdout or "[]")


def main():
    if os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        print("Kein pull_request-Ereignis, nichts zu tun.")
        return 0

    with io.open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
        ereignis = json.load(f)
    pr = ereignis.get("pull_request") or {}
    if ereignis.get("action") != "closed" or not pr.get("merged"):
        print("Kein Merge, nichts zu tun.")
        return 0

    repo = os.environ.get("GITHUB_WORKSPACE", ".")
    repo_slug = os.environ["GITHUB_REPOSITORY"]

    gemergte_dateien = _pr_dateien(repo_slug, pr["number"])
    sperren = _aktuelle_sperren(repo)
    ids = dateien_freizugeben(gemergte_dateien, sperren, pr["merged_at"])

    for i in ids:
        subprocess.run(["git", "-C", repo, "lfs", "unlock", "--id", i, "--force"],
                        check=True)

    print("Freigegeben: %s" % ", ".join(ids) if ids else "Keine Sperre freizugeben.")
    return 0


#  --------------------------------------------------------------------- Selbsttest

def selbsttest():
    fehler = []

    def pruefe(name, ist, erwartet):
        if ist != erwartet:
            fehler.append("%s: %r statt %r" % (name, ist, erwartet))

    merge_zeit = "2026-09-24T10:00:00Z"

    pruefe(
        "Sperre auf geaenderter Datei, vor dem Merge gesetzt -> freigeben",
        dateien_freizugeben(
            ["a.xlsx"],
            [{"id": "1", "path": "a.xlsx", "locked_at": "2026-09-24T09:00:00Z"}],
            merge_zeit,
        ),
        ["1"],
    )

    pruefe(
        "Sperre auf NICHT geaenderter Datei -> unberuehrt",
        dateien_freizugeben(
            ["b.xlsx"],
            [{"id": "1", "path": "a.xlsx", "locked_at": "2026-09-24T09:00:00Z"}],
            merge_zeit,
        ),
        [],
    )

    pruefe(
        "Sperre NACH dem Merge gesetzt (neue, unabhaengige Aenderung) -> unberuehrt",
        dateien_freizugeben(
            ["a.xlsx"],
            [{"id": "1", "path": "a.xlsx", "locked_at": "2026-09-24T10:00:01Z"}],
            merge_zeit,
        ),
        [],
    )

    pruefe(
        "Sperre exakt zum Merge-Zeitpunkt gesetzt -> freigeben (Grenzfall inklusiv)",
        dateien_freizugeben(
            ["a.xlsx"],
            [{"id": "1", "path": "a.xlsx", "locked_at": merge_zeit}],
            merge_zeit,
        ),
        ["1"],
    )

    pruefe(
        "mehrere Sperren, nur die passenden freigeben",
        dateien_freizugeben(
            ["a.xlsx", "c.docx"],
            [
                {"id": "1", "path": "a.xlsx", "locked_at": "2026-09-24T09:00:00Z"},
                {"id": "2", "path": "b.xlsx", "locked_at": "2026-09-24T09:00:00Z"},
                {"id": "3", "path": "c.docx", "locked_at": "2026-09-24T09:59:00Z"},
            ],
            merge_zeit,
        ),
        ["1", "3"],
    )

    pruefe(
        "keine Sperren -> leere Liste, kein Fehler",
        dateien_freizugeben(["a.xlsx"], [], merge_zeit),
        [],
    )

    pruefe(
        "keine gemergten Dateien -> leere Liste",
        dateien_freizugeben(
            [],
            [{"id": "1", "path": "a.xlsx", "locked_at": "2026-09-24T09:00:00Z"}],
            merge_zeit,
        ),
        [],
    )

    gesamt = 7
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(selbsttest() if "--selbsttest" in sys.argv else main())
