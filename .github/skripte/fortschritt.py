#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Der Fortschrittskommentar eines unbeaufsichtigten Laufs.

Ein Lauf, den das Nutzungslimit abschiesst, hinterlaesst sonst nichts: kein Branch,
kein Kommentar, keine Spur - die Arbeit ist weg, und der naechste Lauf faengt von
vorn an. Genau das ist am 12.09. an Vorgang 31 passiert, nach zwanzig Minuten.

Dagegen steht EIN Kommentar je Vorgang, der waehrend der Arbeit fortgeschrieben
wird. Er hat zwei Leser mit derselben Frage: der Mensch, der wissen will, wie weit
es ist, und der Folgelauf, der wissen muss, wo er einsteigt.

Unterbefehle:
    anlegen   findet den Kommentar am Vorgang oder legt ihn an; gibt seine Id aus
    notiz     haengt eine Zeile an, Kommentar per Id (fuer den Runner - das
              Modell bearbeitet den Kommentar direkt)
    vermerk   dasselbe, aber ueber die Vorgangsnummer, und still, wenn es noch
              keinen Kommentar gibt (fuer die Pruefung, die nichts anlegen soll)

WARUM DER RUNNER IHN ANLEGT UND NICHT DAS MODELL
    Weil ein Lauf, der beim ersten Schritt stirbt, sonst wieder nichts hinterlaesst.
    Ist der Kommentar da, bevor das erste Token bezahlt ist, gibt es immer einen Ort,
    an dem etwas stehen kann.
"""
import io
import json
import os
import subprocess
import tempfile
import sys

#  Woran der Kommentar wiedergefunden wird. Unsichtbar im gerenderten Markdown,
#  damit er den Leser nicht stoert - und stabil, damit er nicht am Wortlaut haengt.
MARKE = "<!-- lauf-fortschritt -->"

KOPF = MARKE + chr(10) + "> **Stand der Bearbeitung**"


def gh(*args, eingabe=None):
    p = subprocess.run(["gh"] + list(args), capture_output=True, text=True,
                       encoding="utf-8", input=eingabe)
    if p.returncode != 0:
        raise RuntimeError("gh " + " ".join(args) + ": " + (p.stderr or "").strip())
    return p.stdout


def als_zitat(text):
    """Jede Zeile mit "> " - auch die leeren, sonst bricht das Blockzitat auf."""
    zeilen = text.rstrip(chr(10)).split(chr(10))
    return chr(10).join(("> " + z) if z.strip() else ">" for z in zeilen)


def finde(repo, nr):
    """(id, body) des Fortschrittskommentars, sonst (None, None)."""
    roh = gh("api", "--paginate", "repos/%s/issues/%s/comments" % (repo, nr),
             "--jq", ".[] | {id, body}")
    for zeile in roh.splitlines():
        if not zeile.strip():
            continue
        d = json.loads(zeile)
        if MARKE in (d.get("body") or ""):
            return d["id"], d["body"]
    return None, None


def als_datei(inhalt):
    """Schreibt den Rumpf in eine Datei ausserhalb des Arbeitsverzeichnisses.

    Nicht ins Arbeitsverzeichnis, weil der Rettungsschritt des Workflows
    committet, was im Baum liegt. Hier haelt zwar die Whitelist-.gitignore
    dagegen - aber dieses Skript soll in jedem Repository laufen, und anderswo
    landete die Datei im Commit.
    """
    f = tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8",
                                    newline="", delete=False)
    with f:
        json.dump({"body": inhalt}, f)
    return f.name


def schreibe(repo, kid, body):
    pfad = als_datei(body)
    try:
        gh("api", "--method", "PATCH", "repos/%s/issues/comments/%s" % (repo, kid),
           "--input", pfad)
    finally:
        os.unlink(pfad)


def anlegen(repo, nr, lauf_url, branch):
    kid, body = finde(repo, nr)
    zeile = "Lauf [%s](%s) hat uebernommen, Branch `%s`." % (
        os.environ.get("GITHUB_RUN_ID", "?"), lauf_url, branch)
    if kid is None:
        pfad = als_datei(KOPF + chr(10) + ">" + chr(10) + als_zitat(zeile))
        try:
            roh = gh("api", "--method", "POST",
                     "repos/%s/issues/%s/comments" % (repo, nr), "--input", pfad)
        finally:
            os.unlink(pfad)
        kid = json.loads(roh)["id"]
    else:
        schreibe(repo, kid, body.rstrip(chr(10)) + chr(10) + als_zitat(zeile))
    return kid


def notiz(repo, kid, text):
    roh = gh("api", "repos/%s/issues/comments/%s" % (repo, kid), "--jq", ".body")
    schreibe(repo, kid, roh.rstrip(chr(10)) + chr(10) + als_zitat(text))


def vermerk(repo, nr, text):
    """Anhaengen, wenn es den Kommentar gibt - sonst nichts.

    Die Pruefung laeuft bei JEDEM Push. Legte sie den Kommentar an, entstuende
    er auch fuer Branches, an denen kein unbeaufsichtigter Lauf arbeitet.
    """
    kid, _ = finde(repo, nr)
    if kid is None:
        print("kein Fortschrittskommentar an %s - nichts vermerkt" % nr)
        return False
    notiz(repo, kid, text)
    return True


def main(argv):
    repo = os.environ["GITHUB_REPOSITORY"]
    befehl = argv[0]
    if befehl == "anlegen":
        nr, branch = argv[1], argv[2]
        url = "%s/%s/actions/runs/%s" % (
            os.environ.get("GITHUB_SERVER_URL", "https://github.com"),
            repo, os.environ.get("GITHUB_RUN_ID", ""))
        kid = anlegen(repo, nr, url, branch)
        a = os.environ.get("GITHUB_OUTPUT")
        if a:
            io.open(a, "a", encoding="utf-8").write("kommentar=%s%s" % (kid, chr(10)))
        print(kid)
    elif befehl == "notiz":
        notiz(repo, argv[1], " ".join(argv[2:]))
    elif befehl == "vermerk":
        vermerk(repo, argv[1], " ".join(argv[2:]))
    else:
        raise SystemExit("unbekannter Unterbefehl: " + befehl)
    return 0


def selbsttest():
    """Die beiden Zusagen, die ohne GitHub pruefbar sind - und beide sind die,

    an denen es schiefgeht: Bricht das Blockzitat auf, steht die Haelfte des Standes
    als Fliesstext im Issue; findet die Marke den Kommentar nicht wieder, legt jeder
    Lauf einen neuen an - genau das, was nicht passieren soll.
    """
    fehler = []

    def gleich(name, ist, soll):
        if ist != soll:
            fehler.append("%s: %r statt %r" % (name, ist, soll))

    NL = chr(10)

    gleich("eine Zeile", als_zitat("Hallo"), "> Hallo")
    gleich("zwei Zeilen", als_zitat("a" + NL + "b"), "> a" + NL + "> b")
    #  Eine leere Zeile ohne ">" beendet das Blockzitat - alles danach faellt heraus.
    gleich("leere Zeile behaelt das Zeichen",
           als_zitat("a" + NL + NL + "b"), "> a" + NL + ">" + NL + "> b")
    gleich("nur Leerraum zaehlt als leer",
           als_zitat("a" + NL + "   " + NL + "b"), "> a" + NL + ">" + NL + "> b")
    gleich("abschliessende Umbrueche fallen weg", als_zitat("a" + NL + NL), "> a")
    gleich("leerer Text", als_zitat(""), ">")

    #  Die Marke muss unsichtbar sein: Steht sie im gerenderten Text, liest sie der
    #  Nutzer mit. Ein HTML-Kommentar ist das; gepruefft wird, dass es einer bleibt.
    if not (MARKE.startswith("<!--") and MARKE.endswith("-->")):
        fehler.append("MARKE ist kein HTML-Kommentar: %r" % MARKE)
    if MARKE not in KOPF:
        fehler.append("KOPF traegt die Marke nicht - der Kommentar waere unauffindbar")
    if not KOPF.split(chr(10))[1].startswith(">"):
        fehler.append("KOPF beginnt nicht als Blockzitat")

    #  finde() gegen eine vorgegebene Antwort statt gegen GitHub
    global gh
    echt = gh
    try:
        antwort = (json.dumps({"id": 1, "body": "irgendein Kommentar"}) + chr(10) +
                   json.dumps({"id": 7, "body": KOPF + chr(10) + "> etwas"}) + chr(10))
        gh = lambda *a, **k: antwort
        gleich("finde() nimmt den mit der Marke", finde("o/r", "1")[0], 7)
        gh = lambda *a, **k: json.dumps({"id": 1, "body": "ohne Marke"}) + chr(10)
        gleich("ohne Marke nichts", finde("o/r", "1")[0], None)
        gh = lambda *a, **k: ""
        gleich("gar keine Kommentare", finde("o/r", "1")[0], None)
    finally:
        gh = echt

    #  vermerk() darf keinen Kommentar anlegen, wenn es keinen gibt - sonst
    #  wuerde die Pruefung an jedem fremden Branch einen erzeugen.
    echt2 = gh
    try:
        gh = lambda *a, **k: ""
        if vermerk("o/r", "9", "egal") is not False:
            fehler.append("vermerk() meldet Erfolg ohne vorhandenen Kommentar")
    finally:
        gh = echt2

    gesamt = 13
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


if __name__ == "__main__":
    if "--selbsttest" in sys.argv:
        sys.exit(selbsttest())
    sys.exit(main(sys.argv[1:]))
