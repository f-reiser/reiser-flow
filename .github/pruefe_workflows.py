#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prueft die Workflows dieses Repositories auf fuenf Zusagen, die sonst niemand
haelt - und die, wenn sie brechen, in FREMDEN Projekten wirken.

    1. Selbstbezug   Ein aufrufbarer Workflow bestimmt seinen eigenen Stand ueber
                     job.workflow_sha, nie ueber github.workflow_ref/-_sha.
    2. Verriegelung  Jeder Selbst-Checkout von f-reiser/reiser-flow nennt genau
                     diesen Stand als Ref.
    3. Fremder Code  Ein Workflow an pull_request_target checkt keinen "ref:" aus.
    4. Projektfrei   Ein aufrufbarer Workflow nennt keine Projektspezifika.
    5. Ausdruecke    Kein "${{ ... }}" im on:-Abschnitt.
    8. Berechtigung  Ein "permissions:"-Block nennt nur Scopes, die es gibt.

WARUM 1 UND 2 KEINE STILFRAGE SIND
    In einem per workflow_call aufgerufenen Workflow zeigen github.workflow_ref und
    github.workflow_sha auf den AUFRUFER, nicht auf die aufgerufene Datei - belegt in
    der Kontext-Dokumentation von GitHub und an einem Debug-Mitschnitt in
    github/gh-aw#24918. Ein Workflow, der sich damit selbst nachlaedt, holt also den
    Stand, den der Aufrufer zufaellig hat: bei einem Projekt auf main den main-Stand
    dieses Repositories - die Anpinnung des Aufrufers laeuft ins Leere. Steht der
    Aufrufer auf einem Feature-Branch, gibt es den Ref hier gar nicht und der
    Checkout scheitert.

    Richtig ist job.workflow_sha - "the commit SHA of the workflow file that defines
    the current job". Damit stammen Workflow, Skripte und Skills aus EINEM Commit,
    genau der Vertrag, den f-reiser/reiser-flow#1 begruendet.

WARUM 3 HIER STEHT
    pull_request_target laeuft mit Schreibtoken. Ein "ref:" auf den Kopf des Pull
    Request holte damit fremden Fork-Code auf einen Runner, der schreiben darf.
    Bisher war das nur eine Zeile Prosa in einer Checkliste (Abschnitt A in
    f-reiser/reiser-flow#12) - Prosa haelt niemanden auf.

WARUM 8 SO TEUER WAR
    Die Scopes von GITHUB_TOKEN sind eine geschlossene Liste. Steht in einem
    "permissions:"-Block etwas, das nicht dazugehoert, weist GitHub die GANZE Datei
    zurueck: Der Lauf hat keine Jobs, meldet nur "workflow file issue" und taucht im
    Verlauf als Fehlschlag mit dem Ereignis des Pushes auf - auch wenn die Datei gar
    nicht auf push hoert. Am 19.09.2026 stand so "workflows: write" in
    claude-aufgaben.yml und selbst-aufgaben.yml; der Cron-Lauf des Repositories lief
    daraufhin ueberhaupt nicht mehr, und die Pruefung hier blieb gruen
    (f-reiser/reiser-flow#43).

    Die Faehigkeit, ".github/workflows/*.yml" zu pushen, gibt es als Workflow-
    Berechtigung nicht. Sie haengt am Token selbst - ein Personal Access Token kann
    sie tragen, GITHUB_TOKEN nicht.

    Die Nummern 6 und 7 sind ausgelassen: Sie gehoeren zu Regeln, die noch als Pull
    Request offen sind (f-reiser/reiser-flow#24 und #22). So passen alle drei in
    beliebiger Reihenfolge nach main, ohne sich gegenseitig umzunummerieren.

Aufruf ohne Argument prueft dieses Repository, mit --selbsttest die Pruefung selbst.
"""
import io
import os
import re
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = ".github/workflows"

#  Der Aufrufer-Kontext, der in einem aufrufbaren Workflow das Falsche liefert.
FALSCHER_SELBSTBEZUG = ("github.workflow_ref", "github.workflow_sha",
                        "GITHUB_WORKFLOW_REF", "GITHUB_WORKFLOW_SHA")
RICHTIGER_SELBSTBEZUG = "job.workflow_sha"

DIESES_REPOSITORY = "f-reiser/reiser-flow"

#  Die beiden Arten, dieses Repository zu HOLEN: der "repository:"-Schluessel von
#  actions/checkout und eine Klon-Adresse. Bewusst nicht jede Erwaehnung des
#  Namens - er steht auch in Kommentaren und in Kommentartexten, die ein Workflow
#  an ein Issue schreibt, und dort ist er harmlos.
HOLT_DIESES_REPOSITORY = re.compile(
    r"repository\s*:\s*" + re.escape(DIESES_REPOSITORY) + r"\b"
    r"|github\.com[:/]" + re.escape(DIESES_REPOSITORY) + r"(\.git)?\b")

#  Woerter, die ein aufrufbarer Workflow nicht kennen darf. Sie stammen aus dem
#  Projekt, aus dem diese Workflows gekommen sind - taucht eines auf, ist beim
#  Herausloesen etwas liegengeblieben.
PROJEKTWOERTER = ("Makros", ".bas", ".xlsm", "openpyxl", "cp1252",
                  "Stoffverteilungsplan", "pruefe_alles")

#  Die Scopes, die GitHub in einem "permissions:"-Block kennt. Geschlossene Liste:
#  Was hier fehlt, macht die ganze Datei ungueltig. Kommt ein neuer Scope dazu,
#  gehoert er hierher - eine Zeile, gegen einen Ausfall des gesamten Repositories.
ERLAUBTE_BERECHTIGUNGEN = (
    "actions", "attestations", "checks", "contents", "deployments", "discussions",
    "id-token", "issues", "models", "packages", "pages", "pull-requests",
    "repository-projects", "security-events", "statuses",
)

BERECHTIGUNGSBLOCK = re.compile(r"^(\s*)permissions\s*:\s*$")
EINTRAG = re.compile(r"^(\s*)([A-Za-z][A-Za-z0-9-]*)\s*:")

#  Eine Zeile, die einen Schritt beginnt.
SCHRITT_BEGINN = re.compile(r"^\s*-\s+(uses|name|id|run|if)\s*:")

ZL = chr(10)


def ohne_kommentare(text):
    """Ganze Kommentarzeilen fallen weg - ersetzt durch Leerzeilen, damit die
    Zeilennummer eines Befundes weiter stimmt.

    Bewusst NICHT der Text hinter einem "#" mitten in der Zeile: In einem "run:"-Block
    ist das Shell-Code, kein Kommentar. Und die Richtung stimmt - diese Datei soll
    lieber einen Befund zu viel melden als einen zu wenig.
    """
    return ZL.join("" if z.lstrip().startswith("#") else z
                   for z in text.split(ZL))


def ist_aufrufbar(text):
    return re.search(r"^\s*workflow_call\s*:", text, re.M) is not None


def hoert_auf_fork_ereignis(text):
    return re.search(r"^\s*pull_request_target\s*:", text, re.M) is not None


def schritte(text):
    """Der Text, in Schritte zerlegt - je Schritt (erste Zeilennummer, Text).

    Der Kopf des Workflows vor dem ersten Schritt kommt als eigener Block mit heraus,
    damit keine Zeile ungeprueft bleibt.
    """
    zeilen = text.split(ZL)
    grenzen = [i for i, z in enumerate(zeilen) if SCHRITT_BEGINN.match(z)]
    if not grenzen or grenzen[0] != 0:
        grenzen = [0] + grenzen
    bloecke = []
    for k, anfang in enumerate(grenzen):
        ende = grenzen[k + 1] if k + 1 < len(grenzen) else len(zeilen)
        bloecke.append((anfang + 1, ZL.join(zeilen[anfang:ende])))
    return bloecke


def setzt_ref(block):
    return re.search(r"^\s*ref\s*:", block, re.M) is not None


def unbekannte_berechtigungen(text):
    """[(Zeilennummer, Scope)] fuer jeden Eintrag in einem "permissions:"-Block,
    den GitHub nicht kennt.

    Ein Block endet, sobald eine Zeile wieder hoechstens so weit eingerueckt ist
    wie das "permissions:" selbst. "permissions: read-all" auf einer Zeile ist
    kein Block und wird nicht angefasst.
    """
    zeilen = text.split(ZL)
    gefunden = []
    i = 0
    while i < len(zeilen):
        kopf = BERECHTIGUNGSBLOCK.match(zeilen[i])
        if not kopf:
            i += 1
            continue
        tiefe = len(kopf.group(1))
        i += 1
        while i < len(zeilen):
            z = zeilen[i]
            if not z.strip():
                i += 1
                continue
            eintrag = EINTRAG.match(z)
            if not eintrag or len(eintrag.group(1)) <= tiefe:
                break
            if eintrag.group(2) not in ERLAUBTE_BERECHTIGUNGEN:
                gefunden.append((i + 1, eintrag.group(2)))
            i += 1
    return gefunden


def ausloeser_block(text):
    """Der "on:"-Abschnitt - von "on:" bis zum naechsten Schluessel ganz links."""
    zeilen = text.split(ZL)
    anfang = None
    for i, z in enumerate(zeilen):
        if re.match(r"^on\s*:", z):
            anfang = i
            break
    if anfang is None:
        return 0, ""
    for j in range(anfang + 1, len(zeilen)):
        if zeilen[j].strip() and not zeilen[j][:1].isspace():
            return anfang + 1, ZL.join(zeilen[anfang:j])
    return anfang + 1, ZL.join(zeilen[anfang:])


def befunde(name, roh):
    """Liste der Befunde zu einem Workflow - leer heisst gruen."""
    text = ohne_kommentare(roh)
    aufrufbar = ist_aufrufbar(text)
    fork = hoert_auf_fork_ereignis(text)
    gefunden = []

    def melde(zeile, was):
        gefunden.append("%s:%d: %s" % (name, zeile, was))

    #  GitHub kennt in "on:" ueberhaupt keine Ausdruecke, wertet ein "${{ ... }}"
    #  dort aber trotzdem aus - und weist die GANZE Datei zurueck, wenn es nicht
    #  aufgeht. Der Lauf hat dann keine Jobs und meldet nur "workflow file issue",
    #  ohne die Stelle zu nennen. Genau so ist es am 18.09.2026 passiert: In der
    #  description eines workflow_call-Eingabewertes stand ein Beispiel mit
    #  "needs.<job>.result", gemeint als Text.
    for zeile, scope in unbekannte_berechtigungen(text):
        melde(zeile, "%r ist keine Berechtigung, die GitHub kennt - ein "
                     "unbekannter Schluessel macht die ganze Datei ungueltig, "
                     "und der Lauf meldet dann nur 'workflow file issue'" % scope)

    zeile, aus = ausloeser_block(text)
    if "${{" in aus:
        melde(zeile, "Ausdruck ${{ ... }} im on:-Abschnitt - dort gibt es keine "
                     "Ausdruecke, und GitHub weist die ganze Datei zurueck")

    for zeile, block in schritte(text):
        if aufrufbar:
            for falsch in FALSCHER_SELBSTBEZUG:
                if falsch in block:
                    melde(zeile, "%s zeigt in einem aufrufbaren Workflow auf den "
                                 "AUFRUFER - %s verwenden"
                          % (falsch, RICHTIGER_SELBSTBEZUG))

            if HOLT_DIESES_REPOSITORY.search(block) \
                    and RICHTIGER_SELBSTBEZUG not in block:
                melde(zeile, "holt %s ohne %s - der Stand ist nicht verriegelt"
                      % (DIESES_REPOSITORY, RICHTIGER_SELBSTBEZUG))

            for wort in PROJEKTWOERTER:
                if wort in block:
                    melde(zeile, "projektspezifisch: %r gehoert nicht in einen "
                                 "aufrufbaren Workflow" % wort)

        if fork and "actions/checkout" in block and setzt_ref(block):
            melde(zeile, "actions/checkout mit 'ref:' in einem Workflow an "
                         "pull_request_target - fremder Fork-Code auf einem Runner "
                         "mit Schreibtoken")

    return gefunden


def pruefe(wurzel=WURZEL):
    ordner = os.path.join(wurzel, ".github", "workflows")
    if not os.path.isdir(ordner):
        return ["%s gibt es nicht" % WORKFLOWS]
    dateien = sorted(d for d in os.listdir(ordner)
                     if d.endswith(".yml") or d.endswith(".yaml"))
    if not dateien:
        return ["keine Workflows in %s" % WORKFLOWS]
    alle = []
    for d in dateien:
        with io.open(os.path.join(ordner, d), encoding="utf-8") as f:
            alle.extend(befunde(WORKFLOWS + "/" + d, f.read()))
    return alle


#  ----------------------------------------------------------------- Selbsttest

#  Ein aufrufbarer Workflow, wie er sein soll. Die Mutationen unten aendern je eine
#  Stelle daran - schlaegt danach keine Pruefung an, prueft sie nichts.
MUSTER = """name: Muster
on:
  workflow_call:
    inputs:
      wert:
        type: string
jobs:
  tun:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          repository: f-reiser/reiser-flow
          ref: ${{ job.workflow_sha }}
          path: _reiser-flow
      - name: Etwas tun
        run: python3 _reiser-flow/.github/skripte/etwas.py
"""

#  Ein Workflow mit Berechtigungen auf beiden Ebenen - oben am Workflow, unten am
#  Job. Beide muessen geprueft werden; der Ausfall vom 19.09.2026 sass oben.
RECHTE_MUSTER = """name: Rechte
on:
  workflow_call:
jobs:
  tun:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      id-token: write
    steps:
      - name: Etwas tun
        run: echo hallo
"""

FORK_MUSTER = """name: Fork
on:
  pull_request_target:
    types: [labeled]
jobs:
  tun:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - name: Etwas tun
        run: echo hallo
"""


def selbsttest():
    fehler = []

    def pruefe_text(was, name, text, erwartet_treffer):
        b = befunde(name, text)
        if bool(b) != erwartet_treffer:
            fehler.append("%s: %d Befunde, erwartet waren %s (%s)"
                          % (was, len(b), "welche" if erwartet_treffer else "keine",
                             "; ".join(b) or "-"))

    #  Gruen: die unveraenderten Muster.
    pruefe_text("Muster unveraendert", "muster.yml", MUSTER, False)
    pruefe_text("Fork-Muster unveraendert", "fork.yml", FORK_MUSTER, False)

    #  Mutation 1: Selbstbezug ueber den Aufrufer-Kontext.
    for falsch in FALSCHER_SELBSTBEZUG:
        pruefe_text("Mutation Selbstbezug %s" % falsch, "muster.yml",
                    MUSTER.replace("job.workflow_sha", falsch), True)

    #  Mutation 2: Selbst-Checkout ohne jede Verriegelung.
    pruefe_text("Mutation Ref entfernt", "muster.yml",
                MUSTER.replace("          ref: ${{ job.workflow_sha }}" + ZL, ""),
                True)

    #  Mutation 3: fremder Fork-Code auf einen schreibenden Runner.
    pruefe_text("Mutation ref bei pull_request_target", "fork.yml",
                FORK_MUSTER.replace(
                    "      - uses: actions/checkout@v7",
                    "      - uses: actions/checkout@v7" + ZL
                    + "        with:" + ZL
                    + "          ref: ${{ github.event.pull_request.head.sha }}"),
                True)

    #  Mutation 4: je ein Projektwort, einzeln.
    for wort in PROJEKTWOERTER:
        pruefe_text("Mutation Projektwort %r" % wort, "muster.yml",
                    MUSTER.replace("run: python3", "run: %s python3" % wort), True)

    #  Gegenprobe zu 1/2/4: In einem NICHT aufrufbaren Workflow ist all das erlaubt -
    #  dort meint github.workflow_ref die Datei selbst, und die eigene CI darf ihr
    #  eigenes Projekt beim Namen nennen.
    eigener = MUSTER.replace("  workflow_call:" + ZL
                             + "    inputs:" + ZL
                             + "      wert:" + ZL
                             + "        type: string", "  push:")
    pruefe_text("nicht aufrufbar: Selbstbezug erlaubt", "eigen.yml",
                eigener.replace("job.workflow_sha", "github.workflow_sha"), False)
    pruefe_text("nicht aufrufbar: Projektwort erlaubt", "eigen.yml",
                eigener.replace("run: python3", "run: Makros python3"), False)

    #  Gegenprobe zu 3: ein "ref:" ist nur an pull_request_target gefaehrlich.
    pruefe_text("ohne pull_request_target: ref erlaubt", "eigen.yml",
                eigener.replace("          path: _reiser-flow",
                                "          path: _reiser-flow" + ZL
                                + "          ref: irgendwas"), False)

    #  Regel 8, gruen: nur Scopes, die es gibt - am Job wie am Workflow.
    pruefe_text("Rechte-Muster unveraendert", "rechte.yml", RECHTE_MUSTER, False)

    #  Mutation 7: genau der Ausfall vom 19.09.2026.
    pruefe_text("Mutation unbekannte Berechtigung", "rechte.yml",
                RECHTE_MUSTER.replace("      id-token: write",
                                      "      workflows: write"), True)

    #  Auch oben am Workflow, nicht nur am Job.
    pruefe_text("Mutation am Workflow statt am Job", "rechte.yml",
                RECHTE_MUSTER.replace("jobs:",
                                      "permissions:" + ZL
                                      + "  workflows: write" + ZL + "jobs:"),
                True)

    #  Gegenprobe zu 8, erste Verengung: Der Block endet mit der Einrueckung.
    #  "jobs:" oder "steps:" danach sind keine Berechtigungen.
    if unbekannte_berechtigungen(RECHTE_MUSTER):
        fehler.append("Regel 8: Schluessel ausserhalb des Blocks mitgezaehlt (%r)"
                      % (unbekannte_berechtigungen(RECHTE_MUSTER),))

    #  Gegenprobe zu 8, zweite Verengung: "permissions: read-all" ist kein Block.
    pruefe_text("Kurzform read-all ist kein Block", "rechte.yml",
                RECHTE_MUSTER.replace("    permissions:" + ZL
                                      + "      contents: write" + ZL
                                      + "      id-token: write",
                                      "    permissions: read-all"), False)

    #  Ein Kommentar, der die falsche Schreibweise ERKLAERT, darf nicht anschlagen -
    #  sonst laesst sich der Grund nicht mehr aufschreiben.
    pruefe_text("Kommentar mit der falschen Schreibweise", "muster.yml",
                MUSTER.replace(
                    "      - name: Etwas tun",
                    "      #  github.workflow_ref waere hier der Aufrufer." + ZL
                    + "      - name: Etwas tun"), False)

    #  Der Zerleger selbst. Ohne diese Pruefung koennte ein Ref aus Schritt A einen
    #  Schritt B verriegeln, der gar nicht verriegelt ist.
    anzahl = len(schritte(MUSTER))
    if anzahl != 3:
        fehler.append("schritte(): %d Bloecke statt 3 (Kopf + zwei Schritte)" % anzahl)

    #  Genau dieser Fall: Schritt A ist verriegelt, ein ZWEITER Selbstbezug nicht.
    #  Beide Klon-Schreibweisen, damit die Verengung auf "holen" nicht die eine
    #  oder die andere durchlaesst.
    for adresse in ("https://github.com/f-reiser/reiser-flow.git",
                    "git@github.com:f-reiser/reiser-flow.git"):
        pruefe_text("zweiter Selbstbezug ohne Verriegelung (%s)" % adresse,
                    "muster.yml",
                    MUSTER + ("      - name: Nochmal holen" + ZL
                              + "        run: git clone " + adresse + ZL), True)

    #  Gegenprobe zur Verengung: Der blosse NAME des Repositories ist harmlos. Er
    #  steht in Kommentartexten, die ein Workflow an ein Issue schreibt - eine
    #  Pruefung, die darauf anspringt, zwingt dazu, solche Texte zu verstuemmeln.
    pruefe_text("Name in einem Meldungstext", "muster.yml",
                MUSTER.replace(
                    "        run: python3",
                    "        run: echo 'durchgesetzt von f-reiser/reiser-flow'"
                    + ZL + "        shell: bash" + ZL + "        #x: python3"),
                False)

    #  Mutation 5: ein Ausdruck im on:-Abschnitt. Genau der Fehler vom 18.09.2026,
    #  als Beispiel in der description eines Eingabewertes.
    pruefe_text("Mutation Ausdruck in der description", "muster.yml",
                MUSTER.replace("        type: string",
                               "        description: etwa ${{ needs.x.result }}"
                               + ZL + "        type: string"), True)

    #  Gegenprobe: derselbe Text als Kommentar oder weiter unten im Job ist
    #  richtig und haeufig - "${{ job.workflow_sha }}" steht schon im Muster.
    pruefe_text("Ausdruck unterhalb von on: ist erlaubt", "muster.yml",
                MUSTER.replace("    inputs:",
                               "    # Beispiel: ${{ needs.pruefung.result }}" + ZL
                               + "    inputs:"), False)

    #  Der Zerleger des on:-Abschnitts: Er darf nicht bis in den Job hineinreichen,
    #  sonst meldete jedes "${{ }}" in irgendeinem Schritt einen Befund.
    _, aus = ausloeser_block(MUSTER)
    if "runs-on" in aus or "workflow_call" not in aus:
        fehler.append("ausloeser_block(): falsch abgegrenzt (%r)" % aus[:80])

    gesamt = (2 + len(FALSCHER_SELBSTBEZUG) + 1 + 1 + len(PROJEKTWOERTER)
              + 3 + 1 + 1 + 2 + 1 + 2 + 1 + 5)
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


def main():
    gefunden = pruefe()
    for f in gefunden:
        print("FEHLER: " + f)
    if gefunden:
        print("%d Befund(e)." % len(gefunden))
        return 1
    print("Workflows in Ordnung.")
    return 0


if __name__ == "__main__":
    sys.exit(selbsttest() if "--selbsttest" in sys.argv else main())
