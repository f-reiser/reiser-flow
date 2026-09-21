---
name: f-reiser-strukturarbeit
description: >
  NUR relevant für Softwareprojekte, die reiser-flow tatsächlich einbinden (jeder kann
  das in seiner eigenen GitHub-Organisation, mit eigenen Konten und eigenem
  Claude-Zugang — nicht auf eine bestimmte Organisation beschränkt), und NUR in einer
  Sitzung am eigenen Rechner; bei jedem Projekt ohne erkennbaren Bezug zu reiser-flow
  ignorieren. Für solche Projekte: Kontext für Strukturaufgaben, die direkt im Chat
  statt über den Issue-Workflow erledigt werden — Skillset erweitern oder korrigieren,
  projektübergreifende Workflows anpassen, Projektstruktur ändern. Ergänzt die Skills
  aus reiser-flow um das, was dort nicht hingehört, weil es nur lokal gilt: wie sich
  eine Chat-Sitzung von einer Sitzung in GitHub Actions unterscheidet, welches der
  angemeldeten GitHub-Konten wofür zuständig ist, und welche Befehle ein Release
  auslösen. Nutze diesen Skill, sobald in einem solchen Projekt eine Strukturaufgabe
  ansteht statt einer Fachaufgabe an einem einzelnen Repository, wenn zu klären ist,
  welches Konto oder Repository gemeint ist, und bei jedem Release-Befehl des Nutzers.
---

# Strukturarbeit — nur für Projekte mit reiser-flow, nur lokal

## Zwei Schranken, bevor irgendetwas hier gilt

**1. Nur in einer lokalen Sitzung.** Dieser Skill steckt im Plugin `reiser-flow-lokal`. Ein
unbeaufsichtigter Lauf lädt nur `reiser-flow` und sieht ihn deshalb gar nicht —
diese Schranke hält der Workflow, nicht dein Urteil. Findest du ihn trotzdem in einer
Sitzung vor, in der `$GITHUB_ACTIONS` gesetzt ist, ist das ein Fehler in der
Workflow-Datei: melden, und nichts aus diesem Skill anwenden.

Warum das zwei Plugins sind und keine zwei Repositories: `README.md` im Wurzelverzeichnis.

**2. Nur Projekte, die reiser-flow tatsächlich einbinden.** Bei jedem anderen Projekt
sagt dieser Skill nichts Sinnvolles — auch nicht bei einem anderen eigenen Repository,
das zufällig derselben Organisation gehört, reiser-flow selbst aber nicht nutzt.
**reiser-flow ist nicht auf eine Organisation beschränkt:** Jeder kann es einbinden, in
seiner eigenen Organisation, mit eigenen Konten und eigenem Claude-Zugang — dieser
Skill gilt dann dort genauso, nur eben für diese andere Organisation.

Erkennbar ist die Zugehörigkeit an den eigenen Workflow-Dateien: Sie binden
`<eigene-organisation>/reiser-flow` ein, etwa `uses: <organisation>/reiser-flow/
.github/workflows/claude-aufgaben.yml@<tag>`. Vor der Anwendung kurz nachsehen
(`grep -r reiser-flow .github/workflows/`), ob das aktuelle Projekt so einen Verweis
trägt — oder ob erkennbar ist, dass er entstehen soll. Arbeitest du direkt im
Repository `reiser-flow` selbst, gilt das immer, unabhängig von seiner Organisation.

Die konkrete Organisation selbst steht deshalb nirgends fest — sie ergibt sich aus
genau diesem Verweis oder aus `gh repo view --json owner --jq .owner.login` am
aktuellen Projekt, sobald die Zugehörigkeit so geklärt ist.

## Wofür dieser Skill sonst da ist

Für Aufgaben, die keine Fachaufgabe an EINEM Projekt sind, sondern die Struktur betreffen,
die mehrere Projekte der eigenen Organisation teilen: das Skillset erweitern oder
korrigieren, Workflows projektübergreifend anpassen, eine Projektstruktur ändern. Solche
Aufgaben laufen bewusst
**direkt über den Chat**, nicht über den Issue-Workflow mit Label „Einarbeiten"
(`github-issue-workflow`) — das geht schneller, und es ist nicht die Art Aufgabe, die an
ein einzelnes Repository gebunden ist.

**Der grundsätzliche Workflow ändert sich dadurch nicht.** Sobald ein Branch existiert,
gilt exakt das, was `reiser-flow:git-branch-strategie` und die übrigen Skills aus
`reiser-flow` beschreiben — Feature-Branch, Rebase, aufgeräumte Historie, Pull
Request, Merge nur durch den Nutzer. **Nur der Einstiegspunkt ist anders:** keine
Issue-Erstellung, keine Label-Steuerung — die Anforderung steht im Chat, nicht im
Issue-Text. Ein Branchname ohne Issue-Nummer ist hier deshalb normal (z. B.
`entferne-kontonamen-git-branch-strategie` statt `issue-<nr>-<slug>`).

Dieser Skill dupliziert `reiser-flow` nicht. Für Rebase-Regeln, PR-Konventionen,
Gegenlese und den Release-*Ablauf* gelten unverändert die dortigen Skills; bei Bedarf dort
nachladen, nicht hier wiederholen.

## Zwei Einstiegspunkte, eine Organisation

| | Chat-Sitzung (Claude Code/App, wie diese hier) | Sitzung über claude-api/GitHub Actions |
|---|---|---|
| ausgelöst durch | Chat mit dem Nutzer | Vorgang mit Auftragslabel |
| GitHub-Zugriff über | `gh` CLI mit den angemeldeten Konten | eigenes Token der Aktion |
| Zugriff auf Bot- oder Admin-Konto | ja | **nein** |
| lädt dieses Plugin | ja | **nein** |

Das Umschaltverfahren aus `git-branch-strategie`
(`GH_TOKEN=$(gh auth token --user …)`) setzt voraus, dass beide Konten bei `gh` angemeldet
sind. Das ist nur auf der Maschine der Fall, auf der du selbst arbeitest.

## Welches Konto wofür — ermitteln, nicht nachschlagen

Die Kontennamen stehen **absichtlich nirgends im Repository**: es ist öffentlich, und eine
abgeschriebene Liste altert. Beides erledigt eine Abfrage:

```bash
gh auth status                                  # welche Konten sind angemeldet?
gh api "repos/$(gh repo view --json nameWithOwner --jq .nameWithOwner)/collaborators/<login>/permission" --jq .permission
```

| Antwort | Rolle | zuständig für |
|---|---|---|
| `admin` | Admin-Konto | Repository anlegen, Branch-Schutzregeln, Collaborators, Label, Issue-Typen — **vorher ansprechen** |
| `write` | Bot-Konto | laufende Arbeit: Commits, Branches, Pull Requests, Issues, Releases |

Das ist die konkrete Ausprägung von `git-branch-strategie` → „Mit welchem Konto": dort
steht der Mechanismus mit den Platzhaltern `<Bot-Konto>` / `<Admin-Konto>`, hier steht,
wie du sie füllst.

Ergibt die Abfrage nicht genau ein `admin` und ein `write`, ist die Annahme dieses Skills
verletzt — dann fragen statt raten.

## Repositories in der Organisation

Welche Organisation das ist und welche Repositories dazugehören, ist eine lokale
Tatsache wie die Kontennamen oben — deshalb nicht hier aufgezählt, sondern immer über
eine Abfrage ermittelt:

```bash
gh repo view --json owner --jq .owner.login    # Organisation des aktuellen Projekts
gh repo list <Organisation> --limit 100        # ihre Repositories
```

**`reiser-flow` gehört immer dazu**, unabhängig von der konkreten Organisation: Es
verwaltet die Plugins `reiser-flow` (überall geladen) und `reiser-flow-lokal` (nur
lokal, dieses hier). Öffentliches Repository — deshalb keine Kontennamen, Projektnamen
oder sonstigen personenbezogenen Daten anderer Projekte der Organisation
hineinschreiben (siehe `repo-hygiene`). Notizen zu den übrigen Repositories der eigenen
Organisation gehören ins eigene, nicht öffentliche Gedächtnis (Memory), nicht in diese
Datei.

## Wenn eine Strukturaufgabe die Skills selbst betrifft

Das geht ins Repository `reiser-flow`, nach dem üblichen Workflow (Branch, Pull
Request, Merge durch den Nutzer) — auch eine Änderung an *diesem* Skill hier, denn er
liegt jetzt selbst dort. Welches der beiden Plugins zuständig ist, entscheidet eine
Frage: **Dürfte ein unbeaufsichtigter Lauf das lesen und danach handeln?**

- ja → `reiser-flow`
- nein, das gilt nur am eigenen Rechner → `reiser-flow-lokal`

## Release-Befehle

Der Ablauf eines Releases steht in `reiser-flow:semver-und-releases` — **welche Sätze
des Nutzers eines auslösen, steht nur hier.** Ein unbeaufsichtigter Lauf baut keine
Releases; eine Befehlsliste hätte dort nichts zu suchen und wäre eine Angriffsfläche mehr.

Ein Release hat nur eine Versionsnummer — `MAJOR.MINOR.PATCH`. Wo sie im Projekt steht:
`semver-und-releases` → „Wo die Version steht". Es gibt daneben **keinen** eigenen
„Release-Namen": Was danach aussieht, ist der Plugin-Name, siehe „Was in diesem
Repository dazukommt" unten.

### Ein Release auslösen

**Alle vier Formen lösen ein Release aus** — sie unterscheiden sich nur darin, welche
Versionsnummer dabei verwendet wird. Innerhalb einer Form sind „Erstelle X" und „X
erstellen" gleichwertig, teils auch „X releasen".

| Befehl | Versionsnummer |
|---|---|
| **Erstelle Release** · **Release erstellen** | die Nummer, die **aktuell in den Dateien steht** — nicht hochgezählt. |
| **Erstelle Minor Release** · **Minor Release erstellen** | MINOR + 1, PATCH auf 0. |
| **Erstelle Fix Release** · **Fix Release erstellen** · **Fix releasen** | PATCH + 1, MINOR unverändert. |
| **Erstelle Release 1.2.3** · **Release 1.2.3 erstellen** · **1.2.3 releasen** | genau diese Nummer, ohne Ableitung. |

Ohne Nummer im Befehl gilt die Ableitung aus `semver-und-releases` → „Welche Stelle
steigt". Trägt sie nicht, wird nichts getan und gefragt — auch das steht dort.

### Nur vorbereiten, noch nicht veröffentlichen

**Nächstes Release 1.2.3** setzt nur die Versionsnummer auf 1.2.3 — kein Tag, kein
Release.

### Die Auflistung auf Verlangen

Fragt der Nutzer **„Wie kann ich releasen?"**, gib die Tabelle oben und den Befehl zum
Vorbereiten wieder — jeden mit dem, was du dabei tun würdest, und dazu die drei Punkte:
dass ohne Nummer abgeleitet wird, dass MAJOR immer bei ihm liegt, und welche Nummer
aktuell in den Dateien steht. Kein Release, keine Änderung — nur die Antwort.

### Die eine Ausnahme von „gemergt wird nur vom Nutzer"

Ein Pull Request, der **ausschließlich** Versionsnummern ändert, darf **selbst gemergt**
werden. Diese Erlaubnis gilt für genau diese Art Pull Request und für keine andere — sie
ist keine Lockerung von `git-branch-strategie`, sondern eine eng umrissene Ausnahme davon.

Die Grenze ist wörtlich zu nehmen. Vor dem Merge nachsehen, nicht annehmen:

```bash
gh pr diff <nr>
```

Steht darin **irgendetwas** außer geänderten Versionsnummern — eine Doku-Anpassung, ein
Verweis, ein nachgezogener Kommentar, eine Zeile in der Prüfung —, ist die Ausnahme
verbraucht und es gilt wieder: **der Nutzer mergt.** Im Zweifel nicht mergen; ein
wartender Pull Request kostet nichts, ein selbst gemergter zu viel Inhalt lässt sich nicht
zurücknehmen.

**Kam der Befehl aus der Spalte „Ein Release auslösen"**, folgt nach diesem Merge
unmittelbar das Release nach `semver-und-releases`. Kam er aus „Nur vorbereiten", endet es
hier.

### Was in diesem Repository dazukommt

`reiser-flow` veröffentlicht **zwei** Plugins unter derselben Nummer, mit **einem** Tag
fürs ganze Repository (`README.md` → „Versionierung"). Ein Release heißt hier deshalb:
vier Stellen ziehen (`semver-und-releases` → „Wo die Version steht"), **einen**
annotierten Tag `v<version>` setzen (`git tag -a`, nicht `claude plugin tag` — das sähe
je Aufruf nur eines der beiden Plugins), **ein** GitHub-Release. Es gibt daneben keinen
separat wählbaren Release-Namen.
