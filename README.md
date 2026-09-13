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

Die Grenze ist keine Bitte an das Modell, sondern eine Zeile im Workflow: er listet unter
`plugins:` ausschließlich `reiser-flow@reiser-flow`, also erreicht `reiser-flow-lokal`
eine unbeaufsichtigte Sitzung gar nicht. Eine Regel, die nur lokal gelten soll, im selben
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

### `reiser-flow-lokal`

| Skill | wofür |
|---|---|
| `f-reiser-strukturarbeit` | Strukturaufgaben über den Chat statt über Issues; welches GitHub-Konto wofür; Release-Befehle |

## Verwendung

**In einem Projekt-Workflow** — nur `reiser-flow`:

```yaml
- uses: anthropics/claude-code-action@v1
  with:
    claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
    plugin_marketplaces: "https://github.com/f-reiser/reiser-flow.git"
    plugins: "reiser-flow@reiser-flow"
    prompt: "/github-issue-workflow"
```

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

## Versionierung

Semantic Versioning und Releases: `semver-und-releases`. Tag-Schema hier:
`<plugin>--v<version>`, also `reiser-flow--v1.1.1` und `reiser-flow-lokal--v1.1.1`.

**Beide Plugins tragen dieselbe Nummer und werden zusammen veröffentlicht.** Sie sind zwei
Hälften einer Arbeitsweise, nicht zwei Produkte: `reiser-flow-lokal` verweist auf
Abschnitte in `reiser-flow` und setzt dessen Stand voraus. Getrennte Zählung hieße, dass
„Version 1.4" je nach Plugin etwas anderes bedeutet — und dass niemand sagen kann, welche
Kombination erprobt ist.

Beim Release sind dadurch **vier** Stellen zu ziehen, alle vom Plugin-Format erzwungen:

1. `.claude-plugin/marketplace.json` → Eintrag `reiser-flow`
2. `.claude-plugin/marketplace.json` → Eintrag `reiser-flow-lokal`
3. `plugins/reiser-flow/.claude-plugin/plugin.json`
4. `plugins/reiser-flow-lokal/.claude-plugin/plugin.json`

`claude plugin tag <pfad>` prüft je Plugin die eigene `plugin.json` gegen den
Marketplace-Eintrag und verweigert das Release, wenn sie auseinanderliegen — den Gleichlauf
*zwischen* den Plugins prüft es nicht, das ist Sache des Release-Ablaufs.

## Wiederverwendbare Workflows

Neben den Plugins liegt hier auch ausführbarer Code, den ein Projekt-Workflow über einen
Tag holt, statt ihn in jedem Repository abzuschreiben — derselbe Grund wie bei den
Skills: eine Quelle, sonst altert dieselbe Regel getrennt.

| Workflow | wofür |
|---|---|
| `.github/workflows/issue-autoclose.yml` | schließt ein offenes Issue automatisch, sobald ein Pull Request auf dessen `issue-<nr>-*`-Branch vom Maintainer-Konto gemergt wurde |

Eingebunden per `workflow_call`, referenziert über einen Tag — nie über `@main`, sonst
ändert ein Merge hier sofort das Verhalten aller einbindenden Projekte, ohne Release und
ohne dass es auffällt. Ein fremder Workflow holt sich damit ausführbaren Code über den
Tag: Verschieben eines Tags ist ab hier keine Ordnungsfrage mehr, sondern
sicherheitsrelevant (`semver-und-releases`).

Eigenes Tag-Schema, unabhängig von den beiden Plugin-Versionen: `workflows--v<version>`,
Quelle `.github/workflows/VERSION`. Dieser Code hat mit dem Prompt/Skill-Vertrag der
Plugins nichts zu tun und muss nicht mit ihnen im Gleichschritt bleiben.
