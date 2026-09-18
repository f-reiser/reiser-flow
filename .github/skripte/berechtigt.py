#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entscheidet, ob eine GitHub-Rolle die geschuetzten Label setzen darf.

Aufgerufen von label-waechter.yml mit der Rolle aus
"repos/{repo}/collaborators/{wer}/permission" als einzigem Argument.
Gibt "ja" oder "nein" auf stdout aus und setzt den Exit-Code entsprechend
(0 = ja, 1 = nein), damit der Workflow-Schritt ohne weitere Python-Bruecke
mit "if [ ... ]" darauf reagieren kann.

WARUM ZWEI ROLLEN
    Admin galt bisher als einzige erlaubte Rolle. Der Nutzer hat das am
    13.09.2026 (zu PR#54) erweitert: Maintainer sollen die Steuerlabel
    ebenso setzen duerfen, Write-Mitglieder weiterhin nicht.
"""
import sys

ERLAUBT = ("admin", "maintain")


def darf_setzen(recht):
    return recht in ERLAUBT


def selbsttest():
    fehler = []

    def pruefe(recht, erwartet):
        e = darf_setzen(recht)
        if e != erwartet:
            fehler.append("%r: %r statt %r" % (recht, e, erwartet))

    pruefe("admin", True)
    pruefe("maintain", True)
    pruefe("write", False)
    pruefe("triage", False)
    pruefe("read", False)
    pruefe("none", False)
    pruefe("", False)
    pruefe(None, False)

    gesamt = 8
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


def main():
    recht = sys.argv[1] if len(sys.argv) > 1 else ""
    ok = darf_setzen(recht)
    print("ja" if ok else "nein")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(selbsttest() if "--selbsttest" in sys.argv else main())
