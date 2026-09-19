# Typen, Label, Priorität

## Issue-Typen

| Typ | wofür |
|---|---|
| **Bug** | Fehlverhalten |
| **Feature** | neue Anforderung |
| **Task** | alles andere, etwa Dokumentation |

Gesetzt von Claude wie von Menschen. Eigene Issues bekommen den Typ immer selbst; bei
fremden Issues ohne Typ setzt Claude ihn, wenn die Einordnung eindeutig ist, und meldet
nur die Zweifelsfälle.

## Label

Die Schreibweise ist bindend, `gh label list` zeigt die gültige Fassung.

**Label gelten für Issues und für Pull Requests gleichermaßen** — ein Pull Request mit
`Einarbeiten` wird behandelt wie ein Issue mit `Einarbeiten`.

| Label | Bedeutung | setzt | entfernt |
|---|---|---|---|
| `Dokumentation` | es geht um Dokumentation jeder Art | Claude, Nutzer | beide |
| `Duplicate` | dupliziert ein anderes Issue | Claude, Nutzer | beide |
| `Einarbeiten` | durchgesehen, kann umgesetzt werden | **nur Admin/Maintainer** | beide |
| `Entscheidung` | zwei oder mehr echte Alternativen, der Nutzer muss eine wählen | **nur Claude** | beide |
| `Gegenlese` | für diesen Vorgang ist nach der Arbeit eine fremde Gegenlese zu fahren | **nur Admin/Maintainer** | **nur Claude**, wenn sie gelaufen ist |
| `GegenleseBefund` | die Gegenlese hat einen bestätigten Befund ergeben | **nur Claude** | beide |
| `Pruefluecke` | eine Prüfung kann strukturell nicht anschlagen | **nur Claude** | beide |
| `Rückfrage` | die Richtung steht fest, es fehlt nur die Schärfe | **nur Claude** | beide |
| `Untersuche` | Bug nachstellen; Verfahren in `SKILL.md`, „Bugs untersuchen" | **nur Admin/Maintainer** | Claude nach der Analyse |
| `WontDone` | wird nicht umgesetzt, braucht Begründung als Kommentar | **nur Nutzer** | Nutzer |

Weitere Label können hinzukommen. Ein unbekanntes Label ist kein Grund, ein Issue zu
überspringen — aber ein Grund nachzufragen, wenn es die Behandlung ändern könnte.

### Wer „Admin/Maintainer" ist — und was davon erzwungen wird

Gemeint ist die Rolle auf dem Repository, nicht eine bestimmte Person. In einem
Projekt mit mehreren Beteiligten soll nicht nur der Eigentümer Arbeit freischalten
können, sondern auch Vertrauenswürdige, die nicht die vollen Rechte auf das
Repository brauchen — genau dafür gibt es die Maintainer-Rolle. Vergeben kann sie
ohnehin nur ein Admin.

**Erzwungen** ist das für `Einarbeiten`, `Gegenlese`, `Untersuche` und die drei
Steuerlabel-Scopes: `label-waechter.yml` nimmt sie zurück, wenn sie von einem
anderen Konto kommen (`.github/skripte/berechtigt.py`, `ERLAUBT = ("admin",
"maintain")`). Die übrigen Zeilen der Tabelle sind **Konvention** — `WontDone` etwa
kann technisch jeder setzen, der überhaupt Label vergeben darf.

Bis zum 19.09.2026 stand hier „nur Nutzer". Das war seit der Erweiterung auf
Maintainer (PR #54 vom 13.09.2026) überholt und musste im Sicherheitslauf #19 als
Abweichung zwischen Doku und Durchsetzung gemeldet werden (#29). Wer die Rollen
wieder verengen will, ändert `berechtigt.py` — und diese Stelle mit.

### Steuerlabel: Modell, Version, Aufwand

Sie sagen nichts über den Vorgang, sondern über den **Lauf**, der ihn abarbeitet — was
er kosten darf. Alle drei Scopes: **nur Admin/Maintainer**, entfernen dürfen beide.

Scoped Labels nach dem Vorbild von GitLab: `Scope::Wert`. Zwei Label mit demselben Scope
schließen einander aus, verschiedene Scopes lassen sich frei kombinieren.

| Scope | Label |
|---|---|
| `Modell` | `Modell::Opus` · `Modell::Sonnet` |
| `v` | `v::4` · `v::5` |
| `Aufwand` | `Aufwand::niedrig` · `Aufwand::mittel` · `Aufwand::hoch` · `Aufwand::extra hoch` · `Aufwand::maximal` |

**Über die Scopes hinweg kombinierbar, innerhalb eines Scopes nicht.** `Modell::Opus` +
`v::4` + `Aufwand::niedrig` ist eine gültige Vorgabe; `Modell::Opus` + `Modell::Sonnet`
ist ein Widerspruch — beide tragen denselben Scope `Modell`.

Ohne Label läuft der Durchgang mit einem günstigen Standard. Ohne Versionslabel gilt die
neueste Fassung des gewählten Modells, ohne Aufwandslabel `Aufwand::hoch`.

**Du wertest diese Label nicht aus.** Wenn du liest, ist die Wahl längst getroffen — sie
muss feststehen, bevor du startest, denn ein laufender Lauf kann sein Modell nicht mehr
wechseln. Der Workflow tut das (im Stoffverteilungsplan `.github/modellwahl.py`). Diese
Tabelle steht hier, damit du weißt, was der Nutzer damit steuert und was du ihm sagen
kannst, wenn er fragt — nicht als Handlungsanweisung.

### Duplicate richtig gesetzt

Ist `Duplicate` gesetzt, **muss** das abdeckende Issue in den Relationships stehen — dort
nur die Nummer. Ein Kommentar kommt dazu, wenn eine Erklärung nötig ist, warum es ein
Duplikat ist.

Fällt dir ein `Duplicate`-Issue ohne diesen Verweis auf: **warnen**. Ohne den Verweis ist
das Label wertlos, weil niemand findet, wohin die Sache verschoben wurde.

## Priorität

`Urgent` · `High` · `Medium` · `Low` — **ohne Angabe gilt Medium.**

Priorität ist kein Feld des Issues selbst, sondern ein Feld im zugehörigen Project. Das
Lesen braucht den Scope `read:project`; fehlt er oder gibt es kein Project, gilt Medium.

Wie Priorität, Abhängigkeit und Alter die Reihenfolge bestimmen, steht in `SKILL.md`,
Abschnitt „Welches Issue zuerst".

