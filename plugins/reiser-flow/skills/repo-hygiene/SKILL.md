---
name: repo-hygiene
description: >
  Entscheidet, was in ein Git-Repository gehört und was nicht, über eine Whitelist-.gitignore
  statt einer Blacklist — plus die Kontrollen vor dem ersten Commit (Zugangsdaten,
  personenbezogene Daten in Binärdateien, Zeilenenden) und das Vorgehen, wenn schon etwas
  Falsches im Repository gelandet ist. Nutze diesen Skill unbedingt, sobald es um `git init`,
  den ersten Commit, eine `.gitignore` oder `.gitattributes` oder das Veröffentlichen eines
  bestehenden lokalen Ordners auf GitHub/GitLab geht — und auch dann, wenn nur beiläufig
  gefragt wird, ob eine Datei, ein Ordner, eine Excel-/Word-Datei oder ein Testbericht „mit
  ins Repo soll". Ebenso bei jedem Commit, der Binärdateien, Office-Dokumente, Exporte oder
  Diagnoseausgaben enthält; wenn eine Datei entgegen der Erwartung nicht im Repository landet
  oder ignoriert wird; und dringend, wenn Zugangsdaten, Schlüssel oder personenbezogene Daten
  bereits committet oder gepusht wurden.
---

# Was gehört ins Repository?

## Warum es diesen Skill gibt

Ein Repository vergisst nichts. Was einmal committet und gepusht ist, steht in der
Historie — auch nach einem `git rm` im nächsten Commit.

Deshalb ist der Zeitpunkt **vor** dem ersten Commit der einzige billige. Alles hier zielt
darauf, diesen Moment zu nutzen statt ihn zu verpassen. Ist er verpasst: Abschnitt
„Es ist schon passiert".

## Die Grundasymmetrie

In den meisten Projekten mit einem Menschen und einem Modell gilt eine erstaunlich
verlässliche Faustregel:

- **Erzeugter Quelltext gehört ins Repository.** Genau dafür ist es da — Historie,
  Nachvollziehbarkeit, Änderungsverfolgung. Und die Quelle dieser Dateien ist ohnehin
  das Modell, also gibt es keine zweite Wahrheit, die verloren gehen könnte.
- **Was der Mensch beisteuert, gehört meistens nicht hinein.** Es ist typischerweise
  schon mit echten Daten gefüllt: fertige Dokumente, Exporte, Diagnoseberichte,
  Messreihen, Kundendaten, Screenshots aus dem Produktivsystem.

Das ist eine Faustregel, kein Gesetz — der Mensch liefert auch Konfiguration, Schemata
oder Testdaten, die sehr wohl hineingehören. Aber sie sagt dir, in welche Richtung du im
Zweifel fragen solltest.

## Whitelist statt Blacklist

Die übliche `.gitignore` ist eine Blacklist: alles ist drin, außer man schließt es aus.
Das ist die falsche Richtung, denn ein Versehen fällt in die riskante Richtung — eine
Datei, an die niemand gedacht hat, landet im Repository.

Dreh es um: erst alles ignorieren, dann gezielt zulassen.

```gitignore
# Erst alles ignorieren.
*

# Verzeichnisse muessen durchlaufbar bleiben, sonst greift keine der Ausnahmen
# darunter - Git steigt in ein ignoriertes Verzeichnis gar nicht erst hinab.
!*/

# --- Was hinein soll -------------------------------------------------
!.gitignore
!.gitattributes
!README.md
!src/**
!docs/**
!.github/**

# --- Ausnahmen von den Ausnahmen -------------------------------------
src/secrets.py
**/__pycache__/
```

Drei Dinge, an denen das sonst scheitert:

1. **`!*/` nicht vergessen.** Ohne diese Zeile steigt Git gar nicht erst in die
   Unterverzeichnisse hinab, und keine einzige Ausnahme darunter greift.
2. **Die letzte passende Regel gewinnt.** Re-Ausschlüsse wie `src/secrets.py` müssen
   deshalb **nach** dem `!src/**` stehen.
3. **Die `.gitignore` und `.gitattributes` selbst brauchen ein `!`** — sonst ignoriert
   sich die Datei selbst.

Der Preis dieser Umkehrung ist, dass neue Quelldateien außerhalb der zugelassenen Pfade
eingetragen werden müssen. Genau daraus folgt die nächste Regel.

## Die Nachfragepflicht

Die Whitelist schützt davor, dass versehentlich etwas Falsches hineinwandert. Sie schützt
**nicht** davor, dass versehentlich etwas Wichtiges fehlt.

Deshalb: **Sobald neue Verzeichnisse oder Dateien auftauchen, die von der Whitelist nicht
erfasst sind, frage nach, bevor du committest.** Zeig, was es gibt, und sag dazu, wie du
es einschätzen würdest — der Mensch entscheidet schneller, wenn er einen Vorschlag
korrigieren kann, statt eine offene Frage zu beantworten.

Formuliere es konkret:

> Neu im Ordner: `auswertung/` (3 Dateien, 40 KB) und `notizen.md`.
> Mein Vorschlag: `auswertung/` nicht ins Repo (sieht nach Ergebnissen aus),
> `notizen.md` schon. Passt das?

Was du **nicht** tun solltest: die Frage in einen `git add -A`-Aufruf verwandeln und
hinterher erzählen, was passiert ist.

## Vor dem ersten Commit

Diese Kontrollen laufen einmal, kosten Minuten und ersparen im Ernstfall Stunden.

### 1. Zugangsdaten

Nicht auf die Dateinamen verlassen — in den Inhalt schauen.

```bash
git add -A
git diff --cached --name-only          # WAS wird committet? Lies die Liste wirklich.
git diff --cached -S"password" -S"secret" -S"api_key" -S"token" --name-only
```

Wenn eine Datei mit Zugangsdaten existiert, die zum Betrieb gebraucht wird: eine
Vorlagendatei danebenlegen (`config.example.json`, `modKonfig.bas.vorlage`) und im
README erklären. So funktionieren Prüfungen und Aufbau auch ohne das Original.

### 2. Personenbezogene Daten in Binärdateien

**Das ist die am häufigsten übersehene Stelle.** Office-Dateien, PDFs und Bilder tragen
Metadaten, die im Programm nirgends sichtbar sind:

| Ort | Was dort steht |
|---|---|
| `docProps/core.xml` | `creator`, `lastModifiedBy` — der Klarname |
| `docProps/app.xml` | Firma, Vorlagenpfad |
| Benannte Bereiche, zuletzt benutzte Pfade | vollständige Dateipfade samt Benutzername und Cloud-Ordner |
| EXIF in Bildern | GPS-Koordinaten, Gerät, Aufnahmezeit |
| Textinhalt selbst | Namen, Adressen, echte Vorgangsdaten |

Ein `.xlsx`/`.docx`/`.pptx` ist ein Zip. Sieh hinein, statt zu raten:

```bash
python - <<'PY'
import zipfile, re, sys
z = zipfile.ZipFile("datei.xlsx")
text = "\n".join(z.read(n).decode("utf-8", "replace")
                 for n in z.namelist() if n.endswith((".xml", ".rels")))
for name, muster in [("Benutzerpfad", r"C:\\Users\\[A-Za-z0-9._-]+"),
                     ("Cloud-Pfad", r"OneDrive|SharePoint|Dropbox"),
                     ("E-Mail", r"[\w.-]+@[\w.-]+\.\w+")]:
    treffer = set(re.findall(muster, text))
    if treffer: print(name, "->", list(treffer)[:5])
PY
```

Ist eine solche Datei fachlich nötig (als Vorlage, als Testdatensatz), dann committe
nicht das Original, sondern eine **erzeugte** anonyme Fassung — und lege das erzeugende
Skript mit ins Repository. Erzeugt statt gepflegt heißt: die beiden Fassungen können
nicht unbemerkt auseinanderlaufen, und die Anonymisierung ist nachvollziehbar statt
Handarbeit.

Wenn dieselbe Prüfung auch später greifen soll, mach sie zu einem Skript und häng sie in
die CI. Ein Vorsatz läuft nicht bei jedem Push mit, eine Prüfung schon.

### 3. Zeilenenden

`core.autocrlf` schreibt Dateien beim Commit oder Checkout um. Das ist meist harmlos und
gelegentlich fatal: Batch-Dateien (`.cmd`, `.bat`) wollen CRLF, manche Interpreter und
Importer erwarten byteweise genau das, was sie kennen, und in einem Diff sieht die
Umwandlung nach einer Änderung aus, die niemand vorgenommen hat.

```bash
git config --get core.autocrlf
git add -A                       # meldet "CRLF will be replaced by LF" wenn es zuschlaegt
```

Im Zweifel — besonders bei Dateien mit festgelegter Kodierung oder Herkunft — lass Git
die Finger davon:

```gitattributes
* -text
*.xlsx binary
*.png  binary
```

Byteweise speichern, byteweise ausliefern. Wer Zeilenenden ändern will, tut es dann
bewusst und sieht es im Diff. Das muss **vor** dem ersten Commit stehen, sonst ist die
Normalisierung bereits in der Historie.

### 4. Größe

Große Binärdateien blähen jeden Klon dauerhaft auf, weil jede Fassung vollständig
gespeichert wird — sie lassen sich nicht als Diff ablegen. Bei mehr als ein paar
Megabyte: fragen, ob die Datei wirklich versioniert werden muss, oder ob Git LFS bzw. ein
Ablageort außerhalb des Repositories richtiger ist.

## Ein bestehender Ordner soll auf ein bestehendes Repository

Häufiger Fall: lokal liegt gewachsene Arbeit, auf der Gegenseite ein Repository mit
README und generierter `.gitignore`. Kein Force-Push nötig, und die fremden Commits
bleiben erhalten:

```bash
git init -b main
git remote add origin <URL>
git fetch origin
git reset --mixed origin/main     # uebernimmt die Historie, laesst den Arbeitsbaum in Ruhe
git checkout -- README.md         # holt Dateien zurueck, die es nur drueben gibt
```

Danach ist der lokale Stand ein normaler Folge-Commit. Erst **jetzt** die `.gitignore`
schreiben und die Kontrollen oben durchlaufen — vor `git add`, nicht danach.

## Wenn eine Datei nicht im Repository landet

Meistens ist es die `.gitignore` — besonders bei einer Whitelist, wo eine neue Datei
außerhalb der zugelassenen Pfade schlicht durchfällt. Rate nicht, frag Git:

```bash
git check-ignore -v pfad/zur/datei     # nennt Datei UND Zeile der Regel
git status --ignored                    # zeigt, was alles ignoriert wird
```

Kommt keine Ausgabe, liegt es nicht an der `.gitignore` — dann ist die Datei
wahrscheinlich schon getrackt und unverändert, oder sie liegt in einem eigenen
verschachtelten Repository (`.git` im Unterordner) bzw. einem Submodul.

Ist die Regel gefunden, ist die Frage nicht „wie umgehe ich sie", sondern: gehört diese
Datei ins Repository? Wenn ja, nimm sie in die Whitelist auf. `git add -f` ist der
falsche Weg — es committet die Datei, ohne dass irgendwer der `.gitignore` ansieht,
warum sie trotzdem drin ist.

## Es ist schon passiert

Zugangsdaten oder personenbezogene Daten sind bereits committet. Reihenfolge zählt.

**1. Zuerst annehmen, dass es kompromittiert ist.** Schlüssel, Token und Kennwörter
werden **gewechselt**, nicht gelöscht. Das ist der wichtigste Schritt, und er ist
unabhängig davon, ob du die Historie später säuberst. War der Commit gepusht, muss man
davon ausgehen, dass er kopiert, geklont, gespiegelt und indiziert wurde. Bei einem
öffentlichen Repository geschieht das binnen Minuten automatisiert.

**2. Klären, wie weit es gekommen ist.** Nur lokal committet? Dann reicht Umschreiben.
Schon gepusht? Dann ist Schritt 1 nicht verhandelbar, egal was danach kommt.

```bash
git log --oneline --all -- pfad/zur/datei    # wann kam sie rein
git branch -r --contains <commit>            # wo ist sie ueberall
```

**3. Aus dem aktuellen Stand nehmen und ignorieren.**

```bash
git rm --cached pfad/zur/datei
# Pfad in die .gitignore aufnehmen, dann committen
```

Das entfernt die Datei aus künftigen Ständen — **nicht** aus der Historie. Für viele
Fälle (versehentlich eingecheckter Export, Diagnoseausgabe) reicht genau das.

**4. Historie umschreiben — nur wenn nötig, und nie im Alleingang.** `git filter-repo`
(oder BFG) schreibt jeden betroffenen Commit neu. Alle Hashes ändern sich, jeder
Mitarbeitende muss neu klonen oder aufwendig rebasen, offene Pull Requests brechen.
Das ist eine Entscheidung für das Team, nicht für dich: **frag den Menschen, bevor du
Historie umschreibst oder force-pushst.** Und selbst danach behalten Forks, Caches und
die Anzeige bereits geöffneter Pull Requests die alten Objekte oft weiter.

Der Merksatz dahinter: Historie säubern beseitigt die Peinlichkeit, nicht das Risiko.
Das Risiko beseitigt nur der neue Schlüssel.

## Die eine Frage, wenn du unsicher bist

*Wäre es schlimm, wenn diese Datei in fünf Jahren noch für jeden lesbar wäre, der das
Repository klonen darf?*

Bei erzeugtem Quelltext: nein, das ist der Zweck. Bei allem anderen: nachfragen.
