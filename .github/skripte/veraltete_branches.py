#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ermittelt, welche Branches gegenueber ihrer Basis veraltet sind - also einen
Rebase brauchen (f-reiser/reiser-flow#7).

Reine Hilfsfunktionen ohne Claude, genutzt von branches_synchronisieren.py.
"""
import io
import os
import subprocess
import sys


def lies(pfad):
    try:
        with io.open(pfad, encoding="utf-8") as f:
            return [z.strip() for z in f if z.strip()]
    except OSError:
        return []


def liegt_hinter(repo, branch, haupt="main"):
    """True, wenn 'branch' Commits aus 'haupt' fehlen - ein Rebase ist faellig.

    "git merge-base --is-ancestor origin/<haupt> origin/<branch>" meldet per
    Exit-Code, ob haupt ein Vorfahre von branch ist (0 = ja, 1 = nein). Jeder
    andere Code ist ein echter Git-Fehler (z.B. unbekannter Ref) und wird
    nicht stillschweigend als "veraltet" gewertet.
    """
    lauf = subprocess.run(
        ["git", "-C", repo, "merge-base", "--is-ancestor",
         "origin/%s" % haupt, "origin/%s" % branch],
        capture_output=True, text=True,
    )
    if lauf.returncode == 0:
        return False
    if lauf.returncode == 1:
        return True
    raise RuntimeError("git merge-base fuer %r: %s" % (branch, lauf.stderr.strip()))


def veraltete(repo, branches, basen=None, haupt="main"):
    """Branches aus 'branches' (ohne 'haupt' selbst), die hinter ihrer Basis
    zurueckliegen - Reihenfolge wie in 'branches', doppelte entfernt.

    'basen' bildet Branch -> Quellbranch ab und stammt aus den offenen Pull
    Requests (baseRefName); ohne Eintrag gilt 'haupt'. Das ist keine Feinheit:
    Ein Branch, der laut git-branch-strategie von einem blockierenden Branch
    abzweigt, wuerde durch ein Rebase auf main genau die Commits verlieren,
    derentwegen er dort abzweigt.
    """
    basen = basen or {}
    gesehen = set()
    ergebnis = []
    for b in branches:
        if b == haupt or b in gesehen:
            continue
        gesehen.add(b)
        basis = basen.get(b, haupt)
        if basis == b:
            continue
        if liegt_hinter(repo, b, basis):
            ergebnis.append(b)
    return ergebnis


def lies_basen(pfad):
    """Branch -> Quellbranch aus einer TSV-Datei (Kopf, Basis je Zeile)."""
    basen = {}
    for z in lies(pfad):
        teile = z.split(chr(9))
        if len(teile) >= 2 and teile[0] and teile[1]:
            basen[teile[0]] = teile[1]
    return basen


#  ------------------------------------------------------------------------ main

def main():
    repo = os.environ.get("GITHUB_WORKSPACE", ".")
    branches = lies("branches.txt")
    ver = veraltete(repo, branches, lies_basen("basen.txt"))

    a = os.environ.get("GITHUB_OUTPUT")
    if a:
        io.open(a, "a", encoding="utf-8").write("veraltet=%s\n" % ",".join(ver))
    print("Veraltete Branches: %s" % (", ".join(ver) or "keine"))
    return 0


#  --------------------------------------------------------------------- Selbsttest

def _testrepo():
    """Ein lokales Bare-Repo mit main und drei Branches - real per Git
    erzeugt, nicht gemockt: Der Fallstrick hier ist git selbst (Exit-Codes,
    "origin/"-Prefix), den ein Mock nicht pruefen wuerde."""
    import tempfile

    d = tempfile.mkdtemp()
    arbeit = os.path.join(d, "arbeit")

    def git(*args, cwd=arbeit):
        subprocess.run(["git"] + list(args), cwd=cwd, check=True,
                        capture_output=True)

    os.makedirs(arbeit)
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    io.open(os.path.join(arbeit, "a.txt"), "w").write("1")
    git("add", "a.txt")
    git("commit", "-q", "-m", "erst")

    #  hinter zweigt HIER ab - main laeuft danach weiter, hinter nicht
    git("branch", "hinter")

    io.open(os.path.join(arbeit, "c.txt"), "w").write("3")
    git("add", "c.txt")
    git("commit", "-q", "-m", "main laeuft weiter")

    #  aktuell: zeigt auf denselben (neuesten) Stand wie main -> nicht veraltet
    git("branch", "aktuell")

    #  voraus: enthaelt den neuesten Stand von main, dazu einen eigenen Commit
    git("checkout", "-q", "-b", "voraus")
    io.open(os.path.join(arbeit, "b.txt"), "w").write("2")
    git("add", "b.txt")
    git("commit", "-q", "-m", "voraus")
    git("checkout", "-q", "main")

    #  kind zweigt von hinter ab, nicht von main: Es ist gegenueber main
    #  veraltet, gegenueber seiner eigenen Basis aber aktuell.
    git("branch", "kind", "hinter")

    #  "origin" zeigt auf sich selbst - liegt_hinter() fragt origin/<branch>
    #  ab, genau wie im echten Checkout mit einem Remote.
    spiegel = os.path.join(d, "spiegel.git")
    subprocess.run(["git", "clone", "-q", "--bare", arbeit, spiegel], check=True,
                    capture_output=True)
    git("remote", "add", "origin", spiegel)
    git("fetch", "-q", "origin")
    return arbeit


def selbsttest():
    fehler = []

    def pruefe(name, ist, erwartet):
        if ist != erwartet:
            fehler.append("%s: %r statt %r" % (name, ist, erwartet))

    repo = _testrepo()

    pruefe("auf gleichem Stand: nicht veraltet",
           liegt_hinter(repo, "aktuell"), False)
    pruefe("main bereits enthalten und voraus: nicht veraltet",
           liegt_hinter(repo, "voraus"), False)
    pruefe("main lief weiter: veraltet",
           liegt_hinter(repo, "hinter"), True)

    pruefe("main selbst taucht nie auf",
           veraltete(repo, ["main", "aktuell", "voraus", "hinter"]),
           ["hinter"])
    pruefe("Reihenfolge wie in branches.txt, Duplikate raus",
           veraltete(repo, ["hinter", "aktuell", "hinter"]),
           ["hinter"])
    pruefe("leere Liste bleibt leer", veraltete(repo, []), [])

    #  Ohne Basis-Abbildung zaehlt main - mit ihr der eigene Quellbranch. Genau
    #  hier wuerde ein Rebase auf main einem abhaengigen Branch die Commits
    #  wegziehen, derentwegen er von seinem Blocker abzweigt.
    pruefe("ohne Basis-Angabe gilt main",
           veraltete(repo, ["kind"]), ["kind"])
    pruefe("gegenueber der eigenen Basis aktuell",
           veraltete(repo, ["kind"], {"kind": "hinter"}), [])
    pruefe("gegenueber der eigenen Basis veraltet",
           veraltete(repo, ["hinter"], {"hinter": "voraus"}), ["hinter"])
    pruefe("Basis gleich Branch wird uebersprungen",
           veraltete(repo, ["hinter"], {"hinter": "hinter"}), [])

    pruefe("Basen aus TSV gelesen",
           sorted(lies_basen(os.path.join(repo, "basen_test.txt")).items()),
           [])

    basen_pfad = os.path.join(repo, "basen_test.txt")
    io.open(basen_pfad, "w", encoding="utf-8", newline="").write(
        "kind" + chr(9) + "hinter" + chr(10)
        + "kaputt" + chr(10)
        + "voraus" + chr(9) + "main" + chr(10))
    pruefe("unvollstaendige Zeile faellt weg",
           sorted(lies_basen(basen_pfad).items()),
           [("kind", "hinter"), ("voraus", "main")])

    try:
        liegt_hinter(repo, "gibt-es-nicht")
        fehler.append("unbekannter Branch haette einen Fehler werfen muessen")
    except RuntimeError:
        pass

    gesamt = 12
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(selbsttest() if "--selbsttest" in sys.argv else main())
