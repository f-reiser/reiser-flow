#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Baut API-Pfade, in denen ein Labelname als Pfadsegment steht.

Zum Entfernen eines Labels gibt es nur einen Weg:

    DELETE /repos/{owner}/{repo}/issues/{nr}/labels/{name}

Der Name MUSS im Pfad stehen, die API kennt dafuer keinen Query-Parameter. Und
GitHub laesst in Labelnamen so gut wie alles zu - Leerzeichen ("Aufwand::extra
hoch" gibt es hier wirklich), Doppelpunkte, "#", "?" und auch "/". Wer so einen
Namen ungeprueft in den Pfad schreibt, spricht einen anderen Endpunkt an als
gemeint (f-reiser/reiser-flow#30).

Deshalb EINE Stelle, die diesen Pfad baut, statt derselben Zeile an drei Orten:
label-waechter.yml, scope_ausschluss.py - und label_sicherheitsnetz.py, sobald
f-reiser/reiser-flow#6 fertig ist.

Aufruf aus der Shell mit <repo> <nr> <label>; gibt den fertigen Pfad aus, damit
ein Workflow ihn direkt an "gh api" weiterreichen kann.
"""
import sys


def label_pfad(repo, nr, label):
    """Pfad zum Entfernen von 'label' an Vorgang 'nr' in 'repo'."""
    return "repos/%s/issues/%s/labels/%s" % (repo, nr, label)


def selbsttest():
    fehler = []

    def pruefe(name, label, erwartet):
        ist = label_pfad("f-reiser/reiser-flow", 7, label)
        soll = "repos/f-reiser/reiser-flow/issues/7/labels/" + erwartet
        if ist != soll:
            fehler.append("%s: %r statt %r" % (name, ist, soll))

    #  Der harmlose Normalfall darf sich NICHT veraendern - sonst waere jede
    #  bestehende Label-Entfernung kaputt.
    pruefe("einfacher Name unveraendert", "Einarbeiten", "Einarbeiten")
    pruefe("Punkt und Bindestrich bleiben", "v1.2-alt", "v1.2-alt")

    #  Der Befund: ein "/" bildet ein Pfadsegment nach.
    pruefe("Schraegstrich", "a/b", "a%2Fb")
    pruefe("Segmentflucht", "x/../../repos", "x%2F..%2F..%2Frepos")

    #  Diese Labels gibt es hier wirklich.
    pruefe("Doppelpunkt im Scope", "Modell::Opus", "Modell%3A%3AOpus")
    pruefe("Leerzeichen", "Aufwand::extra hoch", "Aufwand%3A%3Aextra%20hoch")

    #  Zeichen, die eine URL sonst umdeuten.
    pruefe("Fragezeichen", "a?b", "a%3Fb")
    pruefe("Raute", "a#b", "a%23b")
    pruefe("Kaufmanns-Und", "a&b", "a%26b")
    pruefe("Prozent zuerst", "100%", "100%25")

    #  Nicht-ASCII: UTF-8, dann prozentkodiert.
    pruefe("Umlaut", "Rückfrage", "R%C3%BCckfrage")

    #  Die Nummer darf als Zahl oder als Text kommen - der Workflow reicht Text.
    if label_pfad("o/r", "7", "A") != label_pfad("o/r", 7, "A"):
        fehler.append("Nummer als Text und als Zahl ergeben verschiedene Pfade")

    gesamt = 12
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


def main():
    if len(sys.argv) != 4:
        sys.stderr.write("Aufruf: api_pfad.py <repo> <nr> <label>" + chr(10))
        return 2
    print(label_pfad(sys.argv[1], sys.argv[2], sys.argv[3]))
    return 0


if __name__ == "__main__":
    sys.exit(selbsttest() if "--selbsttest" in sys.argv else main())
