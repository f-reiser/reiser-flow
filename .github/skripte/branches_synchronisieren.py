#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bringt offene Branches per echtem Rebase und Push auf den Stand ihrer Basis
(f-reiser/reiser-flow#7).

Anders als veraltete_branches.py (reine Vorpruefung, ob ein Rebase faellig
ist) fuehrt dieses Skript den Rebase wirklich aus. Es ist bewusst von Claude
getrennt: Loest git den Rebase konfliktfrei, kostet das nichts. Nur wenn ein
echter Konflikt bleibt, ist ueberhaupt ein Modell noetig - und das entscheidet
der Aufrufer anhand des Ausgangs "konflikt", nicht dieses Skript selbst.

Eigenstaendig aufrufbar (nicht an claude-aufgaben.yml gebunden), damit
mehrere Stellen es nutzen koennen: nach einem Merge nach main und als
naechtliche Nachschau.
"""
import io
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import veraltete_branches as vb  # noqa: E402  (liegt_hinter, veraltete, lies, lies_basen)


def konfliktdateien(repo):
    """Dateien mit ungeloestem Merge-Konflikt im Arbeitsbaum von 'repo'."""
    lauf = subprocess.run(
        ["git", "-C", repo, "diff", "--name-only", "--diff-filter=U"],
        capture_output=True, text=True, check=True,
    )
    return [z for z in lauf.stdout.splitlines() if z.strip()]


def betrifft_workflows(repo, branch, basis):
    """True, wenn 'branch' gegenueber 'basis' eigene Aenderungen unter
    .github/workflows/ mitbringt.

    Das GITHUB_TOKEN eines Workflow-Laufs darf solche Aenderungen nicht
    pushen, weil ihm die Berechtigung 'workflows' fehlt - der Push schlaegt
    sonst fehl (f-reiser/reiser-flow#62). Der Drei-Punkt-Diff zeigt genau die
    Commits, die 'branch' seit seiner Abspaltung von 'basis' selbst
    beigetragen hat, nicht was 'basis' inzwischen an Workflow-Dateien enthaelt.
    """
    lauf = subprocess.run(
        ["git", "-C", repo, "diff", "--name-only",
         "origin/%s...origin/%s" % (basis, branch), "--", ".github/workflows"],
        capture_output=True, text=True, check=True,
    )
    return bool(lauf.stdout.strip())


def synchronisiere(repo, branch, basis="main"):
    """Rebase 'branch' auf 'basis' und pusht bei Erfolg nach origin.

    Rueckgabe: ("aufgefrischt", []), ("konflikt", [dateien]) oder
    ("uebersprungen", []) fuer einen Branch mit eigenen Aenderungen an
    Workflow-Dateien (siehe betrifft_workflows). Ein Rebase-Fehler ohne
    Konfliktdateien ist kein Konflikt, sondern ein echter Git-Fehler und
    wird nicht stillschweigend geschluckt.

    Nimmt an, dass 'repo' ein 'origin'-Remote mit 'branch' und 'basis' hat.
    """
    def git(*args, check=True):
        return subprocess.run(["git", "-C", repo] + list(args),
                               capture_output=True, text=True, check=check)

    git("fetch", "-q", "origin", branch, basis)
    if betrifft_workflows(repo, branch, basis):
        return "uebersprungen", []
    git("checkout", "-q", "-B", branch, "origin/%s" % branch)
    lauf = git("rebase", "origin/%s" % basis, check=False)
    if lauf.returncode == 0:
        git("push", "-q", "--force-with-lease", "origin", branch)
        return "aufgefrischt", []

    dateien = konfliktdateien(repo)
    git("rebase", "--abort", check=False)
    if not dateien:
        raise RuntimeError("git rebase fuer %r: %s" % (branch, lauf.stderr.strip()))
    return "konflikt", dateien


#  --------------------------------------------------------------------- main

def main():
    repo = os.environ.get("GITHUB_WORKSPACE", ".")
    haupt = os.environ.get("HAUPTBRANCH", "main")
    branches = vb.lies("branches.txt")
    basen = vb.lies_basen("basen.txt")
    kandidaten = vb.veraltete(repo, branches, basen, haupt)

    aufgefrischt = []
    konflikte = []
    uebersprungen = []
    for b in kandidaten:
        basis = basen.get(b, haupt)
        ergebnis, dateien = synchronisiere(repo, b, basis)
        if ergebnis == "aufgefrischt":
            aufgefrischt.append(b)
        elif ergebnis == "uebersprungen":
            uebersprungen.append(b)
        else:
            konflikte.append((b, dateien))

    a = os.environ.get("GITHUB_OUTPUT")
    if a:
        with io.open(a, "a", encoding="utf-8") as f:
            f.write("aufgefrischt=%s\n" % ",".join(aufgefrischt))
            f.write("konflikte=%s\n" % ",".join(b for b, _ in konflikte))
            f.write("uebersprungen=%s\n" % ",".join(uebersprungen))

    if aufgefrischt:
        print("Aufgefrischt: %s" % ", ".join(aufgefrischt))
    if uebersprungen:
        print("Uebersprungen (eigene Aenderung an Workflow-Dateien): %s" % ", ".join(uebersprungen))
    for b, dateien in konflikte:
        print("Konflikt auf %s: %s" % (b, ", ".join(dateien)))
    if not aufgefrischt and not konflikte and not uebersprungen:
        print("Nichts zu tun.")
    return 0


#  --------------------------------------------------------------------- Selbsttest

def _testrepo():
    """Ein lokales Bare-Repo mit main und drei Branches, real per Git erzeugt:

    'sauber'    haengt hinter main, aendert eine andere Datei -> Rebase glatt.
    'aktuell'   enthaelt main bereits -> kein Kandidat, wird nicht angefasst.
    'kaputt'    aendert dieselbe Zeile wie main -> Rebase mit echtem Konflikt.
    """
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
    io.open(os.path.join(arbeit, "geteilt.txt"), "w").write("erste Zeile\n")
    io.open(os.path.join(arbeit, "sauber.txt"), "w").write("start\n")
    git("add", ".")
    git("commit", "-q", "-m", "erst")

    git("branch", "sauber")
    git("branch", "kaputt")
    git("branch", "workflow")

    #  main laeuft weiter: aendert 'geteilt.txt'
    io.open(os.path.join(arbeit, "geteilt.txt"), "w").write("zeile von main\n")
    git("add", "geteilt.txt")
    git("commit", "-q", "-m", "main aendert geteilt.txt")

    git("branch", "aktuell")

    #  sauber: eigener Commit auf einer ANDEREN Datei -> Rebase glatt
    git("checkout", "-q", "sauber")
    io.open(os.path.join(arbeit, "sauber.txt"), "w").write("start\nweiter\n")
    git("add", "sauber.txt")
    git("commit", "-q", "-m", "sauber aendert sauber.txt")

    #  kaputt: eigener Commit auf DERSELBEN Zeile -> Rebase mit Konflikt
    git("checkout", "-q", "kaputt")
    io.open(os.path.join(arbeit, "geteilt.txt"), "w").write("zeile von kaputt\n")
    git("add", "geteilt.txt")
    git("commit", "-q", "-m", "kaputt aendert geteilt.txt anders")

    #  workflow: eigener Commit unter .github/workflows -> das GITHUB_TOKEN
    #  darf so etwas nicht pushen (fehlende 'workflows'-Berechtigung), der
    #  Branch muss deshalb ausgespart werden (f-reiser/reiser-flow#62).
    git("checkout", "-q", "workflow")
    os.makedirs(os.path.join(arbeit, ".github", "workflows"), exist_ok=True)
    io.open(os.path.join(arbeit, ".github", "workflows", "x.yml"), "w").write("name: x\n")
    git("add", ".github/workflows/x.yml")
    git("commit", "-q", "-m", "workflow aendert eine Workflow-Datei")

    git("checkout", "-q", "main")

    spiegel = os.path.join(d, "spiegel.git")
    subprocess.run(["git", "clone", "-q", "--bare", arbeit, spiegel], check=True,
                    capture_output=True)
    git("remote", "add", "origin", spiegel)
    git("fetch", "-q", "origin")
    return arbeit


def _branch_commits(repo, branch):
    lauf = subprocess.run(
        ["git", "-C", repo, "log", "--format=%s", "origin/%s" % branch],
        capture_output=True, text=True, check=True,
    )
    return lauf.stdout.splitlines()


def selbsttest():
    fehler = []

    def pruefe(name, ist, erwartet):
        if ist != erwartet:
            fehler.append("%s: %r statt %r" % (name, ist, erwartet))

    repo = _testrepo()

    ergebnis, dateien = synchronisiere(repo, "sauber", "main")
    pruefe("sauberer Rebase: aufgefrischt", ergebnis, "aufgefrischt")
    pruefe("sauberer Rebase: keine Konfliktdateien", dateien, [])
    pruefe("origin/sauber enthaelt main-Commit jetzt",
           "main aendert geteilt.txt" in _branch_commits(repo, "sauber"), True)

    ergebnis, dateien = synchronisiere(repo, "kaputt", "main")
    pruefe("Konflikt erkannt", ergebnis, "konflikt")
    pruefe("Konfliktdatei genannt", dateien, ["geteilt.txt"])
    pruefe("origin/kaputt NICHT veraendert (kein halber Rebase gepusht)",
           _branch_commits(repo, "kaputt")[0], "kaputt aendert geteilt.txt anders")

    status = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                             capture_output=True, text=True, check=True).stdout
    pruefe("Arbeitsbaum nach abgebrochenem Rebase sauber", status.strip(), "")

    ergebnis, dateien = synchronisiere(repo, "workflow", "main")
    pruefe("Workflow-Aenderung wird ausgespart", ergebnis, "uebersprungen")
    pruefe("keine Konfliktdateien fuer ausgesparten Branch", dateien, [])
    pruefe("origin/workflow NICHT veraendert (kein Push versucht)",
           _branch_commits(repo, "workflow")[0], "workflow aendert eine Workflow-Datei")

    #  main() nur ueber die tatsaechlich veralteten Branches - 'aktuell' bleibt
    #  unberuehrt, sonst wuerde jeder Lauf auch aktuelle Branches anfassen.
    import tempfile
    d = tempfile.mkdtemp()
    os.chdir(d)
    io.open("branches.txt", "w", encoding="utf-8").write(
        "main\nsauber\naktuell\nkaputt\nworkflow\n")
    io.open("basen.txt", "w", encoding="utf-8").write("")
    os.environ["GITHUB_WORKSPACE"] = repo
    os.environ.pop("GITHUB_OUTPUT", None)
    #  'sauber' ist nach dem Aufruf oben schon aufgefrischt - main() muss das
    #  gegen die *neue* origin/main-Basis erneut pruefen, nicht platt wiederholen.
    rc = main()
    pruefe("main() beendet erfolgreich", rc, 0)

    gesamt = 9
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(selbsttest() if "--selbsttest" in sys.argv else main())
