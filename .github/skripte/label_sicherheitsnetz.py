#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sicherheitsnetz: wiederholt die Pruefungen aus label-waechter.yml (Berechtigung,
Scoped-Label-Exklusivitaet) zu Beginn von claude-aufgaben.yml, bevor die gelesenen
Steuerlabel fuer Modellwahl und Aufwand verwendet werden (siehe modellwahl.py).

label-waechter.yml reagiert auf das Ereignis "labeled" und nimmt ein unberechtigt
gesetztes oder im selben Scope doppelt besetztes Steuerlabel sofort zurueck. Bricht
dieser Lauf zwischendurch ab (Fehler, Timeout, Ausfall), bleibt das Label bestehen,
und claude-aufgaben.yml las es bisher ungeprueft (f-reiser/reiser-flow#6). Dieses
Skript ruft dieselben drei Bausteine (geschuetzt.py, berechtigt.py, scope_ausschluss.py
bzw. dessen scoped_labels.py) noch einmal auf - keine Kopie ihrer Regeln, nur ein
zweiter Aufruf.

Liest labels.txt (Format wie modellwahl.py: "<nr>\tLabel,Label,..."), entfernt jedes
geschuetzte Label mit einem offenen Befund auf GitHub UND aus der Datei selbst -
modellwahl.py sieht die Datei erst danach und damit nur noch rechtmaessige Vorgaben.

WOHER "WER HAT GESETZT" KOMMT
    Anders als label-waechter.yml (das Ereignis nennt Label und Absender direkt)
    prueft dieses Skript den bestehenden Zustand nachtraeglich. Wer ein noch
    vorhandenes Label zuletzt gesetzt hat, steht in der Issue-Events-API
    (repos/{repo}/issues/{nr}/events) - zustand_aus_ereignissen() wertet sie aus.
    Laesst sich der Setzer nicht ermitteln, gilt das Label als nicht berechtigt
    gesetzt: eine erfundene Berechtigung waere schlimmer als eine verworfene Vorgabe.
"""
import io
import json
import os
import subprocess
import sys
import tempfile

import berechtigt
import geschuetzt
import labels_lesen
import modellwahl
import scoped_labels


def zustand_aus_ereignissen(ereignisse):
    """label -> (Index des letzten 'labeled'-Ereignisses, Login des Setzenden).

    Ein spaeter folgendes 'unlabeled' nimmt den Eintrag wieder heraus - das Label
    ist dann aktuell nicht mehr gesetzt und taucht folgerichtig nicht mehr auf.
    """
    stand = {}
    for i, e in enumerate(ereignisse):
        name = (e.get("label") or {}).get("name")
        if not name:
            continue
        if e.get("event") == "labeled":
            stand[name] = (i, (e.get("actor") or {}).get("login"))
        elif e.get("event") == "unlabeled":
            stand.pop(name, None)
    return stand


def unautorisierte(labels, rechte):
    """Geschuetzte Label aus 'labels', deren Setzer laut 'rechte' (label -> Recht
    oder None) nicht berechtigt war - siehe berechtigt.darf_setzen()."""
    return [l for l in labels
            if geschuetzt.geschuetzt(l) and not berechtigt.darf_setzen(rechte.get(l))]


def scope_konflikte(labels, reihenfolge):
    """Geschuetzte Label aus 'labels', die einen Geschwisterkonflikt im selben Scope
    haben - alle bis auf das zuletzt gesetzte je Scope (reihenfolge: label -> Index,
    hoeher = spaeter; ein fehlender Eintrag gilt als am fruehesten gesetzt)."""
    gruppen = {}
    for l in labels:
        if not geschuetzt.geschuetzt(l):
            continue
        s = scoped_labels.scope(l)
        if s is None:
            continue
        gruppen.setdefault(s, []).append(l)

    entfernen = []
    for kandidaten in gruppen.values():
        if len(kandidaten) < 2:
            continue
        behalten = max(kandidaten, key=lambda l: reihenfolge.get(l, -1))
        entfernen.extend(scoped_labels.geschwister_im_scope(kandidaten, behalten))
    return entfernen


#  ------------------------------------------------------------------- API-Zugriff

def ereignisse(repo, nr):
    lauf = subprocess.run(
        ["gh", "api", "--paginate", "repos/%s/issues/%s/events" % (repo, nr)],
        capture_output=True, text=True,
    )
    if lauf.returncode != 0:
        return []
    return json.loads(lauf.stdout or "[]")


def recht_von(repo, wer):
    lauf = subprocess.run(
        ["gh", "api", "repos/%s/collaborators/%s/permission" % (repo, wer),
         "--jq", ".permission"],
        capture_output=True, text=True,
    )
    return lauf.stdout.strip() if lauf.returncode == 0 else None


def entfernen(repo, nr, label):
    subprocess.run(
        ["gh", "api", "--method", "DELETE",
         "repos/%s/issues/%s/labels/%s" % (repo, nr, label)],
        check=True,
    )


def kommentieren(repo, nr, label, grund):
    text = (
        "Sicherheitsnetz in `claude-aufgaben.yml`: `%s` wurde automatisch entfernt "
        "(%s). `label-waechter.yml` haette das eigentlich schon zurueckgenommen - "
        "vermutlich ist der Lauf dazwischen abgebrochen.\n"
    ) % (label, grund)
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                      encoding="utf-8") as f:
        f.write(text)
        pfad = f.name
    subprocess.run(
        ["gh", "api", "--method", "POST", "repos/%s/issues/%s/comments" % (repo, nr),
         "-F", "body=@%s" % pfad],
        check=True,
    )


#  ------------------------------------------------------------------------ main

def schreiben(pfad, vorgaenge):
    with io.open(pfad, "w", encoding="utf-8", newline="") as f:
        for nr, labels in vorgaenge:
            f.write("%s\t%s\n" % (nr, ",".join(labels)))


#  Aus labels.json, nicht noch einmal aufgezaehlt: Ein drittes Auftragslabel
#  soll an genau einer Stelle gepflegt werden (f-reiser/reiser-flow#23).
AUFTRAGSLABEL = tuple(labels_lesen.auftragslabel())


def ohne_auftragslabel(bereinigt):
    """Nummern (als str) aus 'bereinigt' (wie von main() geschrieben), bei
    denen nach der Bereinigung kein Auftragslabel mehr uebrig ist.

    labels.txt allein reicht nicht: zuordnung.py waehlt einen Vorgang anhand
    von nummern.txt/kandidaten.txt, die unabhaengig davon entstehen - ein
    hier entferntes "Einarbeiten" wuerde sonst trotzdem bearbeitet
    (f-reiser/reiser-flow#6, Befund von ReiserFlorian)."""
    return {nr for nr, labels in bereinigt
            if not any(l in labels for l in AUFTRAGSLABEL)}


#  Der Workflow, in den dieses Skript eingehaengt gehoert. Dass es aufgerufen wird
#  und WANN, prueft der Selbsttest unten mit: Ein erster Anlauf lieferte den
#  Baustein fertig und getestet ab, ohne ihn zu verdrahten - er lag fertig da und
#  tat nichts (f-reiser/reiser-flow#6). Die Pruefung steht hier und nicht in
#  pruefe_workflows.py, weil sie nicht den Workflow prueft, sondern die Zusage
#  dieses Skripts, an der richtigen Stelle zu wirken.
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(WURZEL, "workflows", "claude-aufgaben.yml")


def reihenfolge_im_workflow(text):
    """(Stelle des Sicherheitsnetz-Aufrufs, Stelle des zuordnung.py-Aufrufs) im
    Text - je -1, wo der Aufruf fehlt.

    Ohne Kommentarzeilen, und das ist nicht kosmetisch: Der Kommentar ueber dem
    Aufruf begruendet gerade die Reihenfolge und nennt dabei zuordnung.py zuerst.
    Gesucht wird der Aufruf, nicht seine Erklaerung.
    """
    t = chr(10).join(z for z in text.split(chr(10))
                     if not z.lstrip().startswith("#"))
    return t.find("label_sicherheitsnetz.py"), t.find("zuordnung.py")


def filtere_zeilen(pfad, entfallen):
    """Entfernt aus 'pfad' jede Zeile, deren erste (tabgetrennte) Spalte in
    'entfallen' steht - passt sowohl auf nummern.txt (nur die Nummer) als
    auch auf kandidaten.txt (Nummer, updatedAt, Titel)."""
    if not entfallen:
        return
    try:
        with io.open(pfad, encoding="utf-8") as f:
            zeilen = [z.rstrip(chr(10)).rstrip(chr(13)) for z in f if z.strip()]
    except OSError:
        return
    behalten = [z for z in zeilen if z.split(chr(9), 1)[0].strip() not in entfallen]
    with io.open(pfad, "w", encoding="utf-8", newline="") as f:
        for z in behalten:
            f.write(z + "\n")


def main():
    repo = os.environ["REPO"]
    bereinigt = []

    for nr, labels in modellwahl.lies("labels.txt"):
        aktuell = list(labels)
        stand = zustand_aus_ereignissen(ereignisse(repo, nr))
        reihenfolge = {l: i for l, (i, _) in stand.items()}

        rechte = {}
        for label in aktuell:
            if not geschuetzt.geschuetzt(label):
                continue
            wer = stand.get(label, (None, None))[1]
            rechte[label] = recht_von(repo, wer) if wer else None

        zu_entfernen = {}
        for label in unautorisierte(aktuell, rechte):
            wer = stand.get(label, (None, None))[1]
            zu_entfernen[label] = "gesetzt von %s ohne Admin- oder Maintainer-Recht" \
                % (wer or "einem nicht ermittelbaren Account")

        #  Nur unter den noch verbleibenden (nicht schon unautorisiert entfernten)
        #  Labeln nach einem Geschwisterkonflikt suchen - sonst zaehlte ein bereits
        #  aussortiertes Label noch als Konfliktpartner mit.
        uebrig = [l for l in aktuell if l not in zu_entfernen]
        for label in scope_konflikte(uebrig, reihenfolge):
            zu_entfernen[label] = "Geschwisterkonflikt im selben Scope"

        for label, grund in zu_entfernen.items():
            print("Sicherheitsnetz: #%s %s (%s)" % (nr, label, grund))
            entfernen(repo, nr, label)
            kommentieren(repo, nr, label, grund)
            aktuell.remove(label)

        bereinigt.append((nr, aktuell))

    schreiben("labels.txt", bereinigt)

    entfallen = ohne_auftragslabel(bereinigt)
    filtere_zeilen("nummern.txt", entfallen)
    filtere_zeilen("kandidaten.txt", entfallen)


#  --------------------------------------------------------------------- Selbsttest

def selbsttest():
    fehler = []

    def pruefe(name, ist, erwartet):
        if sorted(ist) != sorted(erwartet):
            fehler.append("%s: %r statt %r" % (name, ist, erwartet))

    #  --- zustand_aus_ereignissen -------------------------------------------
    pruefe(
        "einfaches Setzen",
        list(zustand_aus_ereignissen(
            [{"event": "labeled", "label": {"name": "Modell::Opus"},
              "actor": {"login": "florian"}}]
        ).items()),
        [("Modell::Opus", (0, "florian"))],
    )
    pruefe(
        "zurueckgenommen taucht nicht mehr auf",
        list(zustand_aus_ereignissen([
            {"event": "labeled", "label": {"name": "Modell::Opus"},
             "actor": {"login": "florian"}},
            {"event": "unlabeled", "label": {"name": "Modell::Opus"},
             "actor": {"login": "bot"}},
        ]).items()),
        [],
    )
    pruefe(
        "erneut gesetzt zaehlt der letzte Setzer",
        list(zustand_aus_ereignissen([
            {"event": "labeled", "label": {"name": "Modell::Opus"},
             "actor": {"login": "florian"}},
            {"event": "unlabeled", "label": {"name": "Modell::Opus"},
             "actor": {"login": "bot"}},
            {"event": "labeled", "label": {"name": "Modell::Opus"},
             "actor": {"login": "jemand-fremdes"}},
        ]).items()),
        [("Modell::Opus", (2, "jemand-fremdes"))],
    )
    pruefe(
        "andere Label und Ereignisse stoeren nicht",
        list(zustand_aus_ereignissen([
            {"event": "commented"},
            {"event": "labeled", "label": {"name": "Einarbeiten"},
             "actor": {"login": "florian"}},
        ]).items()),
        [("Einarbeiten", (1, "florian"))],
    )
    pruefe("leere Ereignisliste", list(zustand_aus_ereignissen([]).items()), [])

    #  --- unautorisierte -----------------------------------------------------
    pruefe(
        "berechtigter Setzer bleibt unangetastet",
        unautorisierte(["Modell::Opus"], {"Modell::Opus": "admin"}),
        [],
    )
    pruefe(
        "unberechtigter Setzer wird gemeldet",
        unautorisierte(["Modell::Opus"], {"Modell::Opus": "write"}),
        ["Modell::Opus"],
    )
    pruefe(
        "nicht ermittelbarer Setzer gilt als unberechtigt",
        unautorisierte(["Aufwand::maximal"], {"Aufwand::maximal": None}),
        ["Aufwand::maximal"],
    )
    pruefe(
        "ungeschuetzte Label bleiben aussen vor, egal welches Recht",
        unautorisierte(["Dokumentation"], {}),
        [],
    )
    pruefe(
        "gemischt: nur das unberechtigte fliegt",
        unautorisierte(
            ["Dokumentation", "Modell::Opus", "Aufwand::niedrig"],
            {"Modell::Opus": "admin", "Aufwand::niedrig": "write"},
        ),
        ["Aufwand::niedrig"],
    )

    #  --- scope_konflikte ------------------------------------------------------
    pruefe(
        "kein Konflikt ohne Geschwister",
        scope_konflikte(["Modell::Opus", "Aufwand::hoch"], {}),
        [],
    )
    pruefe(
        "Konflikt: das spaeter gesetzte bleibt",
        scope_konflikte(
            ["Modell::Opus", "Modell::Sonnet"],
            {"Modell::Opus": 0, "Modell::Sonnet": 3},
        ),
        ["Modell::Opus"],
    )
    pruefe(
        "ohne Reihenfolge-Eintrag faellt eine feste, aber deterministische Wahl",
        scope_konflikte(["Modell::Opus", "Modell::Sonnet"], {}),
        ["Modell::Sonnet"],
    )
    pruefe(
        "drei Werte im selben Scope: nur der letzte bleibt",
        scope_konflikte(
            ["Aufwand::niedrig", "Aufwand::hoch", "Aufwand::maximal"],
            {"Aufwand::niedrig": 0, "Aufwand::hoch": 5, "Aufwand::maximal": 2},
        ),
        ["Aufwand::niedrig", "Aufwand::maximal"],
    )
    pruefe(
        "ungeschuetzte und nicht gescopte Label nie betroffen",
        scope_konflikte(["Einarbeiten", "Untersuche", "Dokumentation"], {}),
        [],
    )
    pruefe(
        "verschiedene Scopes stoeren sich nicht",
        scope_konflikte(["Modell::Opus", "v::4", "v::5"], {"v::4": 1, "v::5": 2}),
        ["v::4"],
    )

    #  --- schreiben/lesen bleiben zueinander kompatibel ------------------------
    d = tempfile.mkdtemp()
    pfad = os.path.join(d, "labels.txt")
    schreiben(pfad, [("31", ["Einarbeiten", "Modell::Opus"]), ("7", [])])
    gelesen = modellwahl.lies(pfad)
    if gelesen != [("31", ["Einarbeiten", "Modell::Opus"]), ("7", [])]:
        fehler.append("schreiben()/lies(): %r" % (gelesen,))

    #  --- ohne_auftragslabel ---------------------------------------------------
    pruefe(
        "Auftragslabel weg zaehlt, anderes Label bleibend nicht",
        ohne_auftragslabel(
            [("31", ["Modell::Opus"]), ("7", ["Einarbeiten", "Modell::Opus"])]
        ),
        {"31"},
    )
    pruefe(
        "Untersuche zaehlt wie Einarbeiten",
        ohne_auftragslabel([("9", ["Untersuche"])]),
        set(),
    )
    pruefe("nichts entfallen bei leerer Liste", ohne_auftragslabel([]), set())

    #  --- filtere_zeilen: nummern.txt und kandidaten.txt bleiben in Schritt ---
    #  mit labels.txt, sonst waehlt zuordnung.py einen Vorgang, dem gerade das
    #  Auftragslabel entzogen wurde (der eigentliche Befund zu #6).
    d2 = tempfile.mkdtemp()
    nummern_pfad = os.path.join(d2, "nummern.txt")
    io.open(nummern_pfad, "w", encoding="utf-8", newline="").write(
        "7" + chr(10) + "31" + chr(10))
    filtere_zeilen(nummern_pfad, {"31"})
    pruefe("nummern.txt bereinigt",
           [z.strip() for z in io.open(nummern_pfad, encoding="utf-8")],
           ["7"])

    kandidaten_pfad = os.path.join(d2, "kandidaten.txt")
    io.open(kandidaten_pfad, "w", encoding="utf-8", newline="").write(
        "7" + chr(9) + "2026-01-01" + chr(9) + "Titel A" + chr(10) +
        "31" + chr(9) + "2026-01-02" + chr(9) + "Titel B" + chr(10))
    filtere_zeilen(kandidaten_pfad, {"31"})
    pruefe("kandidaten.txt bereinigt",
           [z.strip() for z in io.open(kandidaten_pfad, encoding="utf-8")],
           ["7" + chr(9) + "2026-01-01" + chr(9) + "Titel A"])

    fehlend_pfad = os.path.join(d2, "fehlt.txt")
    filtere_zeilen(fehlend_pfad, {"1"})  # darf nicht abstuerzen

    #  --- die Verdrahtung selbst ----------------------------------------------
    #  Die Reihenfolge ist der eigentliche Fallstrick: Steht der Aufruf hinter
    #  zuordnung.py, hat die den Vorgang laengst anhand der ungeprueften Dateien
    #  ausgewaehlt, und das Netz haengt hinter dem Sprung.
    try:
        yml = io.open(WORKFLOW, encoding="utf-8").read()
    except OSError as e:
        fehler.append("claude-aufgaben.yml nicht lesbar: %s" % e)
    else:
        netz, zuordnung = reihenfolge_im_workflow(yml)
        if netz < 0:
            fehler.append("claude-aufgaben.yml ruft label_sicherheitsnetz.py "
                          "nicht auf - der Baustein haengt nicht")
        elif zuordnung < 0:
            fehler.append("claude-aufgaben.yml ruft zuordnung.py nicht mehr auf "
                          "- die Reihenfolge laesst sich nicht mehr pruefen")
        elif netz > zuordnung:
            fehler.append("label_sicherheitsnetz.py laeuft erst nach zuordnung.py "
                          "- die Auswahl steht dann schon fest")

    #  Und die Pruefung selbst gegen einen Text, der sie ausloesen MUSS.
    pruefe("Reihenfolge erkannt", list(reihenfolge_im_workflow(
        "a zuordnung.py b label_sicherheitsnetz.py")), [17, 2])
    pruefe("fehlender Aufruf erkannt",
           list(reihenfolge_im_workflow("nur zuordnung.py")), [-1, 4])
    #  Genau der Fall, der die Pruefung beim ersten Lauf falsch rot machte.
    pruefe("Kommentar ueber dem Aufruf zaehlt nicht mit",
           list(reihenfolge_im_workflow(
               "  #  vor zuordnung.py" + chr(10)
               + "  label_sicherheitsnetz.py" + chr(10)
               + "  zuordnung.py")),
           [2, 29])

    gesamt = 27
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(selbsttest() if "--selbsttest" in sys.argv else main())
