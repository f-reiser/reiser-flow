# reiser-flow

Die Arbeitsweise für alle Softwareprojekte, als Claude-Marketplace. Eine Quelle, von allen
Projekten referenziert — damit dieselbe Regel nicht in fünf Repositories getrennt altert.

> Vorher hieß dieses Repository `f-reiser/claude-skills`. Der Name passte nicht mehr, seit
> hier neben den Skills auch die Workflows liegen, die alle Projekte gemeinsam nutzen. Das
> alte Repository ist archiviert; Historie, offene Pull Requests und Issues sind hierher
> umgezogen.

## Zwei Plugins, eine Grenze

| Plugin | geladen in | Inhalt |
|---|---|---|
| `reiser-flow` | überall — lokal **und** in unbeaufsichtigten GitHub-Läufen | die Arbeitsweise selbst |
| `reiser-flow-lokal` | **nur** lokal | was nur am eigenen Rechner gilt |

Die Grenze ist keine Bitte an das Modell, sondern eine Zeile in `claude-aufgaben.yml`:
`--plugin-dir` zeigt ausschließlich auf `plugins/reiser-flow`, also erreicht
`reiser-flow-lokal` eine unbeaufsichtigte Sitzung gar nicht. Und die Zeile steht nicht im
Projekt, sondern hier — ein Projekt kann die Grenze also nicht versehentlich öffnen. Eine
Regel, die nur lokal gelten soll, im selben
Plugin abzulegen und mit „gilt nur lokal" zu überschreiben, wäre das Gegenteil davon: Sie
hinge daran, dass das Modell den Hinweis liest und befolgt.

Was gehört wohin? Eine Frage entscheidet: **Dürfte ein unbeaufsichtigter Lauf das lesen
und danach handeln?** Ja → `reiser-flow`. Nein → `reiser-flow-lokal`.

Beispiele für das zweite: die Zuordnung der angemeldeten GitHub-Konten (in einem Lauf gibt
es sie nicht — er hat nur sein eigenes Token) und die Befehle, mit denen der Nutzer im Chat
ein Release auslöst (ein Lauf darf gar keines bauen).

### `reiser-flow`

| Skill | wofür |
|---|---|
| `github-issue-workflow` | Issues abarbeiten: Auswahl, Ablauf, Label, Typen, Prioritäten, Regeln für unbeaufsichtigte Läufe |
| `git-branch-strategie` | Feature-Branches, Rebase, Merge-Konflikte, Pull Requests, GitHub-Konten |
| `test-driven-development` | erst der rote Test, dann der Code; Mutationstest für bestehende Suiten |
| `fremde-gegenlese` | Tests und Auslegungen durch einen unabhängigen Agenten prüfen lassen |
| `semver-und-releases` | Versionsnummern, Tags, GitHub-Releases |
| `erklaeren-mit-mass` | wie viel Erklärung ein Text verdient |
| `repo-hygiene` | was in ein Repository gehört und was nicht |
| `projektsprache` | in welcher Sprache ein Projekt kommuniziert — Code, Commits, GitHub, Chat |

### `reiser-flow-lokal`

| Skill | wofür |
|---|---|
| `f-reiser-strukturarbeit` | Strukturaufgaben über den Chat statt über Issues; welches GitHub-Konto wofür; Release-Befehle |

## Verwendung

**In einem Projekt** — nur `reiser-flow`, und nicht als eigener Action-Aufruf, sondern
über die wiederverwendbaren Workflows unten. Das Projekt sagt nur noch, *wann* und *was
bei ihm besonders ist*:

```yaml
on:
  schedule: [{ cron: "0 */4 * * *" }]
  workflow_dispatch:
jobs:
  claude-aufgaben:
    uses: f-reiser/reiser-flow/.github/workflows/claude-aufgaben.yml@v2.0.0
    with:
      projektregeln: |
        Die cp1252-Regel für Makros/*.bas gilt ausnahmslos.
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

Welches Plugin geladen wird, entscheidet dieser Workflow — nicht das Projekt. Er lädt
ausschließlich `reiser-flow`, also erreicht `reiser-flow-lokal` eine unbeaufsichtigte
Sitzung gar nicht.

**Lokal in Claude Code** — beide:

```bash
claude plugin marketplace add f-reiser/reiser-flow
claude plugin install reiser-flow@reiser-flow
claude plugin install reiser-flow-lokal@reiser-flow
```

Beides liest **dasselbe Repository**. Deshalb gibt es diese Skills nicht zusätzlich als
Konto-Skills: Zwei Fassungen bedeuten zwangsläufig, dass eine davon veraltet ist, und man
merkt es erst, wenn die Automatik nach anderen Regeln arbeitet als die Sitzung am Rechner.
Eine Regel ändert man hier, über einen Pull Request.

Was der Marketplace nicht abdeckt: claude.ai im Browser und auf dem Handy. Skills, die
dort gebraucht werden, bleiben Konto-Skills — sie haben mit Softwareprojekten
üblicherweise nichts zu tun.

## Wiederverwendbare Workflows

Neben den Plugins liegt hier ausführbarer Code, den ein Projekt-Workflow über einen Tag
holt, statt ihn in jedem Repository abzuschreiben — derselbe Grund wie bei den Skills:
eine Quelle, sonst altert dieselbe Regel getrennt.

| Workflow | wofür |
|---|---|
| `claude-aufgaben.yml` | arbeitet nach Zeitplan Vorgänge ab, die ein Auftragslabel tragen — Modellwahl aus den Labels, Branch und Fortschrittskommentar vor dem ersten Token, Rettung angefangener Arbeit |
| `label-waechter.yml` | nimmt Steuerlabel zurück, die nicht von Admin oder Maintainer kamen, und setzt die Scoped-Label-Exklusivität durch |
| `label-abgleich.yml` | legt den Label-Katalog aus `.github/labels.json` in einem Projekt an und aktualisiert ihn — nur anlegen und ändern, nie löschen |
| `pruefung-vermerken.yml` | hängt das Ergebnis der Projektprüfung an den Fortschrittskommentar des Vorgangs |
| `issue-autoclose.yml` | schließt ein offenes Issue, sobald ein Pull Request auf dessen `issue-<nr>-*`-Branch vom Maintainer-Konto gemergt wurde |

Wie ein Projekt sie einbindet, steht als Beispiel im Kopf der jeweiligen Datei. Ein
vollständig umgestelltes Projekt ist `f-reiser/Stoffverteilungsplan`.

**Was beim Projekt bleibt:** was dieses Projekt prüft. `pruefung-vermerken.yml` hängt sich
hinter die Projektprüfung, es ersetzt sie nicht.

### Eine einzige Anpinnung

Ein aufgerufener Workflow lädt seine Skripte und die Skills aus **genau dem Commit**, aus
dem er selbst stammt (`job.workflow_sha`). Damit gibt es pro Projekt nur eine Stelle, an
der eine Version steht: die `@<tag>`-Zeile beim Aufrufer.

Das war einmal anders und war eine Wartungsfalle: Der Projekt-Workflow trug den Tag
zweimal, einmal als Klon-Ziel und einmal im Pfad darunter — einzeln geändert fand der Lauf
das Plugin nicht mehr.

`job.workflow_sha` und **nicht** `github.workflow_ref`: In einem per `workflow_call`
aufgerufenen Workflow zeigt der `github`-Kontext auf den **Aufrufer**. Wer sich damit
selbst nachlädt, holt den Stand, den der Aufrufer zufällig hat — die Anpinnung läuft ins
Leere. `.github/pruefe_workflows.py` verhindert genau das, zusammen mit vier weiteren
Zusagen, die sonst erst in einem fremden Projekt auffielen.

### Nie über `@main`

Sonst ändert ein Merge hier sofort das Verhalten aller einbindenden Projekte, ohne Release
und ohne dass es auffällt. Ein fremder Workflow holt sich ausführbaren Code über den Tag:
**Wer einen Tag verschieben kann, führt Code in fremden Projekten aus.** Das Verschieben
eines veröffentlichten Tags ist ab hier keine Ordnungsfrage mehr, sondern
sicherheitsrelevant (`semver-und-releases`).

## Versionierung

Semantic Versioning und Releases: `semver-und-releases`. Tag-Schema hier: **`v<version>`,
ein Tag für das ganze Repository.**

**Alles hier trägt dieselbe Nummer und wird zusammen veröffentlicht** — die beiden
Plugins und die Workflows. Sie sind nicht drei Produkte, sondern Hälften einer
Arbeitsweise: `reiser-flow-lokal` verweist auf Abschnitte in `reiser-flow`, und
`claude-aufgaben.yml` reicht dem Modell Werte an und verweist im Prompt auf Abschnitte
der Skills — es lädt sie sogar aus seinem eigenen Commit. Getrennte Zählung hieße, dass
„Version 1.4" je nach Teil etwas anderes bedeutet, und dass niemand sagen kann, welche
Kombination erprobt ist.

> Bis zum 18.09.2026 gab es zwei Schemata: `<plugin>--v<version>` und ein eigenes
> `workflows--v<version>` mit der Begründung, der Workflow-Code habe „mit dem
> Prompt/Skill-Vertrag der Plugins nichts zu tun". Seit `claude-aufgaben.yml` hier liegt,
> stimmt das nicht mehr — ein Commit entscheidet über Workflow **und** Skills.

Beim Release sind **vier** Stellen zu ziehen, alle vom Plugin-Format erzwungen:

1. `.claude-plugin/marketplace.json` → Eintrag `reiser-flow`
2. `.claude-plugin/marketplace.json` → Eintrag `reiser-flow-lokal`
3. `plugins/reiser-flow/.claude-plugin/plugin.json`
4. `plugins/reiser-flow-lokal/.claude-plugin/plugin.json`

Den Gleichlauf dieser vier prüft `.github/pruefe_marketplace.py` bei jedem Push — nicht
erst `claude plugin tag` beim Release, also an der Stelle, an der ein Fehler am teuersten
auffällt. Der Tag selbst entsteht deshalb als gewöhnlicher annotierter Tag
(`git tag -a v<version>`) und nicht je Plugin über `claude plugin tag`: Es gibt einen Tag,
nicht drei.
