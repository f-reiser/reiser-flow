#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entscheidet, ob ein Label zu den Steuerlabeln gehoert, die label-waechter.yml
vor allen ausser Admin und Maintainer schuetzt.

Aufgerufen mit dem Labelnamen als einzigem Argument. Gibt "ja"/"nein" aus und
setzt den Exit-Code entsprechend (0 = geschuetzt, 1 = nicht geschuetzt).

WARUM KEINE AUFZAEHLUNG DER SCOPED-WERTE
    Modell, Version und Aufwand sind scoped Labels nach dem Vorbild von GitLab
    ("Scope::Wert", erkannt von scoped_labels.py). Ein neuer Aufwandswert (z.B.
    "Aufwand::ultra") ist damit automatisch geschuetzt, ohne dass labels.json
    etwas davon wissen muss - nur die drei Scope-Namen selbst sind dort
    eingetragen, nicht ihre Werte.

WOHER DIE LISTE KOMMT
    Aus .github/labels.json, damit sie nicht ein zweites Mal hier steht (siehe
    f-reiser/reiser-flow#11) - labels_lesen.py liest die Datei.
"""
import sys

import labels_lesen
import scoped_labels


def geschuetzt(label):
    if label in labels_lesen.geschuetzte_einzelne():
        return True
    return scoped_labels.scope(label) in labels_lesen.geschuetzte_scopes()


def selbsttest():
    fehler = []

    def pruefe(label, erwartet):
        e = geschuetzt(label)
        if e != erwartet:
            fehler.append("%r: %r statt %r" % (label, e, erwartet))

    pruefe("Einarbeiten", True)
    pruefe("Untersuche", True)
    pruefe("Gegenlese", True)
    pruefe("Modell::Opus", True)
    pruefe("Modell::Sonnet", True)
    pruefe("v::4", True)
    pruefe("v::5", True)
    pruefe("Aufwand::niedrig", True)
    pruefe("Aufwand::extra hoch", True)
    #  Ein Wert, der noch nie vergeben wurde, ist trotzdem geschuetzt - das ist
    #  der Sinn des Scopes, nicht der Aufzaehlung.
    pruefe("Aufwand::ultra", True)
    pruefe("Modell::Haiku", True)

    #  NICHT geschuetzt: der Befund einer Gegenlese, und alles Fremde.
    pruefe("GegenleseBefund", False)
    pruefe("Dokumentation", False)
    pruefe("Modell", False)
    pruefe("", False)

    gesamt = 15
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else ""
    ok = geschuetzt(label)
    print("ja" if ok else "nein")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(selbsttest() if "--selbsttest" in sys.argv else main())
