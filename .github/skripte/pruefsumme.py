#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Haelt fest, wie ein Vorgang aussah, als sein Auftragslabel gesetzt wurde -
und prueft vor dem teuren Lauf, ob er noch so aussieht
(f-reiser/reiser-flow#23).

WOZU
    Ein Berechtigter labelt einen Vorgang zu EINEM Zeitpunkt. Gelesen wird er
    bis zu vier Stunden spaeter, und dazwischen darf jeder mit Lesezugriff
    kommentieren - Kommentare schuetzt kein Waechter. Der gepruefte Text und
    der gearbeitete Text waren also nie derselbe.

    Der haeufigere Fall ist gar kein Angriff: Wer in einem Issue fremden Text
    zitiert - eine Fehlermeldung, ein Changelog, einen Gegenlese-Bericht -,
    liefert anweisungsartige Saetze mit, die von der Anforderung nicht zu
    unterscheiden sind.

WIE
    Beim Labeln bildet dieses Skript eine Pruefsumme ueber Titel, Beschreibung
    und die menschlichen Kommentare und legt sie am Vorgang ab. Vor dem Lauf
    bildet es sie erneut und vergleicht. Stimmen sie, steht die Anforderung
    fest; der Lauf bekommt den geprueften Text als Datei durchgereicht und
    liest den Vorgang nicht noch einmal - sonst liesse sich die Luecke
    zwischen Vergleich und Arbeit erneut nutzen.

WARUM BOT-KOMMENTARE NICHT ZAEHLEN
    Der Lauf schreibt selbst an den Vorgang, an dem er arbeitet:
    Fortschritts- und Abschlusskommentar. Zaehlten die mit, waere die
    Pruefsumme nach dem ersten eigenen Kommentar verletzt, und der Folgelauf
    meldete einen Angriff, wo nur sein Vorgaenger gearbeitet hat.

WO DIE PRUEFSUMME LIEGT
    In einem Kommentar am Vorgang selbst, erkennbar an einer Marke - dasselbe
    Muster wie der Fortschrittskommentar (fortschritt.py). Er ueberlebt
    beliebig lange, laesst sich ueberschreiben, braucht keine zusaetzliche
    Berechtigung und ist nachlesbar. Gezaehlt wird nur ein Kommentar eines
    Bots: Wer bloss Lesezugriff hat, kann zwar kommentieren, aber keinen
    Bot-Kommentar erzeugen.
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

MARKE = "<!-- auftrag-pruefsumme -->"
SUMME = re.compile(r"sha256:([0-9a-f]{64})")
TRENNER = chr(10) + "----8<----" + chr(10)


def ist_bot(autor):
    """Ob ein Kommentar- oder Vorgangsautor ein Bot ist (Feld "user")."""
    return ((autor or {}).get("type") or "") == "Bot"


def menschliche(kommentare):
    return [k for k in kommentare if not ist_bot(k.get("user"))]


def relevanter_text(titel, body, kommentare):
    """Der Text, ueber den die Pruefsumme gebildet wird.

    Der Trenner steht zwischen den Teilen, damit sich eine Verschiebung
    zwischen Beschreibung und erstem Kommentar nicht wegkuerzt: Ohne ihn
    ergaeben "ab" + "c" und "a" + "bc" dieselbe Summe.
    """
    teile = [titel or "", body or ""]
    teile += [(k.get("body") or "") for k in menschliche(kommentare)]
    return TRENNER.join(teile)


def pruefsumme(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def abgelegte_summe(kommentare):
    """(id, summe) aus dem letzten Bot-Kommentar mit der Marke, sonst
    (None, None).

    Nur von einem Bot: Einen Kommentar mit derselben Marke darf jeder
    schreiben, der lesen darf - einen Bot-Kommentar nicht.
    """
    treffer = (None, None)
    for k in kommentare:
        if not ist_bot(k.get("user")):
            continue
        text = k.get("body") or ""
        if MARKE not in text:
            continue
        m = SUMME.search(text)
        if m:
            treffer = (k.get("id"), m.group(1))
    return treffer


def kommentartext(summe):
    return (MARKE + chr(10)
            + "`sha256:" + summe + "`" + chr(10) * 2
            + "Stand von Titel, Beschreibung und Kommentaren, als das "
              "Auftragslabel gesetzt wurde. Aendert sich daran etwas, nimmt "
              "der Label-Waechter das Auftragslabel zurueck; der "
              "unbeaufsichtigte Lauf arbeitet nur an einem Vorgang, dessen "
              "Pruefsumme noch stimmt." + chr(10))


def uebergabetext(titel, body, kommentare):
    """Der gepruefte Vorgang fuer den Lauf - mit Autor und Rolle je Beitrag.

    Die Herkunft steht dabei, weil sie ohne Kosten eine Einordnung gibt:
    Wer nur Lesezugriff hat, darf kommentieren und soll das auch - aber der
    Lauf soll sehen, von wem was stammt.
    """
    z = ["# " + (titel or ""), "",
         "## Beschreibung", "", (body or "").strip(), ""]
    for k in menschliche(kommentare):
        wer = (k.get("user") or {}).get("login") or "unbekannt"
        rolle = k.get("author_association") or "NONE"
        z += ["## Kommentar von %s (%s)" % (wer, rolle), "",
              (k.get("body") or "").strip(), ""]
    return chr(10).join(z)


#  ------------------------------------------------------------------- API-Zugriff

def _gh(*args):
    lauf = subprocess.run(["gh"] + list(args), capture_output=True, text=True)
    if lauf.returncode != 0:
        raise RuntimeError("gh %s: %s" % (" ".join(args), lauf.stderr.strip()))
    return lauf.stdout


def hole(repo, nr):
    """(titel, body, kommentare) eines Vorgangs. Ein Pull Request ist in der
    Issues-API dasselbe Objekt wie ein Issue - derselbe Pfad traegt beide."""
    v = json.loads(_gh("api", "repos/%s/issues/%s" % (repo, nr)))
    k = json.loads(_gh("api", "--paginate",
                       "repos/%s/issues/%s/comments" % (repo, nr)) or "[]")
    return v.get("title"), v.get("body"), k


def kommentieren(repo, nr, text, kommentar_id=None):
    f = tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8",
                                    newline="", delete=False)
    with f:
        f.write(text)
    try:
        if kommentar_id:
            _gh("api", "--method", "PATCH",
                "repos/%s/issues/comments/%s" % (repo, kommentar_id),
                "-F", "body=@%s" % f.name)
        else:
            _gh("api", "--method", "POST",
                "repos/%s/issues/%s/comments" % (repo, nr),
                "-F", "body=@%s" % f.name)
    finally:
        os.unlink(f.name)


#  ------------------------------------------------------------------------ main

WARNUNG = (
    "## Pruefsumme des Auftrags stimmt nicht" + chr(10) * 2
    + "Der unbeaufsichtigte Lauf wurde abgebrochen; `claude-code` ist nicht "
      "aufgerufen worden." + chr(10) * 2
    + "%s" + chr(10) * 2
    + "**Das sollte nicht vorkommen.** Der harmlose Grund: Der Label-Waechter "
      "ist abgebrochen oder gar nicht erst gestartet, als dieser Vorgang "
      "zuletzt geaendert wurde - dann haette er das Auftragslabel abnehmen "
      "muessen und hat es nicht getan." + chr(10) * 2
    + "Der andere Grund: Jemand hat den Vorgang nach der Freigabe veraendert "
      "oder die Pruefsumme selbst angefasst. Lies den Vorgang deshalb noch "
      "einmal genau gegen, **bevor** du das Auftragslabel erneut setzt."
      + chr(10))


def schreiben(repo, nr):
    titel, body, kommentare = hole(repo, nr)
    summe = pruefsumme(relevanter_text(titel, body, kommentare))
    alt_id, alt_summe = abgelegte_summe(kommentare)
    if alt_summe == summe:
        print("Pruefsumme unveraendert (#%s)." % nr)
        return 0
    #  Ohne Nachfrage ueberschreiben: Ein Rest aus einem abgebrochenen Lauf
    #  darf den neuen Auftrag nicht aufhalten.
    kommentieren(repo, nr, kommentartext(summe), alt_id)
    print("Pruefsumme %s fuer #%s abgelegt." % (summe[:12], nr))
    return 0


def pruefen(repo, nummern, ziel):
    """Vergleicht je Vorgang und legt den geprueften Text ab. Gibt die Liste
    der Beanstandungen zurueck - leer heisst: alles stimmt."""
    befunde = []
    for nr in nummern:
        titel, body, kommentare = hole(repo, nr)
        ist = pruefsumme(relevanter_text(titel, body, kommentare))
        _, soll = abgelegte_summe(kommentare)
        if soll is None:
            befunde.append((nr, "Es liegt keine Pruefsumme am Vorgang."))
            continue
        if soll != ist:
            befunde.append((nr, "Abgelegt war `%s`, jetzt ergibt sich `%s`."
                            % (soll[:12], ist[:12])))
            continue
        pfad = os.path.join(ziel, "vorgang-%s.md" % nr)
        with io.open(pfad, "w", encoding="utf-8", newline="") as f:
            f.write(uebergabetext(titel, body, kommentare))
        print("#%s geprueft, Text in %s" % (nr, pfad))
    return befunde


def main():
    repo = os.environ["REPO"]
    if "--schreiben" in sys.argv:
        return schreiben(repo, os.environ["NR"])

    nummern = [z.strip() for z in io.open("nummern.txt", encoding="utf-8")
               if z.strip()] if os.path.isfile("nummern.txt") else []
    befunde = pruefen(repo, nummern, os.environ.get("RUNNER_TEMP", "."))
    for nr, grund in befunde:
        print("::error::Pruefsumme von #%s stimmt nicht - %s" % (nr, grund))
        try:
            kommentieren(repo, nr, WARNUNG % grund)
        except RuntimeError as e:
            print("::warning::Warnung an #%s nicht zugestellt: %s" % (nr, e))
    return 1 if befunde else 0


#  Beide Seiten der Zusage: Der Waechter legt die Pruefsumme ab, der Lauf
#  vergleicht sie. Fehlt eine davon, wirkt dieses Skript nicht - und das faellt
#  ohne diese Pruefung nirgends auf (wie in label_sicherheitsnetz.py).
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = {
    "label-waechter.yml": "--schreiben",
    "claude-aufgaben.yml": "pruefsumme.py",
}


def ruft_auf(text, was):
    """Ob der Workflow-Text den Aufruf enthaelt - ohne Kommentarzeilen, die
    ihn nur erklaeren."""
    t = chr(10).join(z for z in text.split(chr(10))
                     if not z.lstrip().startswith("#"))
    return "pruefsumme.py" in t and was in t


#  --------------------------------------------------------------------- Selbsttest

def _k(body, typ="User", login="wer", id=1):
    return {"id": id, "body": body, "user": {"type": typ, "login": login},
            "author_association": "MEMBER"}


def selbsttest():
    fehler = []

    def pruefe(name, ist, soll):
        if ist != soll:
            fehler.append("%s: %r statt %r" % (name, ist, soll))

    #  --- wer zaehlt mit --------------------------------------------------
    pruefe("Mensch zaehlt", ist_bot({"type": "User"}), False)
    pruefe("Bot zaehlt nicht", ist_bot({"type": "Bot"}), True)
    pruefe("fehlender Autor gilt als Mensch", ist_bot(None), False)

    #  Der Lauf kommentiert den Vorgang, an dem er arbeitet. Ohne diese Regel
    #  waere die Pruefsumme nach dem ersten eigenen Kommentar verletzt.
    mit_bot = [_k("Anforderung"), _k("Fortschritt", typ="Bot")]
    pruefe("Bot-Kommentar aendert den Text nicht",
           relevanter_text("T", "B", mit_bot),
           relevanter_text("T", "B", [_k("Anforderung")]))

    #  --- Pruefsumme ------------------------------------------------------
    a = pruefsumme(relevanter_text("T", "B", [_k("x")]))
    pruefe("gleiche Eingabe, gleiche Summe",
           pruefsumme(relevanter_text("T", "B", [_k("x")])), a)
    for name, args in [("Titel", ("T2", "B", [_k("x")])),
                       ("Beschreibung", ("T", "B2", [_k("x")])),
                       ("Kommentar", ("T", "B", [_k("y")])),
                       ("neuer Kommentar", ("T", "B", [_k("x"), _k("z")])),
                       ("Kommentar geloescht", ("T", "B", []))]:
        if pruefsumme(relevanter_text(*args)) == a:
            fehler.append("%s geaendert, Summe gleich geblieben" % name)

    #  Eine Verschiebung zwischen zwei Teilen darf sich nicht wegkuerzen.
    pruefe("Verschiebung faellt auf",
           pruefsumme(relevanter_text("T", "ab", [_k("c")]))
           == pruefsumme(relevanter_text("T", "a", [_k("bc")])), False)

    #  --- abgelegte Summe -------------------------------------------------
    sha = "a" * 64
    echt = _k(MARKE + chr(10) + "`sha256:" + sha + "`", typ="Bot", id=7)
    pruefe("Summe aus dem Bot-Kommentar", abgelegte_summe([echt]), (7, sha))
    pruefe("keine Marke, keine Summe", abgelegte_summe([_k("egal")]),
           (None, None))
    #  Genau der Weg, auf dem sich sonst eine fremde Summe unterschieben
    #  liesse: Kommentieren darf jeder mit Lesezugriff.
    gefaelscht = _k(MARKE + chr(10) + "`sha256:" + "b" * 64 + "`", id=8)
    pruefe("Mensch kann keine Summe ablegen", abgelegte_summe([gefaelscht]),
           (None, None))
    pruefe("bei mehreren gilt die letzte",
           abgelegte_summe([echt, _k(MARKE + " `sha256:" + "c" * 64 + "`",
                                     typ="Bot", id=9)]),
           (9, "c" * 64))
    #  Was das Skript selbst schreibt, muss es auch wieder lesen koennen.
    pruefe("eigener Kommentar ist lesbar",
           abgelegte_summe([_k(kommentartext(sha), typ="Bot", id=3)]),
           (3, sha))

    #  --- Uebergabetext ---------------------------------------------------
    ue = uebergabetext("Titel", "Body", [_k("Hallo", login="florian"),
                                         _k("Bot", typ="Bot")])
    for teil in ("# Titel", "Body", "Kommentar von florian (MEMBER)", "Hallo"):
        if teil not in ue:
            fehler.append("Uebergabetext ohne %r" % teil)
    if "Bot" in ue.replace("Body", ""):
        fehler.append("Uebergabetext enthaelt den Bot-Kommentar")

    #  --- die Verdrahtung -------------------------------------------------
    for datei, was in sorted(WORKFLOWS.items()):
        pfad = os.path.join(WURZEL, "workflows", datei)
        try:
            yml = io.open(pfad, encoding="utf-8").read()
        except OSError as e:
            fehler.append("%s nicht lesbar: %s" % (datei, e))
            continue
        if not ruft_auf(yml, was):
            fehler.append("%s ruft pruefsumme.py nicht auf (%r fehlt)"
                          % (datei, was))
    pruefe("Kommentarzeile zaehlt nicht als Aufruf",
           ruft_auf("#  pruefsumme.py --schreiben", "--schreiben"), False)

    gesamt = 3 + 1 + 1 + 5 + 1 + 5 + 4 + 1 + 3
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(selbsttest() if "--selbsttest" in sys.argv else main())
