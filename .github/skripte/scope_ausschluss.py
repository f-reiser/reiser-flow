#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Setzt die Scoped-Label-Regel durch, die konventionen.md dokumentiert, aber die
bisher niemand technisch erzwingt: pro Scope (Modell, v, Aufwand) gilt gleichzeitig
hoechstens ein Wert. Wird ein neuer Wert gesetzt, entfernt dieses Skript die
anderen Werte desselben Scope vom selben Issue/PR.

Aufgerufen von label-waechter.yml, NACH der Berechtigungspruefung in derselben
Datei - dieses Skript prueft die Berechtigung nicht noch einmal, sondern nur, ob
das neue Label ueberhaupt noch da ist (die Berechtigungspruefung kann es schon
entfernt haben) und ob sein Scope zu den drei Steuerlabel-Scopes gehoert.
"Prioritaet::hoch" o.ae. bleibt unberuehrt.

Holt den Label-Stand FRISCH von GitHub statt sich auf das Event zu verlassen -
das macht das Skript robust gegen zwei fast gleichzeitige "labeled"-Events auf
demselben Issue. label-waechter.yml serialisiert das zusaetzlich ueber eine
concurrency-Gruppe je Issue, damit zwei Laeufe nicht denselben Vorgang doppelt
bearbeiten.
"""
import json
import os
import subprocess
import sys
import tempfile

import geschuetzt
import scoped_labels


def aktuelle_labels(repo, nr):
    lauf = subprocess.run(
        ["gh", "api", "repos/%s/issues/%s" % (repo, nr), "--jq", "[.labels[].name]"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(lauf.stdout)


def entfernen(repo, nr, label):
    subprocess.run(
        ["gh", "api", "--method", "DELETE",
         "repos/%s/issues/%s/labels/%s" % (repo, nr, label)],
        check=True,
    )


def kommentieren(repo, nr, neues_label, entfernte):
    text = (
        "`%s` gesetzt: %s automatisch entfernt, weil im selben Scope nur ein "
        "Wert gleichzeitig gilt (siehe `konventionen.md`, Abschnitt "
        "\"Steuerlabel: Modell, Version, Aufwand\").\n"
    ) % (neues_label, ", ".join("`%s`" % e for e in entfernte))
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                      encoding="utf-8") as f:
        f.write(text)
        pfad = f.name
    subprocess.run(
        ["gh", "api", "--method", "POST", "repos/%s/issues/%s/comments" % (repo, nr),
         "-F", "body=@%s" % pfad],
        check=True,
    )


def main():
    repo = os.environ["REPO"]
    nr = os.environ["NR"]
    label = os.environ["LABEL"]
    trockenlauf = "--trockenlauf" in sys.argv

    if not geschuetzt.geschuetzt(label):
        print("%s ist kein Steuerlabel-Scope - nichts zu tun." % label)
        return

    aktuell = aktuelle_labels(repo, nr)
    if label not in aktuell:
        print("%s ist nicht mehr auf #%s - vermutlich schon zurueckgenommen." % (label, nr))
        return

    entfernte = scoped_labels.geschwister_im_scope(aktuell, label)
    if not entfernte:
        print("Keine Geschwister im selben Scope - nichts zu tun.")
        return

    if trockenlauf:
        print("Trockenlauf: wuerde entfernen: %s" % ", ".join(entfernte))
        return

    for e in entfernte:
        entfernen(repo, nr, e)
    kommentieren(repo, nr, label, entfernte)
    print("Entfernt wegen Scope-Konflikt mit %s: %s" % (label, ", ".join(entfernte)))


if __name__ == "__main__":
    main()
