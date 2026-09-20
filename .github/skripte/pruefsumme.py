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
    Im Actions-Cache des Repositories, nicht in einem Kommentar: Eine
    Pruefsumme ist ein Sicherheitsmerkmal, ein Kommentar waere fuer jeden mit
    Lesezugriff einsehbar (f-reiser/reiser-flow#23, Ruecksprache vom
    20.09.2026). label-waechter.yml legt sie beim Setzen des Auftragslabels
    unter einem Schluessel ab, der die Vorgangsnummer traegt; claude-aufgaben.yml
    holt sie sich per "restore-keys:"-Praefix zurueck - das Ablegen und
    Restaurieren selbst ist Sache der Workflow-Datei (actions/cache), dieses
    Skript sieht nur die lokale Datei, die dabei entsteht bzw. gebraucht wird.
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

TRENNER = chr(10) + "----8<----" + chr(10)
SUMME_ZEILE = re.compile(r"^([0-9a-f]{64})\s*$")


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


def gelesene_summe(pfad):
    """Die im Actions-Cache abgelegte Pruefsumme aus der restaurierten Datei,
    sonst None - fehlt sie (kein Cache-Treffer) oder ist sie kein sha256-Hex,
    ist das gleichbedeutend mit "keine Pruefsumme abgelegt"."""
    if not pfad or not os.path.isfile(pfad):
        return None
    inhalt = io.open(pfad, encoding="utf-8").read()
    m = SUMME_ZEILE.match(inhalt.strip())
    return m.group(1) if m else None


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


def schreiben(repo, nr, ausgabe_pfad):
    """Schreibt die aktuelle Pruefsumme in eine lokale Datei - der Workflow-
    Schritt danach legt sie in den Actions-Cache (label-waechter.yml)."""
    titel, body, kommentare = hole(repo, nr)
    summe = pruefsumme(relevanter_text(titel, body, kommentare))
    with io.open(ausgabe_pfad, "w", encoding="utf-8", newline="") as f:
        f.write(summe + chr(10))
    print("Pruefsumme %s fuer #%s nach %s geschrieben." % (summe[:12], nr, ausgabe_pfad))
    return 0


def pruefen(repo, kandidaten, ziel):
    """kandidaten: [(nr, restore_pfad), ...] - restore_pfad ist die Datei, die
    ein vorangehender "actions/cache/restore"-Schritt fuer diese Nummer
    angelegt hat, oder ein nicht existierender Pfad ohne Cache-Treffer.

    Vergleicht je Vorgang und legt den geprueften Text ab. Gibt die Liste der
    Beanstandungen zurueck - leer heisst: alles stimmt."""
    befunde = []
    for nr, restore_pfad in kandidaten:
        titel, body, kommentare = hole(repo, nr)
        ist = pruefsumme(relevanter_text(titel, body, kommentare))
        soll = gelesene_summe(restore_pfad)
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


def lies_kandidaten_pruefsumme(pfad):
    """[(nr, restore_pfad), ...] aus "<nr>\\t<restore_pfad>"-Zeilen."""
    if not os.path.isfile(pfad):
        return []
    ergebnis = []
    for zeile in io.open(pfad, encoding="utf-8"):
        zeile = zeile.rstrip(chr(10)).rstrip(chr(13))
        if not zeile.strip():
            continue
        nr, _, rest = zeile.partition(chr(9))
        ergebnis.append((nr.strip(), rest.strip()))
    return ergebnis


def main():
    repo = os.environ["REPO"]
    if "--schreiben" in sys.argv:
        return schreiben(repo, os.environ["NR"], os.environ["AUSGABE"])

    kandidaten = lies_kandidaten_pruefsumme("kandidaten-pruefsumme.txt")
    befunde = pruefen(repo, kandidaten, os.environ.get("RUNNER_TEMP", "."))
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

    #  --- gelesene Summe (aus der restaurierten Cache-Datei) --------------
    import tempfile as _tempfile
    sha = "a" * 64
    with _tempfile.TemporaryDirectory() as td:
        vorhanden = os.path.join(td, "vorhanden.txt")
        io.open(vorhanden, "w", encoding="utf-8", newline="").write(sha + chr(10))
        pruefe("Summe aus der restaurierten Datei", gelesene_summe(vorhanden), sha)

        leer = os.path.join(td, "leer.txt")
        io.open(leer, "w", encoding="utf-8").write("")
        pruefe("leere Datei -> keine Summe", gelesene_summe(leer), None)

        muell = os.path.join(td, "muell.txt")
        io.open(muell, "w", encoding="utf-8").write("kein-sha256")
        pruefe("kein Hex-Digest -> keine Summe", gelesene_summe(muell), None)

        pruefe("fehlende Datei -> keine Summe (kein Cache-Treffer)",
               gelesene_summe(os.path.join(td, "gibtsnicht.txt")), None)
        pruefe("leerer Pfad -> keine Summe", gelesene_summe(""), None)
        pruefe("None -> keine Summe", gelesene_summe(None), None)

    #  --- lies_kandidaten_pruefsumme() -------------------------------------
    with _tempfile.TemporaryDirectory() as td:
        pfad = os.path.join(td, "kandidaten-pruefsumme.txt")
        io.open(pfad, "w", encoding="utf-8", newline="").write(
            "31" + chr(9) + "/tmp/a.txt" + chr(10)
            + chr(10)
            + "7" + chr(9) + "/tmp/b.txt" + chr(10))
        pruefe("Kandidaten eingelesen", lies_kandidaten_pruefsumme(pfad),
               [("31", "/tmp/a.txt"), ("7", "/tmp/b.txt")])
        pruefe("fehlende Datei -> leere Liste",
               lies_kandidaten_pruefsumme(os.path.join(td, "nix.txt")), [])

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

    gesamt = 27
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(selbsttest() if "--selbsttest" in sys.argv else main())
