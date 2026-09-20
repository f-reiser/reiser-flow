#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plant und fuehrt den Label-Abgleich fuer label-abgleich.yml aus
(f-reiser/reiser-flow#54).

plane() ist reine Logik, ohne Netzwerkzugriff, deshalb voll testbar. main()
verbindet sie mit "gh label ..." fuer das Repository aus der Umgebungsvariable
REPO.

REGEL FARBE VS. BESCHREIBUNG
    Ein bereits unter seinem aktuellen Katalognamen bestehendes Label behaelt
    seine Farbe unangetastet - eine bewusste Nutzerwahl wird nie ueberschrieben.
    Die Beschreibung dagegen wird immer auf den Katalogstand gebracht (Issue
    #54, Abschnitt "Labelkommentare"). Farbe UND Beschreibung werden nur beim
    Neuanlegen oder bei einer Umbenennung gesetzt - beides ist der Moment, in
    dem ein Label ueberhaupt erst unter reiser-flows Verwaltung kommt.

REGEL UMBENENNUNG
    Ein Katalogeintrag kann "vorher" tragen - fruehere Namen desselben Labels.
    Findet sich einer davon im Zielprojekt, wird umbenannt statt ein zweites,
    doppeltes Label anzulegen.

REGEL LOESCHUNG
    Ein Name aus dem "entfernt"-Zweig des Katalogs wird im Zielprojekt
    geloescht, wenn er dort existiert, kein aktueller oder frueherer Name
    eines noch bestehenden Katalogeintrags ist, UND nicht in Verwendung ist.
    Ist er in Verwendung, bleibt er stehen - das gehoert dann von Hand in die
    Release-Notes (Issue #54).
"""
import io
import json
import os
import subprocess
import sys

WURZEL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WURZEL)

import labels_lesen  # noqa: E402


def plane(ziel, katalog, entfernt, genutzt):
    """ziel: {Name: {"farbe":..., "beschreibung":...}} - Stand im Zielprojekt.
    katalog: Liste wie labels_lesen.katalog_eintraege().
    entfernt: Liste wie labels_lesen.entfernte().
    genutzt: Menge von Namen aus "entfernt", die im Zielprojekt noch an einem
             offenen oder geschlossenen Vorgang haengen.
    """
    aktionen = []

    for eintrag in katalog:
        name = eintrag["name"]
        if name in ziel:
            if ziel[name].get("beschreibung", "") != eintrag["beschreibung"]:
                aktionen.append({"art": "beschreibung", "name": name,
                                  "beschreibung": eintrag["beschreibung"]})
            continue

        alter_name = next((v for v in eintrag.get("vorher", []) if v in ziel), None)
        if alter_name is not None:
            aktionen.append({"art": "umbenennen", "von": alter_name, "name": name,
                              "farbe": eintrag["farbe"], "beschreibung": eintrag["beschreibung"]})
        else:
            aktionen.append({"art": "erstellen", "name": name,
                              "farbe": eintrag["farbe"], "beschreibung": eintrag["beschreibung"]})

    #  Ein Name zaehlt nicht als "entfernt", solange er noch aktueller oder
    #  fruehererer Name irgendeines bestehenden Katalogeintrags ist.
    lebende_namen = {e["name"] for e in katalog}
    lebende_namen |= {v for e in katalog for v in e.get("vorher", [])}

    for eintrag in entfernt:
        name = eintrag["name"]
        if name in lebende_namen or name not in ziel:
            continue
        if name in genutzt:
            aktionen.append({"art": "loeschen_uebersprungen", "name": name})
        else:
            aktionen.append({"art": "loeschen", "name": name})

    return aktionen


#  ------------------------------------------------------------------ gh-Anbindung

def _gh(*args):
    return subprocess.run(["gh"] + list(args), check=True, capture_output=True, text=True)


def ziel_lesen(repo):
    p = _gh("label", "list", "--repo", repo, "--json", "name,color,description", "--limit", "1000")
    rohliste = json.loads(p.stdout)
    return {l["name"]: {"farbe": l["color"], "beschreibung": l.get("description") or ""}
            for l in rohliste}


def in_verwendung(repo, name):
    """True, wenn irgendein Issue oder Pull Request (offen oder geschlossen)
    dieses Label noch traegt."""
    p = _gh("api", "search/issues", "--jq", ".total_count",
            "-f", "q=repo:%s label:\"%s\"" % (repo, name))
    return int(p.stdout.strip() or "0") > 0


def anwenden(repo, aktionen):
    for a in aktionen:
        if a["art"] == "erstellen":
            _gh("label", "create", a["name"], "--repo", repo,
                "--color", a["farbe"], "--description", a["beschreibung"], "--force")
            print("angelegt: %s" % a["name"])
        elif a["art"] == "umbenennen":
            _gh("label", "edit", a["von"], "--repo", repo, "--name", a["name"],
                "--color", a["farbe"], "--description", a["beschreibung"])
            print("umbenannt: %s -> %s" % (a["von"], a["name"]))
        elif a["art"] == "beschreibung":
            _gh("label", "edit", a["name"], "--repo", repo,
                "--description", a["beschreibung"])
            print("Beschreibung aktualisiert: %s" % a["name"])
        elif a["art"] == "loeschen":
            _gh("label", "delete", a["name"], "--repo", repo, "--yes")
            print("geloescht: %s" % a["name"])
        elif a["art"] == "loeschen_uebersprungen":
            print("NICHT geloescht (noch in Verwendung, gehoert in die "
                  "Release-Notes): %s" % a["name"])


def main():
    repo = os.environ["REPO"]
    katalog_pfad = os.environ.get("LABELS_JSON", labels_lesen.KATALOG)

    katalog = labels_lesen.katalog_eintraege(katalog_pfad)
    entfernt = labels_lesen.entfernte(katalog_pfad)
    ziel = ziel_lesen(repo)

    kandidaten = [e["name"] for e in entfernt if e["name"] in ziel]
    genutzt = {name for name in kandidaten if in_verwendung(repo, name)}

    aktionen = plane(ziel, katalog, entfernt, genutzt)
    if not aktionen:
        print("Nichts zu tun - Katalog und Zielprojekt stimmen ueberein.")
        return 0
    anwenden(repo, aktionen)
    return 0


#  ------------------------------------------------------------------ Selbsttest

def selbsttest():
    fehler = []

    def pruefe(was, ist, erwartet):
        if ist != erwartet:
            fehler.append("%s: %r statt %r" % (was, ist, erwartet))

    katalog = [
        {"name": "Einarbeiten", "farbe": "0e8a16", "beschreibung": "neu", "vorher": []},
        {"name": "Duplikat", "farbe": "cfd3d7", "beschreibung": "dup", "vorher": ["Duplicate", "duplicate"]},
        {"name": "Verworfen", "farbe": "ffffff", "beschreibung": "weg", "vorher": ["WontDone"]},
        {"name": "Frisch", "farbe": "abcdef", "beschreibung": "neues Label", "vorher": []},
    ]
    entfernt = [{"name": "Altlast"}, {"name": "NieVerwendet"}]

    #  Fall 1: existiert schon unter aktuellem Namen, Beschreibung veraltet ->
    #  nur Beschreibung aendern, Farbe bleibt (moegliche Nutzerwahl) unangetastet.
    ziel = {"Einarbeiten": {"farbe": "irgendeine-andere-farbe", "beschreibung": "alt"}}
    a = plane(ziel, [katalog[0]], [], set())
    pruefe("Fall 1", a, [{"art": "beschreibung", "name": "Einarbeiten", "beschreibung": "neu"}])

    #  Fall 1b: existiert schon, Beschreibung stimmt bereits -> keine Aktion.
    ziel = {"Einarbeiten": {"farbe": "x", "beschreibung": "neu"}}
    a = plane(ziel, [katalog[0]], [], set())
    pruefe("Fall 1b", a, [])

    #  Fall 2: existiert unter einem frueheren Namen -> umbenennen, dabei Farbe
    #  UND Beschreibung frisch setzen.
    ziel = {"duplicate": {"farbe": "irgendwas", "beschreibung": "alt"}}
    a = plane(ziel, [katalog[1]], [], set())
    pruefe("Fall 2", a, [{"art": "umbenennen", "von": "duplicate", "name": "Duplikat",
                           "farbe": "cfd3d7", "beschreibung": "dup"}])

    #  Fall 3: existiert unter keinem der Namen -> neu anlegen.
    ziel = {}
    a = plane(ziel, [katalog[3]], [], set())
    pruefe("Fall 3", a, [{"art": "erstellen", "name": "Frisch",
                           "farbe": "abcdef", "beschreibung": "neues Label"}])

    #  Fall 4: entfernter Name existiert im Ziel, nicht in Verwendung -> loeschen.
    ziel = {"Altlast": {"farbe": "x", "beschreibung": "y"}}
    a = plane(ziel, [], entfernt, set())
    pruefe("Fall 4", a, [{"art": "loeschen", "name": "Altlast"}])

    #  Fall 5: entfernter Name existiert im Ziel, ist aber noch in Verwendung
    #  -> stehen lassen, aber melden.
    ziel = {"Altlast": {"farbe": "x", "beschreibung": "y"}}
    a = plane(ziel, [], entfernt, {"Altlast"})
    pruefe("Fall 5", a, [{"art": "loeschen_uebersprungen", "name": "Altlast"}])

    #  Fall 6: "entfernter" Name ist tatsaechlich noch der VORHERIGE Name eines
    #  lebenden Labels (Umbenennung mitten im Rollout) -> nicht loeschen, die
    #  Umbenennung uebernimmt ihn.
    ziel = {"WontDone": {"farbe": "x", "beschreibung": "y"}}
    a = plane(ziel, [katalog[2]], [{"name": "WontDone"}], set())
    pruefe("Fall 6", a, [{"art": "umbenennen", "von": "WontDone", "name": "Verworfen",
                           "farbe": "ffffff", "beschreibung": "weg"}])

    #  Fall 7: entfernter Name existiert im Ziel gar nicht -> keine Aktion.
    ziel = {}
    a = plane(ziel, [], entfernt, set())
    pruefe("Fall 7", a, [])

    gesamt = 8
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(selbsttest() if "--selbsttest" in sys.argv else main())
