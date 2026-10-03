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
    Als Artefakt "pruefsumme-<nr>" des Waechter-Laufs, nicht in einem Kommentar:
    Eine Pruefsumme ist ein Sicherheitsmerkmal, ein Kommentar waere fuer jeden
    mit Lesezugriff einsehbar (f-reiser/reiser-flow#23, Ruecksprache vom
    20.09.2026). Der Actions-Cache schied aus: Seit dem 26.06.2026 ist er fuer
    "issues", "issue_comment" und "pull_request_target" schreibgeschuetzt, der
    Waechter laeuft aber genau auf diesen Ausloesern (#84).

    Ein Fork-PR darf Artefakte gleichen Namens hochladen. Gilt deshalb nur, was
    ein Lauf mit dem Ausloeser des Waechters hochgeladen hat - dessen Workflow
    kommt immer aus dem Standard-Branch (waehle_artefakt).
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile

#  Name der Datei im Artefakt; label-waechter.yml laedt genau diese hoch.
ARTEFAKT_DATEI = "pruefsumme-schreiben.txt"
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


def summe_aus_text(inhalt):
    """Die Pruefsumme aus dem abgelegten Text, sonst None - ist sie kein
    sha256-Hex, ist das gleichbedeutend mit "keine Pruefsumme abgelegt"."""
    m = SUMME_ZEILE.match((inhalt or "").strip())
    return m.group(1) if m else None


def summe_aus_zip(daten):
    """Die Pruefsumme aus dem heruntergeladenen Artefakt (ein Zip mit genau
    der Datei, die label-waechter.yml hochlaedt), sonst None."""
    try:
        with zipfile.ZipFile(io.BytesIO(daten)) as z:
            return summe_aus_text(z.read(ARTEFAKT_DATEI).decode("utf-8"))
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError):
        return None


#  Ausloeser, bei denen der Waechter eine Summe ablegt: ein Auftragslabel
#  wird gesetzt ("labeled" gibt es nur bei diesen beiden).
WAECHTER_AUSLOESER = ("issues", "pull_request_target")


def waehle_artefakt(artefakte, event_von):
    """Das juengste unabgelaufene Artefakt, das ein Waechter-Lauf hochgeladen
    hat, sonst None. event_von(lauf_id) liefert den Ausloeser des Laufs oder
    None."""
    for art in sorted(artefakte, key=lambda a: a.get("created_at") or "",
                      reverse=True):
        if art.get("expired"):
            continue
        if event_von((art.get("workflow_run") or {}).get("id")) in WAECHTER_AUSLOESER:
            return art
    return None


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


def artefakt_summe(repo, nr):
    """Die vom Waechter abgelegte Summe zu #nr, sonst None."""
    antwort = json.loads(_gh("api", "-X", "GET",
                             "repos/%s/actions/artifacts" % repo,
                             "-f", "name=pruefsumme-%s" % nr,
                             "-f", "per_page=100"))
    events = {}

    def event_von(lauf_id):
        if lauf_id not in events:
            try:
                events[lauf_id] = json.loads(_gh(
                    "api", "repos/%s/actions/runs/%s" % (repo, lauf_id))).get("event")
            except RuntimeError:
                events[lauf_id] = None
        return events[lauf_id]

    art = waehle_artefakt(antwort.get("artifacts") or [], event_von)
    if art is None:
        return None
    lauf = subprocess.run(["gh", "api", "repos/%s/actions/artifacts/%s/zip"
                           % (repo, art["id"])], capture_output=True)
    return summe_aus_zip(lauf.stdout) if lauf.returncode == 0 else None


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
    Schritt danach laedt sie als Artefakt hoch (label-waechter.yml)."""
    titel, body, kommentare = hole(repo, nr)
    summe = pruefsumme(relevanter_text(titel, body, kommentare))
    with io.open(ausgabe_pfad, "w", encoding="utf-8", newline="") as f:
        f.write(summe + chr(10))
    print("Pruefsumme %s fuer #%s nach %s geschrieben." % (summe[:12], nr, ausgabe_pfad))
    return 0


def pruefen(repo, nummern, ziel, summe_von=artefakt_summe):
    """Vergleicht je Vorgang und legt den geprueften Text ab. Gibt die Liste
    der Beanstandungen zurueck - leer heisst: alles stimmt."""
    befunde = []
    for nr in nummern:
        titel, body, kommentare = hole(repo, nr)
        ist = pruefsumme(relevanter_text(titel, body, kommentare))
        soll = summe_von(repo, nr)
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


def lies_nummern(pfad):
    """Die Vorgangsnummern aus einer Datei mit einer Nummer je Zeile."""
    if not os.path.isfile(pfad):
        return []
    return [z.strip() for z in io.open(pfad, encoding="utf-8") if z.strip()]


def main():
    repo = os.environ["REPO"]
    if "--schreiben" in sys.argv:
        return schreiben(repo, os.environ["NR"], os.environ["AUSGABE"])

    kandidaten = lies_nummern("kandidaten-pruefsumme.txt")
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

    gesamt = [0]

    def pruefe(name, ist, soll):
        gesamt[0] += 1
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

    #  --- Summe aus dem Text ----------------------------------------------
    pruefe("Summe aus dem Text", summe_aus_text("a" * 64 + chr(10)), "a" * 64)
    pruefe("leerer Text -> keine Summe", summe_aus_text(""), None)
    pruefe("kein Hex-Digest -> keine Summe", summe_aus_text("kein-sha256"), None)
    pruefe("None -> keine Summe", summe_aus_text(None), None)

    import tempfile as _tempfile
    sha = "a" * 64

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

    #  --- Artefakt waehlen (#84) ------------------------------------------
    #  Der Cache ist fuer "issues"/"issue_comment" seit 26.06.2026 schreibgeschuetzt;
    #  die Summe liegt deshalb als Artefakt des Waechter-Laufs.
    def art(i, wann, lauf, abgelaufen=False):
        return {"id": i, "created_at": wann, "expired": abgelaufen,
                "workflow_run": {"id": lauf}}

    events = {1: "issues", 2: "issues", 3: "pull_request", 4: "pull_request_target",
              5: "issue_comment"}
    ev = events.get
    alt, neu_ = art(10, "2026-10-01T10:00:00Z", 1), art(11, "2026-10-02T10:00:00Z", 2)
    pruefe("juengstes Artefakt gewinnt", (waehle_artefakt([alt, neu_], ev) or {}).get("id"), 11)
    pruefe("Reihenfolge der Liste egal", (waehle_artefakt([neu_, alt], ev) or {}).get("id"), 11)
    pruefe("abgelaufenes zaehlt nicht",
           (waehle_artefakt([alt, art(12, "2026-10-03T10:00:00Z", 2, True)], ev) or {}).get("id"), 10)
    #  Ein Fork-PR darf Artefakte gleichen Namens hochladen - sein Lauf hat aber
    #  den Ausloeser "pull_request", nie "issues".
    pruefe("Artefakt aus fremdem Ausloeser wird uebergangen",
           (waehle_artefakt([alt, art(13, "2026-10-04T10:00:00Z", 3)], ev) or {}).get("id"), 10)
    pruefe("pull_request_target ist ein Waechter-Ausloeser",
           (waehle_artefakt([art(14, "2026-10-04T10:00:00Z", 4)], ev) or {}).get("id"), 14)
    pruefe("issue_comment legt keine Summe ab",
           waehle_artefakt([art(15, "2026-10-04T10:00:00Z", 5)], ev), None)
    pruefe("unbekannter Lauf -> keine Summe",
           waehle_artefakt([art(16, "2026-10-04T10:00:00Z", 99)], ev), None)
    pruefe("keine Artefakte -> keine Summe", waehle_artefakt([], ev), None)

    #  --- Summe aus dem heruntergeladenen Artefakt -------------------------
    import zipfile as _zipfile
    def zip_mit(name, inhalt):
        puffer = io.BytesIO()
        with _zipfile.ZipFile(puffer, "w") as z:
            z.writestr(name, inhalt)
        return puffer.getvalue()
    pruefe("Summe aus dem Zip",
           summe_aus_zip(zip_mit("pruefsumme-schreiben.txt", sha + chr(10))), sha)
    pruefe("Zip mit Muell -> keine Summe",
           summe_aus_zip(zip_mit("pruefsumme-schreiben.txt", "kein-sha256")), None)
    pruefe("Zip ohne die erwartete Datei -> keine Summe",
           summe_aus_zip(zip_mit("etwas-anderes.txt", sha)), None)
    pruefe("kein Zip -> keine Summe", summe_aus_zip(b"das ist kein zip"), None)

    #  --- Kandidaten: nur noch Nummern -------------------------------------
    with _tempfile.TemporaryDirectory() as td:
        pfad = os.path.join(td, "kandidaten-pruefsumme.txt")
        io.open(pfad, "w", encoding="utf-8", newline="").write("31" + chr(10) + chr(10) + "7" + chr(10))
        pruefe("Nummern eingelesen", lies_nummern(pfad), ["31", "7"])
        pruefe("fehlende Datei -> keine Nummern", lies_nummern(os.path.join(td, "nix.txt")), [])

    #  --- die Verdrahtung: kein Cache-Schreiben mehr im Waechter -----------
    def ohne_kommentare(text):
        return chr(10).join(z for z in text.split(chr(10)) if not z.lstrip().startswith("#"))
    for datei, verboten, noetig in [("label-waechter.yml", "actions/cache/save", "actions/upload-artifact"),
                                    ("claude-aufgaben.yml", "actions/cache/restore", None)]:
        pfad = os.path.join(WURZEL, "workflows", datei)
        try:
            t = ohne_kommentare(io.open(pfad, encoding="utf-8").read())
        except OSError as e:
            fehler.append("%s nicht lesbar: %s" % (datei, e))
            continue
        if verboten in t:
            fehler.append("%s nutzt noch %s" % (datei, verboten))
        if noetig and noetig not in t:
            fehler.append("%s nutzt %s nicht" % (datei, noetig))

    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt[0] - len(fehler), gesamt[0]))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(selbsttest() if "--selbsttest" in sys.argv else main())
