#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Filtert Rueckfrage-Vorgaenge auf die, deren Label wirklich vom NUTZER kommt
(f-reiser/reiser-flow#53).

"Rueckfrage" ist bidirektional: Claude setzt es fuer eine eigene Frage an den
Nutzer, der Nutzer setzt es fuer eine eigene Frage an Claude. claude-aufgaben.yml
soll nur die zweite Richtung anstossen - sonst griffe der naechste Lauf Claudes
eigene, noch unbeantwortete Frage wieder auf, faende darauf natuerlich keine
neue Antwort und liefe ins Leere.

Aufruf: Vorgangsnummern zeilenweise auf stdin, REPO in der Umgebung. Gibt die
Teilmenge aus, deren Label zuletzt von einem MENSCHEN gesetzt wurde.

Unterscheidet ueber die Timeline des Vorgangs: wer hat "Rueckfrage" zuletzt
gesetzt? Ein Bot-Akteur (github-actions[bot], unter dem auch dieser Lauf
selbst handelt) heisst: Claude hat gefragt - ausschliessen. Findet sich gar
kein "labeled"-Ereignis dafuer (Timeline-Grenze, siehe _gh_timeline), gilt im
Zweifel AUSGESCHLOSSEN: ein verpasster Lauf kostet nichts, ein faelschlich
angestossener schon.
"""
import json
import os
import subprocess
import sys


def ist_von_nutzer(ereignisse):
    """True, wenn das zuletzt gesetzte "Rueckfrage"-Label von einem Menschen
    kommt (nicht von einem Bot-Akteur). ereignisse: rohe Timeline-Eintraege."""
    treffer = [e for e in ereignisse
               if e.get("event") == "labeled"
               and (e.get("label") or {}).get("name") == "Rückfrage"]
    if not treffer:
        return False
    akteur = treffer[-1].get("actor") or {}
    return akteur.get("type") != "Bot"


def _gh_timeline(repo, nr):
    #  Nur die letzten 100 Ereignisse: fuer die Frage "wer hat das Label
    #  ZULETZT gesetzt" reicht das in jedem realistischen Fall - ein Vorgang
    #  mit mehr als 100 Timeline-Ereignissen ist eine Ausnahme, die diese
    #  Datei bewusst nicht verfolgt (sie faellt dann auf "nein" zurueck).
    p = subprocess.run(
        ["gh", "api", "repos/%s/issues/%s/timeline?per_page=100" % (repo, nr)],
        check=True, capture_output=True, text=True)
    return json.loads(p.stdout)


def main():
    repo = os.environ["REPO"]
    nummern = [z.strip() for z in sys.stdin if z.strip()]
    for nr in nummern:
        try:
            ereignisse = _gh_timeline(repo, nr)
        except (subprocess.CalledProcessError, ValueError):
            #  Kein Abbruch: ein einzelner nicht lesbarer Vorgang darf die
            #  uebrigen nicht mitreissen. Im Zweifel ausgeschlossen.
            continue
        if ist_von_nutzer(ereignisse):
            print(nr)
    return 0


#  ------------------------------------------------------------------ Selbsttest

def selbsttest():
    fehler = []

    def pruefe(was, ist, erwartet):
        if ist != erwartet:
            fehler.append("%s: %r statt %r" % (was, ist, erwartet))

    def labeled(name, akteur_login, akteur_typ):
        return {"event": "labeled", "label": {"name": name},
                "actor": {"login": akteur_login, "type": akteur_typ}}

    #  Nutzer setzt Rueckfrage -> einschliessen.
    pruefe("vom Nutzer gesetzt",
           ist_von_nutzer([labeled("Rückfrage", "ReiserFlorian", "User")]), True)

    #  Bot (der Lauf selbst) setzt Rueckfrage -> ausschliessen.
    pruefe("vom Bot gesetzt",
           ist_von_nutzer([labeled("Rückfrage", "github-actions[bot]", "Bot")]), False)

    #  Kein "labeled"-Ereignis fuer Rueckfrage ueberhaupt -> im Zweifel nein.
    pruefe("kein Ereignis", ist_von_nutzer([]), False)
    pruefe("nur andere Ereignisse",
           ist_von_nutzer([{"event": "commented"}]), False)

    #  Andere Label im Verlauf stoeren nicht.
    pruefe("anderes Label dazwischen",
           ist_von_nutzer([labeled("Einarbeiten", "ReiserFlorian", "User"),
                            labeled("Rückfrage", "ReiserFlorian", "User")]), True)

    #  Entscheidend ist das LETZTE Ereignis: Bot setzt, Nutzer entfernt und
    #  setzt erneut -> jetzt vom Nutzer.
    pruefe("zuletzt vom Nutzer nach Bot",
           ist_von_nutzer([labeled("Rückfrage", "github-actions[bot]", "Bot"),
                            {"event": "unlabeled", "label": {"name": "Rückfrage"}},
                            labeled("Rückfrage", "ReiserFlorian", "User")]), True)

    #  Umgekehrt: Nutzer setzt, wird entfernt, Bot setzt erneut (Claude hat
    #  eine eigene neue Frage) -> jetzt wieder ausgeschlossen.
    pruefe("zuletzt vom Bot nach Nutzer",
           ist_von_nutzer([labeled("Rückfrage", "ReiserFlorian", "User"),
                            {"event": "unlabeled", "label": {"name": "Rückfrage"}},
                            labeled("Rückfrage", "github-actions[bot]", "Bot")]), False)

    gesamt = 7
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(selbsttest() if "--selbsttest" in sys.argv else main())
