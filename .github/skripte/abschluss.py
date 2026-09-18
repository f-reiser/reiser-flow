#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Der Abschlusskommentar eines unbeaufsichtigten Laufs: Skills, Tokens, Dauer.

Diese Angaben standen bisher in der Job-Summary und im Log. Dort findet sie
niemand - man muesste wissen, dass es sie gibt, und im Actions-Verlauf danach
suchen. Sie gehoeren an den Vorgang, an dem gearbeitet wurde: dort schaut hin,
wer wissen will, was der Lauf getan und gekostet hat.

Getrennt vom Fortschrittskommentar (fortschritt.py), und zwar absichtlich: Der
eine ist ein Stand, der fortgeschrieben und gekuerzt wird; dieser hier ist eine
Abrechnung, die stehen bleibt. In einem Text gemischt waere beides schlechter
lesbar.

Gelesen wird die Ausfuehrungsdatei der Action (Output "execution_file"). Deren
Aufbau ist nicht zugesagt - deshalb sucht dieses Skript tolerant und schreibt
"nicht ermittelbar" statt zu raten oder abzubrechen. Eine fehlende Zahl ist
aergerlich; eine erfundene waere schlimmer, und ein Abbruch verloere auch die
Angaben, die da sind.
"""
import io
import json
import os
import subprocess
import tempfile
import sys

#  Nur Felder, die die Ergebnismeldung des CLI wirklich fuehrt
#  (--output-format json: result, session_id, usage, total_cost_usd, Dauer, Runden).
TOKENFELDER = [
    ("input_tokens", "Eingabe"),
    ("output_tokens", "Ausgabe"),
    ("cache_creation_input_tokens", "Cache angelegt"),
    ("cache_read_input_tokens", "Cache gelesen"),
]


def ergebnismeldung(text):
    """Die letzte Meldung mit type == result - egal, wie die Datei aufgebaut ist.

    Drei Formen sind denkbar: ein einzelnes Objekt, ein Array von Meldungen, oder
    eine Meldung je Zeile. Welche die Action schreibt, ist nirgends zugesagt,
    also werden alle drei gelesen.
    """
    text = (text or "").strip()
    if not text:
        return None

    def aus(wert):
        if isinstance(wert, dict):
            return [wert]
        if isinstance(wert, list):
            return [x for x in wert if isinstance(x, dict)]
        return []

    kandidaten = []
    try:
        kandidaten = aus(json.loads(text))
    except ValueError:
        for zeile in text.splitlines():
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                kandidaten += aus(json.loads(zeile))
            except ValueError:
                continue

    treffer = [k for k in kandidaten if k.get("type") == "result"]
    if treffer:
        return treffer[-1]
    #  Ohne "type": ein einzelnes Objekt aus --output-format json traegt die
    #  Felder direkt. An usage, total_cost_usd oder duration_ms zu erkennen.
    for k in reversed(kandidaten):
        if "usage" in k or "total_cost_usd" in k or "duration_ms" in k:
            return k
    return None


def dauer(ms):
    """Millisekunden als "12 min 34 s" - blanke Sekunden liest niemand gern."""
    if not isinstance(ms, (int, float)) or isinstance(ms, bool) or ms < 0:
        return None
    s = int(round(ms / 1000.0))
    return "%d min %d s" % (s // 60, s % 60) if s >= 60 else "%d s" % s


def zahl(n):
    """Tausenderpunkte - 1234567 sagt weniger als 1.234.567."""
    if not isinstance(n, (int, float)) or isinstance(n, bool):
        return None
    return "{:,}".format(int(n)).replace(",", ".")


def zeilen(meldung, skills, ergebnis, bemerkung, lauf_url, wanduhr_s=None):
    """Der Text des Abschlusskommentars als Liste von Zeilen."""
    z = ["## Abschluss des Laufs", ""]
    z.append("Ergebnis: **%s**" % (ergebnis or "unbekannt"))
    if bemerkung:
        z += ["", bemerkung]
    z.append("")

    z.append("### Skills")
    if skills:
        z += ["- `%s`" % s for s in skills]
    else:
        #  Keine gemeldeten Skills ist ein Befund, kein Formatierungsproblem:
        #  Der Lauf soll ohne sie nicht arbeiten.
        z.append("**Keine gemeldet.** Der Lauf soll nicht ohne sie arbeiten - "
                 "siehe Schritt `Skills nachweisen`.")
    z.append("")

    z.append("### Verbrauch")
    m = meldung or {}
    verbrauch = m.get("usage") or {}
    tabelle = []
    summe = 0
    for feld, name in TOKENFELDER:
        wert = verbrauch.get(feld)
        formatiert = zahl(wert)
        if formatiert:
            tabelle.append((name, formatiert))
            summe += int(wert)
    if tabelle:
        tabelle.append(("**Summe**", "**%s**" % zahl(summe)))
        z += ["| Tokens | Anzahl |", "|---|---:|"]
        z += ["| %s | %s |" % kv for kv in tabelle]
    else:
        z.append("Tokens: nicht ermittelbar.")
    z.append("")

    d = dauer(m.get("duration_ms"))
    api = dauer(m.get("duration_api_ms"))
    angaben = []
    if d:
        angaben.append("Dauer der claude-API: **%s**" % d)
    elif wanduhr_s is not None:
        #  Ersatzmass, falls die Ausfuehrungsdatei keine Dauer fuehrt: die Zeit,
        #  die der Runner selbst gemessen hat. Ausdruecklich benannt, damit sie
        #  niemand fuer die API-Zeit haelt - sie ist groesser.
        angaben.append("Dauer des Schritts (Uhr des Runners, nicht der API): "
                       "**%s**" % dauer(wanduhr_s * 1000))
    else:
        angaben.append("Dauer: nicht ermittelbar.")
    if api and d:
        angaben.append("davon Wartezeit auf die API: %s" % api)
    if isinstance(m.get("num_turns"), int):
        angaben.append("Runden: %d" % m["num_turns"])
    if isinstance(m.get("total_cost_usd"), (int, float)):
        #  Schaetzung des CLI, nicht die Abrechnung - so steht es auch dort.
        angaben.append("Geschaetzte Kosten: %.2f USD (Schaetzung des CLI)"
                       % m["total_cost_usd"])
    z += ["- " + a for a in angaben]

    verweigert = m.get("permission_denials")
    if verweigert:
        z += ["", "### Verweigerte Werkzeuge",
              "Der Lauf wollte %d Aufruf(e) machen, die die Sperrliste des "
              "Workflows nicht erlaubt." % len(verweigert)]

    z += ["", "[Lauf im Actions-Verlauf](%s)" % lauf_url]
    return z


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    nr = os.environ.get("VORGANG", "").strip()
    if not nr:
        print("Kein Vorgang - kein Abschlusskommentar.")
        return 0

    roh = ""
    pfad = os.environ.get("AUSFUEHRUNGSDATEI", "").strip()
    if pfad and os.path.isfile(pfad):
        roh = io.open(pfad, encoding="utf-8", errors="replace").read()
    else:
        print("::warning::Ausfuehrungsdatei nicht gefunden (%r) - der Verbrauch "
              "fehlt im Abschlusskommentar." % pfad)

    skills = []
    ergebnis = os.environ.get("AUSGANG")
    bemerkung = ""
    try:
        d = json.loads(os.environ.get("SCHLUSSMELDUNG") or "{}")
        skills = [str(s) for s in (d.get("skills") or [])]
        ergebnis = d.get("ergebnis") or ergebnis
        bemerkung = d.get("bemerkung") or ""
    except ValueError:
        print("::warning::Schlussmeldung ist kein gueltiges JSON.")

    wanduhr = os.environ.get("WANDUHR_S", "").strip()
    text = chr(10).join(zeilen(
        ergebnismeldung(roh), skills, ergebnis, bemerkung,
        "%s/%s/actions/runs/%s" % (os.environ.get("GITHUB_SERVER_URL", ""),
                                   repo, os.environ.get("GITHUB_RUN_ID", "")),
        int(wanduhr) if wanduhr.isdigit() else None))

    #  Ausserhalb des Arbeitsverzeichnisses, damit der Rettungsschritt des
    #  Workflows die Datei nicht mitcommittet.
    f = tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8",
                                    newline="", delete=False)
    with f:
        json.dump({"body": text}, f)
    try:
        subprocess.run(["gh", "api", "--method", "POST",
                        "repos/%s/issues/%s/comments" % (repo, nr),
                        "--input", f.name], check=True)
    finally:
        os.unlink(f.name)
    print(text)
    return 0


def selbsttest():
    """Die drei Stellen, an denen dieses Skript falsch liegen kann.

    Es liest eine Datei, deren Aufbau nicht zugesagt ist. Wenn es dabei etwas
    nicht findet, MUSS "nicht ermittelbar" dastehen - eine erfundene Zahl waere
    schlimmer als gar keine, und ein Abbruch verloere auch das, was da ist.
    """
    fehler = []
    NL = chr(10)

    def gleich(name, ist, soll):
        if ist != soll:
            fehler.append("%s: %r statt %r" % (name, ist, soll))

    def enthaelt(name, text, teil):
        if teil not in text:
            fehler.append("%s: %r fehlt in %r" % (name, teil, text[:200]))

    def fehlt_nicht(name, text, teil):
        if teil in text:
            fehler.append("%s: %r steht faelschlich in %r" % (name, teil, text[:200]))

    fertig = {"type": "result", "duration_ms": 754000, "duration_api_ms": 600000,
              "num_turns": 42, "total_cost_usd": 1.2345,
              "usage": {"input_tokens": 12000, "output_tokens": 3400,
                        "cache_read_input_tokens": 1234567}}

    #  --- Die Datei finden, in jeder der drei denkbaren Formen ---
    gleich("einzelnes Objekt", ergebnismeldung(json.dumps(fertig)), fertig)
    gleich("Array", ergebnismeldung(json.dumps([{"type": "system"}, fertig])), fertig)
    gleich("eine Meldung je Zeile",
           ergebnismeldung(json.dumps({"type": "system"}) + NL + json.dumps(fertig)),
           fertig)
    #  Mehrere Ergebnisse: das letzte gilt.
    gleich("das letzte Ergebnis gilt",
           ergebnismeldung(json.dumps([dict(fertig, num_turns=1), fertig])), fertig)
    #  Objekt ohne "type", wie --output-format json es liefert.
    ohne = {"usage": {"input_tokens": 5}, "session_id": "x"}
    gleich("ohne type an usage erkannt", ergebnismeldung(json.dumps(ohne)), ohne)

    #  --- Und wenn nicht: None, kein Absturz, keine Ausnahme ---
    for name, roh in [("leer", ""), ("nur Leerraum", "   " + NL),
                      ("kaputtes JSON", "{nicht json"),
                      ("JSON ohne Kennzeichen", json.dumps({"a": 1})),
                      ("Liste aus Zahlen", json.dumps([1, 2, 3]))]:
        gleich("keine Meldung bei " + name, ergebnismeldung(roh), None)

    #  --- Formatierung ---
    gleich("Dauer unter einer Minute", dauer(45000), "45 s")
    gleich("Dauer darueber", dauer(754000), "12 min 34 s")
    gleich("Dauer null", dauer(0), "0 s")
    gleich("Dauer fehlt", dauer(None), None)
    gleich("Dauer als Text", dauer("viel"), None)
    gleich("Tausenderpunkte", zahl(1234567), "1.234.567")
    gleich("Null ist eine Zahl", zahl(0), "0")
    gleich("keine Zahl", zahl(None), None)
    #  True ist in Python eine Zahl - hier waere "1" aber sicher falsch.
    gleich("Wahrheitswert ist keine Zahl", zahl(True), None)

    #  --- Der fertige Text ---
    voll = NL.join(zeilen(fertig, ["a", "b"], "abgearbeitet", "", "http://l"))
    enthaelt("Summe der Tokens", voll, "**1.249.967**")
    enthaelt("Dauer", voll, "12 min 34 s")
    enthaelt("Runden", voll, "Runden: 42")
    enthaelt("Kosten", voll, "1.23 USD")
    enthaelt("Skills", voll, "- `a`")
    fehlt_nicht("keine Luecke", voll, "nicht ermittelbar")
    #  Ein Feld, das die Meldung nicht fuehrt, darf keine Zeile erzeugen.
    fehlt_nicht("kein leeres Cache-Feld", voll, "Cache angelegt")

    #  Ohne Ausfuehrungsdatei: der Kommentar entsteht trotzdem und sagt es.
    leer = NL.join(zeilen(None, [], None, "", "http://l"))
    enthaelt("Tokens fehlen", leer, "Tokens: nicht ermittelbar")
    enthaelt("Dauer fehlt", leer, "Dauer: nicht ermittelbar")
    enthaelt("Ergebnis unbekannt", leer, "unbekannt")
    enthaelt("fehlende Skills sind ein Befund", leer, "Keine gemeldet")

    #  Ersatzmass nur, wenn die echte Dauer fehlt - und benannt als Ersatzmass.
    ersatz = NL.join(zeilen(None, [], None, "", "http://l", wanduhr_s=90))
    enthaelt("Wanduhr springt ein", ersatz, "Uhr des Runners")
    enthaelt("und rechnet richtig", ersatz, "1 min 30 s")
    echt = NL.join(zeilen(fertig, [], None, "", "http://l", wanduhr_s=90))
    fehlt_nicht("Wanduhr weicht der echten Dauer", echt, "Uhr des Runners")

    gesamt = 32
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


if __name__ == "__main__":
    if "--selbsttest" in sys.argv:
        sys.exit(selbsttest())
    sys.exit(main())
