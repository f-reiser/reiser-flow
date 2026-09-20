#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Liest .github/labels.json, den Label-Katalog dieses Repositories - fuer den
Abgleich-Workflow (label-abgleich.yml) und fuer geschuetzt.py, damit die Liste
der geschuetzten Label nicht zweimal existiert (f-reiser/reiser-flow#11).

Aufruf ohne Argument gibt den Katalog als TSV aus (Name, Farbe, Beschreibung),
eine Zeile je Label - auch die aus den Scopes aufgeklappten ("Modell::Opus").
Mit --selbsttest prueft es sich selbst, mit einem eigenen Katalog als Muster.
"""
import io
import json
import os
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KATALOG = os.path.join(WURZEL, "labels.json")


def lade(pfad):
    with io.open(pfad, encoding="utf-8") as f:
        return json.load(f)


def einzelne(katalog):
    """Die direkt benannten Label als (Name, Farbe, Beschreibung, geschuetzt)."""
    return [(l["name"], l["farbe"], l.get("beschreibung", ""), bool(l.get("geschuetzt")))
            for l in katalog.get("label", [])]


def aus_scopes(katalog):
    """Dieselbe Form, aus den Scopes zu "Scope::Wert" aufgeklappt.

    Die Farbe und ob es geschuetzt ist, gelten je Scope - ein einzelner Wert
    traegt beides nicht selbst, sonst koennte ein neuer Wert unbemerkt
    ungeschuetzt bleiben.
    """
    ergebnis = []
    for scope, angaben in katalog.get("scopes", {}).items():
        farbe = angaben["farbe"]
        geschuetzt = bool(angaben.get("geschuetzt"))
        for wert in angaben.get("werte", []):
            ergebnis.append(("%s::%s" % (scope, wert), farbe, "", geschuetzt))
    return ergebnis


def alle(pfad=KATALOG):
    katalog = lade(pfad)
    return einzelne(katalog) + aus_scopes(katalog)


def geschuetzte_einzelne(pfad=KATALOG):
    return {l["name"] for l in lade(pfad).get("label", []) if l.get("geschuetzt")}


def geschuetzte_scopes(pfad=KATALOG):
    return {s for s, a in lade(pfad).get("scopes", {}).items() if a.get("geschuetzt")}


#  ------------------------------------------------------------------ Selbsttest

MUSTER = {
    "label": [
        {"name": "Einarbeiten", "farbe": "0e8a16", "beschreibung": "x", "geschuetzt": True},
        {"name": "Dokumentation", "farbe": "0075ca", "beschreibung": "y"},
    ],
    "scopes": {
        "Modell": {"farbe": "bfdadc", "geschuetzt": True, "werte": ["Opus", "Sonnet"]},
        "Prioritaet": {"farbe": "ffffff", "werte": ["hoch", "niedrig"]},
    },
}


def _muster_datei(tmp_verzeichnis):
    pfad = os.path.join(tmp_verzeichnis, "muster_labels.json")
    with io.open(pfad, "w", encoding="utf-8") as f:
        json.dump(MUSTER, f)
    return pfad


def selbsttest():
    import tempfile

    fehler = []

    with tempfile.TemporaryDirectory() as td:
        pfad = _muster_datei(td)

        def pruefe(was, ist, erwartet):
            if ist != erwartet:
                fehler.append("%s: %r statt %r" % (was, ist, erwartet))

        #  Einzelne Label unveraendert uebernommen.
        e = einzelne(lade(pfad))
        pruefe("einzelne()", sorted(e),
               sorted([("Einarbeiten", "0e8a16", "x", True),
                       ("Dokumentation", "0075ca", "y", False)]))

        #  Scopes klappen zu "Scope::Wert" auf, mit der Scope-Farbe und ohne
        #  eigene Beschreibung.
        s = aus_scopes(lade(pfad))
        pruefe("aus_scopes()", sorted(s),
               sorted([("Modell::Opus", "bfdadc", "", True),
                       ("Modell::Sonnet", "bfdadc", "", True),
                       ("Prioritaet::hoch", "ffffff", "", False),
                       ("Prioritaet::niedrig", "ffffff", "", False)]))

        #  alle() ist beides zusammen.
        pruefe("alle()", sorted(alle(pfad)), sorted(e + s))

        #  Geschuetzte einzelne Label: nur die mit "geschuetzt": true.
        pruefe("geschuetzte_einzelne()", geschuetzte_einzelne(pfad),
               {"Einarbeiten"})

        #  Geschuetzte Scopes: nur die mit "geschuetzt": true, unabhaengig vom
        #  konkreten Wert - ein Wert, der noch nie vergeben wurde, ist trotzdem
        #  geschuetzt, weil der SCOPE es ist.
        pruefe("geschuetzte_scopes()", geschuetzte_scopes(pfad), {"Modell"})

    #  Der echte Katalog dieses Repositories: muss laden und die Label
    #  nennen, auf die geschuetzt.py sich verlaesst (Regression gegen
    #  konventionen.md).
    echte_geschuetzte = geschuetzte_einzelne(KATALOG)
    for name in ("Einarbeiten", "Untersuche", "Gegenlese"):
        if name not in echte_geschuetzte:
            fehler.append("echter Katalog: %r nicht geschuetzt" % name)
    echte_scopes = geschuetzte_scopes(KATALOG)
    for scope in ("Modell", "v", "Aufwand"):
        if scope not in echte_scopes:
            fehler.append("echter Katalog: Scope %r nicht geschuetzt" % scope)

    #  "Lokale Arbeit" vermerkt, dass ein Vorgang ohne den Menschen nicht fertig
    #  wird (f-reiser/reiser-flow#47). Es MUSS im Katalog stehen, damit
    #  label-abgleich.yml es in jedem einbindenden Projekt anlegt - und es darf
    #  NICHT geschuetzt sein: Gesetzt wird es vom unbeaufsichtigten Lauf, und der
    #  hat kein Maintainer-Recht. Der Waechter naehme es ihm sofort wieder ab.
    namen = {n for n, _, _, _ in alle(KATALOG)}
    if "Lokale Arbeit" not in namen:
        fehler.append("echter Katalog: 'Lokale Arbeit' fehlt")
    if "Lokale Arbeit" in echte_geschuetzte:
        fehler.append("'Lokale Arbeit' ist geschuetzt - der Lauf koennte es dann "
                      "nicht selbst setzen")

    gesamt = 5 + 3 + 3 + 2
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


def main():
    for name, farbe, beschreibung, _ in alle():
        print("%s\t%s\t%s" % (name, farbe, beschreibung))
    return 0


if __name__ == "__main__":
    sys.exit(selbsttest() if "--selbsttest" in sys.argv else main())
