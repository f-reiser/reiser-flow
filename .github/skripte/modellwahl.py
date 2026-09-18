#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bestimmt aus den Labels der offenen Vorgaenge, mit welchem Modell und welchem
Aufwand der naechste unbeaufsichtigte Lauf arbeitet.

Liest eine Datei, die der Workflow-Schritt vorher erzeugt hat:
    labels.txt   je Zeile ein Vorgang: "<nr>\t<label>,<label>,..."

Schreibt nach GITHUB_OUTPUT:
    modell      Wert fuer "claude_args: --model"
    aufwand     Wert fuer "claude_args: --effort"
    warnungen   leer oder Text, den der Workflow als ::warning ausgibt

WARUM DAS HIER STEHT UND NICHT IM PROMPT
    "--model" und "--effort" muessen feststehen, BEVOR das Modell startet - ein Lauf
    kann sein eigenes Modell nicht mehr waehlen. Die Wahl ist damit zwangslaeufig
    Sache des Runners, und sie ist es auch inhaltlich gern: Sie folgt festen Regeln,
    kostet hier nichts und kann nicht anders ausgehen.
"""
import io
import os
import sys

import scoped_labels

#  Die Aufwandsstufen der CLI ("claude --help": low, medium, high, xhigh, max) unter
#  den deutschen Labelnamen, die im Repository vergeben werden.
AUFWAND = {
    "niedrig": "low",
    "mittel": "medium",
    "hoch": "high",
    "extra hoch": "xhigh",
    "maximal": "max",
}

#  Ohne Versionslabel wird der ALIAS gesetzt - er zeigt immer auf die neueste Fassung
#  der Reihe und veraltet damit nicht. Mit Versionslabel muss eine konkrete Fassung
#  her, und die ist eine Pflegestelle: Erscheint Opus 4.9, gehoert sie HIER nachgezogen.
MODELLE = {
    ("Opus", None): "opus",
    ("Opus", "4"): "claude-opus-4-8",
    ("Opus", "5"): "claude-opus-5",
    ("Sonnet", None): "sonnet",
    ("Sonnet", "4"): "claude-sonnet-4-6",
    ("Sonnet", "5"): "claude-sonnet-5",
}

#  Scoped Labels nach dem Vorbild von GitLab: "Scope::Wert" (erkannt von
#  scoped_labels.py). Zwei Label mit gleichem Scope schliessen einander aus
#  (siehe _eindeutig). Anders als vorher steht nirgends mehr eine Liste,
#  WELCHE Werte zu einem Scope gehoeren - das Trennzeichen im Labelnamen sagt
#  es. Ein neuer Aufwandswert braucht dadurch keine Aenderung mehr an dieser
#  Datei, nur einen neuen Eintrag in AUFWAND.
MODELL_SCOPE = "Modell"
VERSION_SCOPE = "v"
AUFWAND_SCOPE = "Aufwand"

#  Regel 1 des Auftrags, zu Ende gedacht: Der Runner kann die Komplexitaet eines
#  Vorgangs nicht beurteilen - er hat den Text nicht gelesen. Er ist also immer der
#  Fall "falls du nicht sicher bist", und der lautet Sonnet mit hohem Aufwand.
#  Ausdruecklich kein Abbruch und keine Rueckfrage.
STANDARD_MODELL = "sonnet"
STANDARD_AUFWAND = "high"


def lies(pfad):
    """[(nr, [label, ...]), ...]"""
    vorgaenge = []
    try:
        with io.open(pfad, encoding="utf-8") as f:
            for zeile in f:
                zeile = zeile.rstrip(chr(10)).rstrip(chr(13))
                if not zeile.strip():
                    continue
                nr, _, roh = zeile.partition(chr(9))
                labels = [x.strip() for x in roh.split(",") if x.strip()]
                vorgaenge.append((nr.strip(), labels))
    except OSError:
        pass
    return vorgaenge


def _eindeutig(vorgaenge, scope, was):
    """(wert, warnungen, war_gesetzt)

    wert ist der Teil hinter "Scope::", None wenn nichts gesetzt war ODER die
    Vorgaben sich widersprechen - war_gesetzt unterscheidet die beiden Faelle. Ohne
    diese Unterscheidung wuerde ein widerspruechliches Modell-Label zusaetzlich als
    "kein Modell-Label" gemeldet, und die zweite Meldung widerspraeche der ersten.
    """
    warnungen = []
    gesehen = set()
    streit = False
    for nr, labels in vorgaenge:
        treffer = sorted({x for x in labels if scoped_labels.scope(x) == scope})
        if len(treffer) > 1:
            streit = True
            warnungen.append("Vorgang %s traegt %s gleichzeitig: %s. Die Labels "
                             "schliessen einander aus."
                             % (nr, was, " und ".join(treffer)))
        gesehen.update(scoped_labels.wert(x) for x in treffer)

    if streit:
        #  Die Ursache ist schon benannt. Die Meldung unten waere dieselbe Sache
        #  ein zweites Mal, nur unscharf formuliert.
        return None, warnungen, True
    if len(gesehen) > 1:
        anzeige = sorted(scope + "::" + w for w in gesehen)
        warnungen.append("Die offenen Vorgaenge verlangen verschiedene %s (%s). Ein "
                         "Lauf hat nur eines." % (was, ", ".join(anzeige)))
        return None, warnungen, True
    return (gesehen.pop() if gesehen else None), warnungen, bool(gesehen)


def waehle(vorgaenge):
    """(modell, aufwand, warnungen)"""
    modell, w1, modell_gesetzt = _eindeutig(vorgaenge, MODELL_SCOPE, "Modell-Label")
    version, w2, _ = _eindeutig(vorgaenge, VERSION_SCOPE, "Versions-Label")
    stufe, w3, _ = _eindeutig(vorgaenge, AUFWAND_SCOPE, "Aufwands-Label")
    warnungen = w1 + w2 + w3

    if modell is None:
        #  Regel 5: Version oder Aufwand ohne Modell ist keine halbe Vorgabe, sondern
        #  gar keine - ohne Modell ist nicht bestimmt, WESSEN Version gemeint ist.
        #  War ein Modell-Label da und nur widerspruechlich, steht der Grund schon
        #  oben; dann waere diese Meldung falsch.
        if (version or stufe) and not modell_gesetzt:
            warnungen.append("Es ist ein Label fuer Version oder Aufwand gesetzt, aber "
                             "keines fuer das Modell. Beide werden verworfen.")
        return STANDARD_MODELL, STANDARD_AUFWAND, warnungen

    ziel = MODELLE.get((modell, version))
    if ziel is None:
        #  Scoped Labels erlauben jeden Wert hinter "Modell::" bzw. "v::" - anders
        #  als die frueheren, fest aufgezaehlten Label kann das auf eine
        #  Kombination zeigen, die MODELLE nicht kennt. Abbrechen waere hier
        #  falsch: Regel 1 gilt auch fuer einen Tippfehler im Label.
        warnungen.append("Unbekanntes Modell oder unbekannte Version: Modell::%s%s. "
                         "Standard wird verwendet."
                         % (modell, " v::" + version if version else ""))
        return STANDARD_MODELL, STANDARD_AUFWAND, warnungen

    return ziel, AUFWAND.get(stufe, "high"), warnungen


def main():
    vorgaenge = lies("labels.txt")
    modell, aufwand, warnungen = waehle(vorgaenge)

    zeilen = ["Modell: %s" % modell, "Aufwand: %s" % aufwand]
    zeilen += ["Warnung: " + w for w in warnungen]
    text = chr(10).join(zeilen)
    print(text)
    for w in warnungen:
        print("::warning::" + w)

    z = os.environ.get("GITHUB_STEP_SUMMARY")
    if z:
        io.open(z, "a", encoding="utf-8").write(text + chr(10))
    a = os.environ.get("GITHUB_OUTPUT")
    if a:
        io.open(a, "a", encoding="utf-8").write(
            "modell=%s%saufwand=%s%s" % (modell, chr(10), aufwand, chr(10)))
    return 0


def selbsttest():
    """Je Regel des Auftrags mindestens ein Fall, und je Fall ein Gegenbeispiel.

    Die erwarteten Werte stehen hier als Literale - nicht als Aufruf derselben
    Tabellen, die geprueft werden. Sonst pruefte der Test die Tabelle gegen sich
    selbst und bliebe auch dann gruen, wenn beide gemeinsam falsch waeren.
    """
    fehler = []

    def v(*labelmengen):
        return [(str(i + 1), list(m)) for i, m in enumerate(labelmengen)]

    def pruefe(name, vorgaenge, modell, aufwand, warnt=None):
        m, a, w = waehle(vorgaenge)
        if (m, a) != (modell, aufwand):
            fehler.append("%s: (%r, %r) statt (%r, %r)" % (name, m, a, modell, aufwand))
        if warnt is None:
            if w:
                fehler.append("%s: unerwartete Warnung %r" % (name, w))
        elif not any(warnt in x for x in w):
            fehler.append("%s: %r nicht gewarnt, stattdessen %r" % (name, warnt, w))

    #  Regel 1: kein Label - Sonnet, hoch, keine Warnung, kein Abbruch
    pruefe("gar kein Label", v([]), "sonnet", "high")
    pruefe("gar kein Vorgang", [], "sonnet", "high")
    pruefe("nur fremde Label", v(["Einarbeiten", "Gegenlese"]), "sonnet", "high")

    #  Regel 3: Modell ohne Version - der Alias, damit es nicht veraltet
    pruefe("Opus ohne Version", v(["Modell::Opus"]), "opus", "high")
    pruefe("Sonnet ohne Version", v(["Modell::Sonnet"]), "sonnet", "high")

    #  Regel 6: Version gesetzt - neueste Variante dieser Reihe, fest benannt
    pruefe("Opus 4", v(["Modell::Opus", "v::4"]), "claude-opus-4-8", "high")
    pruefe("Opus 5", v(["Modell::Opus", "v::5"]), "claude-opus-5", "high")
    pruefe("Sonnet 4", v(["Modell::Sonnet", "v::4"]), "claude-sonnet-4-6", "high")
    pruefe("Sonnet 5", v(["Modell::Sonnet", "v::5"]), "claude-sonnet-5", "high")

    #  Regel 2: kombinierbar ueber die Scopes hinweg
    pruefe("Opus 4 niedrig", v(["Modell::Opus", "v::4", "Aufwand::niedrig"]),
           "claude-opus-4-8", "low")
    pruefe("Sonnet maximal", v(["Modell::Sonnet", "Aufwand::maximal"]), "sonnet", "max")
    pruefe("Opus extra hoch", v(["Modell::Opus", "Aufwand::extra hoch"]), "opus", "xhigh")
    pruefe("Sonnet 5 mittel", v(["Modell::Sonnet", "v::5", "Aufwand::mittel"]),
           "claude-sonnet-5", "medium")

    #  Regel 4: Aufwand fehlt - "hoch"
    pruefe("Aufwand fehlt", v(["Modell::Opus", "v::5"]), "claude-opus-5", "high")

    #  Regel 2: innerhalb eines Scopes nicht kombinierbar - Warnung, dann Regel 1
    pruefe("Opus und Sonnet", v(["Modell::Opus", "Modell::Sonnet"]), "sonnet", "high",
           "schliessen einander aus")
    pruefe("4 und 5", v(["Modell::Opus", "v::4", "v::5"]), "opus", "high",
           "schliessen einander aus")
    pruefe("niedrig und maximal",
           v(["Modell::Opus", "Aufwand::niedrig", "Aufwand::maximal"]), "opus", "high",
           "schliessen einander aus")

    #  Regel 5: Version oder Aufwand ohne Modell - Warnung, dann Regel 1.
    #  Der Aufwand wird MIT verworfen; "Aufwand::niedrig" allein darf nicht durchschlagen.
    pruefe("nur Version", v(["v::5"]), "sonnet", "high", "keines fuer das Modell")
    pruefe("nur Aufwand", v(["Aufwand::niedrig"]), "sonnet", "high",
           "keines fuer das Modell")
    pruefe("nur Version und Aufwand", v(["v::4", "Aufwand::maximal"]), "sonnet", "high",
           "keines fuer das Modell")

    #  Widerspruch beim Modell darf NICHT zusaetzlich als "kein Modell-Label"
    #  gemeldet werden - die zweite Meldung widerspraeche der ersten.
    def keine_meldung(vorgaenge, teil):
        return not any(teil in w for w in waehle(vorgaenge)[2])

    if not keine_meldung(v(["Modell::Opus", "Modell::Sonnet", "Aufwand::maximal"]),
                          "keines fuer das Modell"):
        fehler.append("Widerspruch beim Modell wird zusaetzlich als fehlend gemeldet")

    #  Umgekehrt muss die Meldung kommen, wenn wirklich kein Modell dasteht.
    if keine_meldung(v(["Aufwand::maximal"]), "keines fuer das Modell"):
        fehler.append("fehlendes Modell-Label wird nicht gemeldet")

    #  Mehrere Vorgaenge: gleiche Vorgabe traegt, widerspruechliche faellt auf Regel 1
    pruefe("zwei Vorgaenge, einer gelabelt",
           v(["Modell::Opus", "v::5"], []), "claude-opus-5", "high")
    pruefe("zwei Vorgaenge, gleiche Vorgabe",
           v(["Modell::Opus"], ["Modell::Opus", "Aufwand::niedrig"]), "opus", "low")
    pruefe("zwei Vorgaenge, verschiedene Modelle",
           v(["Modell::Opus"], ["Modell::Sonnet"]), "sonnet", "high",
           "verschiedene Modell-Label")
    pruefe("zwei Vorgaenge, verschiedener Aufwand",
           v(["Modell::Opus", "Aufwand::niedrig"], ["Modell::Opus", "Aufwand::maximal"]),
           "opus", "high", "verschiedene Aufwands-Label")

    #  Scope ohne bekannten Wert: keine gepflegte Liste mehr, die das verhindern
    #  koennte (das ist der Sinn scoped Labels) - also faengt das hier ab statt
    #  mit einem KeyError abzubrechen.
    pruefe("unbekannter Modellwert", v(["Modell::Haiku"]), "sonnet", "high",
           "Unbekanntes Modell")
    pruefe("unbekannte Modell-Version-Kombination", v(["Modell::Opus", "v::7"]),
           "sonnet", "high", "Unbekanntes Modell")

    #  Das Einlesen: Tabulator trennt, Komma trennt, Leerraum stoert nicht
    import tempfile
    d = tempfile.mkdtemp()
    pfad = os.path.join(d, "labels.txt")
    io.open(pfad, "w", encoding="utf-8", newline="").write(
        "31" + chr(9) + "Einarbeiten, Modell::Opus , v::5" + chr(10) + chr(10) +
        "30" + chr(9) + "" + chr(10))
    gelesen = lies(pfad)
    if gelesen != [("31", ["Einarbeiten", "Modell::Opus", "v::5"]), ("30", [])]:
        fehler.append("lies(): %r" % (gelesen,))
    if lies(os.path.join(d, "gibtsnicht.txt")) != []:
        fehler.append("fehlende Datei sollte [] geben")

    gesamt = 30
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(selbsttest() if "--selbsttest" in sys.argv else main())
