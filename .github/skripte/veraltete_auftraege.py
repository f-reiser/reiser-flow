#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nimmt ein geschuetztes Label (Einarbeiten, Untersuche, Gegenlese) automatisch
zurueck, wenn es laenger als FRIST_TAGE Tage ununterbrochen an einem Vorgang
haengt, ohne dass sich etwas getan hat (f-reiser/reiser-flow#23, Kommentar vom
20.09.2026).

WOZU
    Ein liegen gebliebener Auftrag ist entweder harmlos - unwahrscheinlich, der
    Cron von claude-aufgaben laeuft alle vier Stunden - oder ein Anzeichen, dass
    etwas nicht stimmt: der Waechter abgestuerzt, die Automatik blockiert. Fuenf
    Tage ohne jede Reaktion sind in jedem Fall ein Grund, den Auftrag
    zurueckzunehmen und nachzusehen, statt ihn endlos liegen zu lassen.

WELCHE LABEL
    Dieselben, die label-waechter.yml schuetzt - labels_lesen.geschuetzte_einzelne()
    ist die einzige Quelle dafuer, damit ein viertes geschuetztes Label automatisch
    mitgeprueft wird, ohne dass diese Datei etwas davon wissen muss.

WIE ALT IST "ALT"
    Nicht das Alter des Vorgangs, sondern seit wann DIESES Label ununterbrochen
    gesetzt ist - ueber die Timeline, das juengste "labeled"-Ereignis dafuer.
    Wurde es zwischendurch entfernt und neu gesetzt (etwa durch den
    Pruefsummen-Waechter aus #23, wenn sich der Vorgang geaendert hat), zaehlt
    das als Neubeginn - zu Recht, denn eine neue Freigabe ist ein neuer Start.
"""
import datetime
import io
import json
import os
import subprocess
import sys

WURZEL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WURZEL)

import labels_lesen  # noqa: E402

FRIST_TAGE_STANDARD = 5


def letztes_setzen(ereignisse, label):
    """ISO-Zeitpunkt des juengsten "labeled"-Ereignisses fuer label, sonst None."""
    treffer = [e for e in ereignisse
               if e.get("event") == "labeled"
               and (e.get("label") or {}).get("name") == label]
    if not treffer:
        return None
    return treffer[-1].get("created_at")


def abgelaufen(gesetzt_am, jetzt, frist_tage=FRIST_TAGE_STANDARD):
    """True, wenn gesetzt_am (ISO, "...Z") laenger als frist_tage vor jetzt liegt.

    gesetzt_am None (kein "labeled"-Ereignis gefunden, etwa Timeline-Grenze) gilt
    als NICHT abgelaufen - im Zweifel nichts zuruecknehmen, was noch nie
    nachgewiesen wurde."""
    if gesetzt_am is None:
        return False
    dann = datetime.datetime.strptime(gesetzt_am, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc)
    return (jetzt - dann) > datetime.timedelta(days=frist_tage)


#  ------------------------------------------------------------------ gh-Anbindung

def _gh(*args):
    p = subprocess.run(["gh"] + list(args), check=True, capture_output=True, text=True)
    return p.stdout


def _offene_mit_label(repo, label):
    nummern = []
    for typ in ("issue", "pr"):
        roh = _gh("api", "--paginate",
                  "repos/%s/%ss?state=open&labels=%s&per_page=100"
                  % (repo, typ, label)) or "[]"
        nummern += [n["number"] for n in json.loads(roh)]
    return sorted(set(nummern))


def _timeline(repo, nr):
    roh = _gh("api", "repos/%s/issues/%s/timeline?per_page=100" % (repo, nr))
    return json.loads(roh)


def _zuruecknehmen(repo, nr, label, gesetzt_am):
    _gh("api", "--method", "DELETE", "repos/%s/issues/%s/labels/%s" % (repo, nr, label))
    text = (
        "## Label `%s` automatisch zurückgenommen" % label + chr(10) * 2
        + "Es stand seit `%s` ununterbrochen an diesem Vorgang - länger als die "
          "Frist von %d Tagen, ohne dass sich sichtbar etwas getan hat."
          % (gesetzt_am, FRIST_TAGE_STANDARD) + chr(10) * 2
        + "Das kann harmlos sein (der Vorgang wurde übersehen) oder ein Zeichen, "
          "dass die Automatik an dieser Stelle nicht lief. Vor erneutem Setzen "
          "kurz nachsehen, woran es lag." + chr(10)
    )
    f = os.path.join(os.environ.get("RUNNER_TEMP", "."), "veraltet-%s-%s.md" % (nr, label))
    io.open(f, "w", encoding="utf-8", newline="").write(text)
    _gh("api", "--method", "POST", "repos/%s/issues/%s/comments" % (repo, nr),
        "-F", "body=@%s" % f)
    os.unlink(f)


def main():
    repo = os.environ["REPO"]
    frist_tage = int(os.environ.get("FRIST_TAGE", FRIST_TAGE_STANDARD))
    jetzt = datetime.datetime.now(datetime.timezone.utc)

    zuruecknahmen = 0
    for label in sorted(labels_lesen.geschuetzte_einzelne()):
        for nr in _offene_mit_label(repo, label):
            ereignisse = _timeline(repo, nr)
            gesetzt_am = letztes_setzen(ereignisse, label)
            if not abgelaufen(gesetzt_am, jetzt, frist_tage):
                continue
            print("#%s: %r seit %s abgelaufen - wird zurueckgenommen."
                  % (nr, label, gesetzt_am))
            _zuruecknehmen(repo, nr, label, gesetzt_am)
            zuruecknahmen += 1

    if zuruecknahmen == 0:
        print("Nichts abgelaufen.")
    return 0


#  ------------------------------------------------------------------ Selbsttest

def selbsttest():
    fehler = []

    def pruefe(was, ist, erwartet):
        if ist != erwartet:
            fehler.append("%s: %r statt %r" % (was, ist, erwartet))

    def labeled(name, zeit):
        return {"event": "labeled", "label": {"name": name}, "created_at": zeit}

    #  --- letztes_setzen ---------------------------------------------------
    pruefe("kein Ereignis", letztes_setzen([], "Einarbeiten"), None)
    pruefe("ein Treffer",
           letztes_setzen([labeled("Einarbeiten", "2026-09-01T00:00:00Z")],
                          "Einarbeiten"),
           "2026-09-01T00:00:00Z")
    pruefe("anderes Label stoert nicht",
           letztes_setzen([labeled("Untersuche", "2026-09-01T00:00:00Z"),
                           labeled("Einarbeiten", "2026-09-02T00:00:00Z")],
                          "Einarbeiten"),
           "2026-09-02T00:00:00Z")
    pruefe("das LETZTE Ereignis zaehlt (erneut gesetzt)",
           letztes_setzen([labeled("Einarbeiten", "2026-09-01T00:00:00Z"),
                           {"event": "unlabeled", "label": {"name": "Einarbeiten"}},
                           labeled("Einarbeiten", "2026-09-10T00:00:00Z")],
                          "Einarbeiten"),
           "2026-09-10T00:00:00Z")

    #  --- abgelaufen ---------------------------------------------------------
    jetzt = datetime.datetime(2026, 9, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)
    pruefe("kein Zeitpunkt -> nicht abgelaufen", abgelaufen(None, jetzt), False)
    pruefe("vor 4 Tagen -> nicht abgelaufen",
           abgelaufen("2026-09-16T12:00:01Z", jetzt), False)
    pruefe("genau 5 Tage -> noch nicht abgelaufen (strikt groesser)",
           abgelaufen("2026-09-15T12:00:00Z", jetzt), False)
    pruefe("vor 6 Tagen -> abgelaufen",
           abgelaufen("2026-09-14T12:00:00Z", jetzt), True)
    pruefe("eigene Frist beruecksichtigt",
           abgelaufen("2026-09-20T00:00:00Z", jetzt, frist_tage=1), False)
    pruefe("eigene Frist beruecksichtigt (ueberschritten)",
           abgelaufen("2026-09-18T00:00:00Z", jetzt, frist_tage=1), True)

    #  --- Anbindung an labels_lesen ------------------------------------------
    #  Genau die drei Label, die konventionen.md/labels.json als geschuetzt
    #  fuehrt - eine Regression, falls sich das mal veraendert, ohne dass hier
    #  jemand mitdenkt.
    geschuetzte = labels_lesen.geschuetzte_einzelne()
    for name in ("Einarbeiten", "Untersuche", "Gegenlese"):
        if name not in geschuetzte:
            fehler.append("echter Katalog: %r nicht geschuetzt - "
                          "veraltete_auftraege.py prueft es dann nicht mit" % name)

    gesamt = 4 + 6 + 3
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(selbsttest() if "--selbsttest" in sys.argv else main())
