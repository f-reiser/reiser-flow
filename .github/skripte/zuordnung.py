#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ordnet offenen Vorgaengen ihre bereits vorhandenen Branches zu.

Liest zwei Dateien, die der Workflow-Schritt vorher erzeugt hat:
    nummern.txt     je Zeile die Nummer eines Vorgangs mit Auftragslabel
    branches.txt    je Zeile der Name eines Branches im Repository
    kandidaten.txt  je Zeile "<nr>	<updatedAt>	<titel>" fuer jeden dieser Vorgaenge

Schreibt nach GITHUB_OUTPUT:
    offen       Zahl der Vorgaenge mit Auftragslabel
    vorgang     die Nummer, mit der dieser Lauf ANFAENGT
    branch      der Branchname dazu - schon vorhanden oder neu zu bilden
    fortsetzen  angefangene Vorgaenge als "nr auf branch", mit "; " getrennt
                (sonst leer). Hoechstens so viele, wie ein Durchgang
                ueberhaupt annehmen darf - der Rest wartet auf den naechsten.

WARUM DAS HIER STEHT UND NICHT IM PROMPT
    Ein abgebrochener Lauf hinterlaesst einen Branch, waehrend das Issue
    sein Label behaelt. Wer den fortsetzt, darf nicht davon abhaengen, dass
    das Modell (a) dasselbe Issue nochmal auswaehlt und (b) beim Suchen
    dasselbe Namensschema raet, das der vorige Lauf beim Anlegen benutzt
    hat. Beides entscheidet jetzt der Runner, bevor das Modell startet -
    das kostet nichts und kann nicht anders ausgehen.

    Aus demselben Grund benennt der Runner auch den ERSTEN Vorgang und seinen
    Branch: Nur so kann der Branch angelegt und gepusht sein, bevor das erste
    Token bezahlt ist. Ein Lauf, den das Nutzungslimit nach zwanzig Minuten
    abschiesst, hinterlaesst dann wenigstens einen Ort, an dem etwas steht.
"""
import io
import os
import re
import sys

#  Das Schema aus git-branch-strategie. Streng geprueft, weil ein
#  abweichender Name genau den Fall unauffindbar macht, fuer den es
#  diese Datei gibt.
SCHEMA = re.compile(r"^issue-(\d+)-[A-Za-z0-9._-]+$")

#  Deckungsgleich mit "Hoechstens drei Vorgaenge pro Durchgang" aus
#  github-issue-workflow. Mehr anzureichen waere sinnlos: Der Lauf duerfte
#  sie ohnehin nicht annehmen.
HOECHSTENS = 3


def lies(pfad):
    try:
        with io.open(pfad, encoding="utf-8") as f:
            return [z.strip() for z in f if z.strip()]
    except OSError:
        return []


def zuordnen(nummern, branches):
    """(paare, meldungen) - paare als Liste (nr, branch), hoechstens HOECHSTENS"""
    offen = sorted({int(n) for n in nummern if n.isdigit()})
    je_nummer = {}
    fremd = []
    for b in branches:
        if b == "main":
            continue
        m = SCHEMA.match(b)
        if m:
            je_nummer.setdefault(int(m.group(1)), []).append(b)
        else:
            fremd.append(b)

    meldungen = []
    for b in fremd:
        #  Kein Abbruch: Ein Branch darf auch aus anderem Anlass entstehen.
        #  Sichtbar muss es trotzdem sein, denn wenn ein Lauf das Schema
        #  verlaesst, findet der naechste seine Arbeit nicht wieder.
        meldungen.append("Branch ausserhalb des Schemas issue-<nr>-<slug>: " + b)

    for nr, bs in sorted(je_nummer.items()):
        if nr not in offen:
            meldungen.append("Branch ohne offenen Auftrag (Label entfernt?): "
                             + ", ".join(sorted(bs)))

    paare = []
    for nr, bs in sorted(je_nummer.items()):
        if nr not in offen:
            continue
        if len(bs) > 1:
            #  Zwei Branches zu einem Vorgang kann der Runner nicht
            #  aufloesen; raten waere schlimmer als abgeben.
            meldungen.append("Mehrere Branches zu Vorgang %d (%s) - keine "
                             "Vorgabe, das Modell entscheidet."
                             % (nr, ", ".join(sorted(bs))))
            continue
        paare.append((nr, bs[0]))

    if len(paare) > HOECHSTENS:
        meldungen.append("Angefangen sind %d Vorgaenge; %d passen in einen "
                         "Durchgang, der Rest wartet: %s"
                         % (len(paare), HOECHSTENS,
                            ", ".join(str(n) for n, _ in paare[HOECHSTENS:])))
        paare = paare[:HOECHSTENS]
    return paare, meldungen


UMLAUTE = {"ä": "ae", "ö": "oe", "ü": "ue",
           "Ä": "ae", "Ö": "oe", "Ü": "ue", "ß": "ss"}

#  Lang genug, um den Vorgang wiederzuerkennen, kurz genug fuer eine Zeile im
#  "git branch"-Listing.
SLUG_LAENGE = 40


def slug(titel):
    """Titel zu einem Branchteil, der SCHEMA erfuellt.

    Nicht kosmetisch: Faellt der Slug leer aus oder enthaelt er ein Zeichen
    ausserhalb des Schemas, findet der naechste Lauf den Branch nicht wieder -
    genau der Fall, den diese Datei verhindern soll.
    """
    text = "".join(UMLAUTE.get(z, z) for z in titel).lower()
    sauber = []
    for z in text:
        sauber.append(z if (z.isascii() and (z.isalnum() or z in "._")) else "-")
    wort = "".join(sauber).strip("-")
    while "--" in wort:
        wort = wort.replace("--", "-")
    wort = wort[:SLUG_LAENGE].strip("-.")
    return wort or "vorgang"


def waehle_vorgang(paare, kandidaten):
    """(nr, branch) fuer den Vorgang, mit dem dieser Lauf anfaengt - sonst (None, None).

    kandidaten: [(nr, updatedAt, titel), ...]
    """
    #  Angefangenes zuerst - und zwar auf SEINEM Branch, sonst waere die ganze
    #  Zuordnung oben umsonst.
    if paare:
        return paare[0][0], paare[0][1]
    if not kandidaten:
        return None, None
    #  Sonst das am laengsten Unveraenderte: "updatedAt" aufsteigend, bei
    #  Gleichstand die kleinere Nummer, damit zwei Laeufe dasselbe waehlen.
    nr, _, titel = sorted(kandidaten, key=lambda k: (k[1], k[0]))[0]
    return nr, "issue-%d-%s" % (nr, slug(titel))


def lies_kandidaten(pfad):
    """[(nr, updatedAt, titel), ...] - Zeilen ohne Nummer werden uebergangen."""
    kandidaten = []
    for zeile in lies(pfad):
        teile = zeile.split(chr(9))
        if len(teile) < 3 or not teile[0].strip().isdigit():
            continue
        kandidaten.append((int(teile[0].strip()), teile[1].strip(),
                           chr(9).join(teile[2:]).strip()))
    return kandidaten


def main():
    nummern = lies("nummern.txt")
    branches = lies("branches.txt")
    paare, meldungen = zuordnen(nummern, branches)
    offen = len({n for n in nummern if n.isdigit()})
    fortsetzen = "; ".join("%d auf %s" % p for p in paare)

    nr, branch = waehle_vorgang(paare, lies_kandidaten("kandidaten.txt"))

    zeilen = ["Vorgaenge mit Auftragslabel: %d" % offen]
    zeilen.append("Dieser Lauf faengt an mit: "
                  + ("%s auf %s" % (nr, branch) if nr else "nichts"))
    zeilen.append("Fortsetzen: " + (fortsetzen or "nichts angefangen"))
    zeilen += meldungen

    text = chr(10).join(zeilen)
    print(text)
    z = os.environ.get("GITHUB_STEP_SUMMARY")
    if z:
        io.open(z, "a", encoding="utf-8").write(text + chr(10))
    a = os.environ.get("GITHUB_OUTPUT")
    if a:
        io.open(a, "a", encoding="utf-8").write(
            "offen=%d%sfortsetzen=%s%svorgang=%s%sbranch=%s%s"
            % (offen, chr(10), fortsetzen, chr(10),
               nr or "", chr(10), branch or "", chr(10)))
    return 0


def selbsttest():
    fehler = []

    def pruefe(name, fn, erwartet):
        try:
            ist = fn()
        except Exception as ex:
            ist = "AUSNAHME %s" % ex
        if ist != erwartet:
            fehler.append("%s: %r statt %r" % (name, ist, erwartet))

    def paare(nummern, branches):
        return zuordnen(nummern, branches)[0]

    def meldet(nummern, branches, teil):
        return any(teil in m for m in zuordnen(nummern, branches)[1])

    #  Der Normalfall, um den es geht
    pruefe("angefangener Vorgang wird gereicht",
           lambda: paare(["7", "13"], ["main", "issue-7-leer-definition"]),
           [(7, "issue-7-leer-definition")])

    #  Mehrere angefangene: alle, aufsteigend
    pruefe("mehrere, aufsteigend",
           lambda: paare(["7", "13"], ["issue-13-x", "issue-7-y"]),
           [(7, "issue-7-y"), (13, "issue-13-x")])

    #  Mehr als in einen Durchgang passen: gekappt und gemeldet
    viele = [str(n) for n in (3, 5, 7, 9)]
    zweige = ["issue-%d-x" % n for n in (3, 5, 7, 9)]
    pruefe("auf HOECHSTENS gekappt",
           lambda: len(paare(viele, zweige)), HOECHSTENS)
    pruefe("und der Rest genannt",
           lambda: meldet(viele, zweige, "der Rest wartet"), True)

    #  Aehnliche Nummer darf nicht treffen
    pruefe("17 ist nicht 7", lambda: paare(["7"], ["main", "issue-17-etwas"]), [])

    #  Nichts angefangen
    pruefe("ohne Branch nichts", lambda: paare(["7", "13"], ["main"]), [])

    #  Branch ohne Auftrag: nicht reichen, aber sichtbar
    pruefe("Branch ohne offenen Auftrag",
           lambda: paare(["13"], ["main", "issue-9-alt"]), [])
    pruefe("und er wird gemeldet",
           lambda: meldet(["13"], ["main", "issue-9-alt"], "ohne offenen Auftrag"), True)

    #  Schemaverstoss: nicht zugeordnet, aber gemeldet
    pruefe("fremdes Schema nicht zugeordnet",
           lambda: paare(["7"], ["main", "fix-7-irgendwas"]), [])
    pruefe("und gemeldet",
           lambda: meldet(["7"], ["main", "fix-7-irgendwas"], "ausserhalb des Schemas"),
           True)

    #  Zwei Branches zu einem Vorgang: dieser faellt raus, andere bleiben
    pruefe("mehrdeutiger faellt raus, anderer bleibt",
           lambda: paare(["7", "13"], ["issue-7-a", "issue-7-b", "issue-13-x"]),
           [(13, "issue-13-x")])
    pruefe("Mehrdeutigkeit wird gemeldet",
           lambda: meldet(["7"], ["issue-7-a", "issue-7-b"], "Mehrere Branches"), True)

    #  --- Wahl des Vorgangs, mit dem der Lauf anfaengt -----------------------
    #  Der Branch muss stehen, BEVOR das Modell startet. Raet der Runner den
    #  Namen anders als beim naechsten Mal, findet der Folgelauf nichts wieder.

    K = [(31, "2026-09-10T08:00:00Z", "Nutzer auf fehlerhafte Bezuege hinweisen"),
         (30, "2026-09-11T08:00:00Z", "Einrichten repariert nicht")]

    pruefe("angefangenes schlaegt neues",
           lambda: waehle_vorgang([(7, "issue-7-alt")], K), (7, "issue-7-alt"))
    pruefe("ohne angefangenes das aelteste",
           lambda: waehle_vorgang([], K),
           (31, "issue-31-nutzer-auf-fehlerhafte-bezuege-hinweisen"))
    pruefe("gar nichts", lambda: waehle_vorgang([], []), (None, None))

    #  Bei gleichem Zeitstempel muessen zwei Laeufe dasselbe waehlen.
    pruefe("Gleichstand nach Nummer",
           lambda: waehle_vorgang([], [(9, "T", "b"), (4, "T", "a")])[0], 4)

    #  Der Slug MUSS das Schema erfuellen, sonst ist der Branch unauffindbar.
    for titel in ["Umlaute: äöüÄÖÜß",
                  "  ---  ", "", "Klammern (und) /Schraegstriche/",
                  "中文 nur fremd", "Punkt.am.Ende."]:
        b = waehle_vorgang([], [(5, "T", titel)])[1]
        if not SCHEMA.match(b):
            fehler.append("Slug verletzt SCHEMA bei %r: %r" % (titel, b))

    pruefe("Umlaute werden umschrieben",
           lambda: slug("Bezüge ändern"), "bezuege-aendern")
    pruefe("Slug wird nicht zu lang",
           lambda: len(slug("x" * 200)) <= SLUG_LAENGE, True)
    pruefe("leerer Titel ergibt nicht den leeren Slug",
           lambda: slug("!!!"), "vorgang")

    #  Einlesen der Kandidaten: Tabulatoren, Muell, Titel mit Tabulator
    import tempfile
    d = tempfile.mkdtemp()
    kp = os.path.join(d, "k.txt")
    io.open(kp, "w", encoding="utf-8", newline="").write(
        "31" + chr(9) + "2026-01-01" + chr(9) + "Ein" + chr(9) + "Titel" + chr(10) +
        "Muell ohne Nummer" + chr(10) +
        "7" + chr(9) + "2026-02-02" + chr(9) + "Zwei" + chr(10))
    pruefe("Kandidaten einlesen", lambda: lies_kandidaten(kp),
           [(31, "2026-01-01", "Ein" + chr(9) + "Titel"), (7, "2026-02-02", "Zwei")])
    pruefe("fehlende Datei", lambda: lies_kandidaten(os.path.join(d, "nix")), [])

    #  Leere Eingaben duerfen nicht abstuerzen
    pruefe("gar nichts", lambda: paare([], []), [])

    for f in fehler:
        print("FEHLER: " + f)
    gesamt = 23
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(selbsttest() if "--selbsttest" in sys.argv else main())
