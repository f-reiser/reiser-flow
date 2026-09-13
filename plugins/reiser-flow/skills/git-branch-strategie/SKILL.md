---
name: git-branch-strategie
description: >
  Verbindlicher Feature-Branch-Workflow für alle Softwareprojekte: von main abzweigen und
  nach main zurück, Aktualisieren ausnahmslos per Rebase, Sonderfall blockierter Issues,
  ein gemeinsamer Branch für hierarchische Issues, Aufräumen der Historie vor dem Pull
  Request, Rebase-Merge gegen Merge-Commit, eigenständiges Lösen von Merge-Konflikten — und
  mit welchem GitHub-Konto gearbeitet wird. Nutze diesen Skill, bevor du einen Branch
  anlegst, committest, pushst, einen Pull Request erstellst oder mergst; wenn zu klären ist,
  wie ein Pull Request nach main kommt; wenn ein Branch länger offen ist; bei jedem Merge-Konflikt; und immer, wenn
  zwei Änderungen voneinander abhängen. Ebenso bei Fragen nach Branch-Namen,
  Merge-Reihenfolge, Commit-Identität oder dem zu verwendenden GitHub-Konto.
---

# Branch-Strategie

## Grundform

Feature-Branch-Workflow, ausnahmslos. Ein Branch trägt genau ein Issue.

```bash
git fetch origin
git checkout -b issue-<nr>-<kurzer-slug> origin/main
```

Nie direkt auf `main` committen.

**Vorher nachsehen, ob es den Branch schon gibt.** Ein früherer Versuch kann abgebrochen
sein — Zeitüberschreitung, erschöpftes Nutzungslimit, abgestürzter Lauf — und Commits
hinterlassen haben, während das Issue sein Label behielt:

```bash
git ls-remote --heads origin "issue-<nr>-*"
```

Kommt etwas zurück, wird **darauf weitergearbeitet**, nicht neu angefangen:

```bash
git checkout -b issue-<nr>-<slug> origin/issue-<nr>-<slug>
git rebase origin/main
```

Und dann zuerst `git log origin/main..HEAD` lesen, um zu sehen, wie weit der vorige
Versuch gekommen ist. Ein neuer Branch mit demselben Namen wäre die schlechteste Antwort:
Der Push würde abgelehnt, und ein `--force` darüber verwürfe stillschweigend Arbeit, die
schon getan ist.

## Aktualisieren: immer Rebase, nie Merge

Ein Feature-Branch wird **ausnahmslos per Rebase** auf den Stand seines Quellbranchs
gebracht — nie per Merge. Merge-Commits aus dem Quellbranch erzeugen einen
Historien-Salat, in dem später niemand mehr etwas eingrenzen kann.

```bash
git fetch origin
git rebase origin/main          # Quellbranch; bei Child-Branches der Parent-Branch
git push --force-with-lease
```

Pflicht an drei Stellen:

- **mindestens einmal täglich**, solange der Branch offen ist
- **bevor du neue Arbeit** an einem bestehenden Branch aufnimmst
- **vor dem finalen Commit**, dem nur noch der Pull Request folgt

Je länger ein Branch wegdriftet, desto teurer der Konflikt — und desto wahrscheinlicher
fällt er erst im Pull Request auf, wo er den Prüfer trifft statt dich.

**`--force-with-lease`, nie `--force`:** Es bricht ab, wenn jemand anderes zwischenzeitlich
gepusht hat, statt dessen Arbeit zu überschreiben. Auf `main` wird nie force-gepusht.

## Merge-Konflikte löst du

Du bist der Hauptentwickler. Konflikte gehören zu deiner Arbeit, nicht zu der des Nutzers.
Er kommt mit der Menge Code, die hier entsteht, zeitlich nicht mit — ihn einen Konflikt
lösen zu lassen ist auf seiner Seite teuer und der Ausnahmefall.

Also: den Konflikt verstehen, beide Seiten im Kontext lesen, auflösen, Tests laufen
lassen. Erst wenn du nach ernsthaftem Versuch nicht sicher entscheiden kannst, **welches
Verhalten gewollt ist** — nicht: wie man es technisch löst —, geht die Frage an den Nutzer,
mit beiden Fassungen und deiner Empfehlung.

Das wirkt auch nach vorn: Bevorzuge Vorgehensweisen, die Konflikte gar nicht erst
entstehen lassen — häufig rebasen, Änderungen klein und thematisch geschnitten halten,
nicht nebenbei formatieren.

## Wie Issues zusammenhängen — drei verschiedene Dinge

| GitHub | Bedeutung | Wirkung auf die Reihenfolge |
|---|---|---|
| **Add parent** / Sub-Issues | echte Hierarchie: großes Feature, zerlegt in Teile | alle arbeiten auf **einem** Branch, dem des Parent-Issues |
| **Mark as blocked by / blocking** | eigenständige Features, die aber in einer Reihenfolge müssen | blockierendes Issue zuerst |
| **Add relates to** | thematisch verwandt, z. B. Doku-Task zu einem Feature | **keine** — für die Reihenfolge ignorieren |

Die Begriffe nicht vermischen: **Parent** heißt Hierarchie, sonst nichts. Ein Issue, das
ein anderes blockiert, ist kein Parent.

## Blockierte Issues

Zuerst das Issue, das von keinem offenen Issue blockiert wird. Erst wenn dessen Änderungen
in `main` sind, ist der Normalfall wiederhergestellt.

Muss das blockierte Issue vorher begonnen werden, **zweigt sein Branch vom blockierenden
Branch ab** statt von `main`:

```bash
git fetch origin
git checkout -b issue-<nr>-<slug> origin/issue-<blocker-nr>-<slug>
```

Der blockierende Branch ist damit sein Quellbranch — Aktualisieren heißt Rebase auf ihn,
und sobald er in `main` gelandet ist, Rebase auf `origin/main`.

> Früher stand hier: von `main` abzweigen und den blockierenden Branch hineinmergen. Das
> erzeugt genau den Merge-Commit, den die Rebase-Regel vermeiden soll. Inhaltlich ist
> Abzweigen vom Blocker dasselbe, nur linear.

Erlaubt ist das nur, wenn **beides** zutrifft:

- Das blockierende Feature ist nach bestem Wissen fertig — es fehlt nur noch der Pull
  Request, oder es sind Kleinigkeiten offen (etwa eine Doku-Ergänzung), die auf eine
  Rückfrage warten.
- Es hat **alle Tests grün** durchlaufen.

Im Pull Request des blockierten Issues muss stehen, von welchem Issue es abhängt und dass
**dessen Pull Request zuerst** bearbeitet werden muss.

## Reihenfolge der Pull Requests

Pull Requests werden in der Reihenfolge ihrer Abhängigkeit bearbeitet. **Ein Pull Request
bringt niemals zwei verschiedene Features nach `main`.**

Die Branch-Historie ist eine Suchhilfe: Wer einen schwer auffindbaren Fehler eingrenzt,
braucht einen konsistenten Stand nach dem anderen. Ein Merge, der zwei unabhängige
Features gleichzeitig einbringt, macht jeden Treffer von `git bisect` mehrdeutig.

## Große Features mit Sub-Issues

**Ein Branch für das Parent-Issue, und alle Child-Issues arbeiten darauf.** Keine
Branches je Child. Aktuell gehalten wird er per Rebase auf `main`, wie jeder andere
Feature-Branch; nach `main` zurück geht er als ein Pull Request.

Der Grund ist die Verträglichkeit mit der Rebase-Regel: Zweigten Children vom
Parent-Branch ab, würde jedes Rebase des Parents ihnen die Basis unter den Füßen
wegziehen — sie müssten in derselben Sitzung nachgezogen werden, und wer das einmal
vergisst, hinterlässt Branches, die auf Commits sitzen, die es nicht mehr gibt. Ein
gemeinsamer Branch kennt dieses Problem nicht.

Die Commits bleiben trotzdem je Child unterscheidbar: jeder trägt `Refs #<nr>` seines
eigenen Issues. Beim Merge-Commit (unten) bleibt diese innere Struktur sichtbar.

## Historie aufräumen vor dem Pull Request

Zwischenstände wie „Tippfehler", „doch anders" oder „Test grün" tragen nichts. Vor dem
Pull Request die eigenen Commits zusammenfassen — besonders bei großen Features und immer,
wenn es viel Hin und Her zwischen Nutzer und Claude gab.

```bash
git fetch origin
git rebase -i origin/main
git push --force-with-lease
```

### Auch nach einer Gegenlese, und dort besonders

**Befunde aus `fremde-gegenlese` werden eingefaltet, nicht angehängt.** Der häufigste Fall
ist nicht der Tippfehler, sondern dieser: Der Pull Request steht, die Gegenlese meldet,
du korrigierst — und wer den Pull Request dann liest, liest deinen Denkweg statt der
Änderung. Bei drei Befunden sind das drei Commits, in denen du dich selbst berichtigst.

Das kostet fremde Zeit, und zwar genau die des Menschen, der zustimmen soll.

Also: korrigieren, dann `git reset --soft <basis>` und **einmal** committen, was am Ende
dasteht. Die Meldung beschreibt den Endstand, nicht den Weg dorthin.

**Zwei Dinge überleben das Zusammenfassen trotzdem:**

- **Was jemand später wissen muss, um die Änderung nicht rückgängig zu machen.** „Diese
  Berechtigung sieht überflüssig aus, ist sie aber nicht, weil …" gehört in die Meldung —
  das ist Projektwissen, keine Selbstkorrektur.
- **Ein Befund, den du geprüft und verworfen hast**, samt Begründung. Sonst kommt er bei
  der nächsten Gegenlese wieder.

**Zieh die abhängigen Branches mit.** Nach dem Umschreiben sitzen sie auf Commits, die es
nicht mehr gibt:

```bash
git rebase --onto <branch> <alte-spitze> <abhaengiger-branch>
git push --force-with-lease origin <abhaengiger-branch>
```

Und danach nachweisen, dass nur die Historie anders ist und nicht das Ergebnis:

```bash
git diff <alte-spitze> <branch>     # muss leer sein
```

## Wie der Pull Request nach main kommt

| Fall | Modus |
|---|---|
| kleineres Feature, Bugfix | **Rebase and merge** |
| großes Feature (hierarchisch über mehrere Issues strukturiert) | **Create a merge commit** |
| immer | **kein Squash-Merge** |

**Warum nicht squashen.** Die Commits sind vor dem Pull Request ohnehin per Rebase
aufgeräumt (siehe oben) — sie sind also genau die, die man behalten will. Squashen wirft
diese Arbeit wieder weg. Und bei einer Änderung, die in einen oder zwei Commits passt,
erzeugt es eine Nebenlinie mit einem einzigen Commit darin: Aufwand ohne Ertrag.

Rebase-Merge setzt die aufgeräumten Commits linear auf `main` — keine Nebenlinie, keine
Merge-Commits für Kleinkram, und `git log` liest sich als eine Reihe.

Beim großen Feature ist der Merge-Commit richtig: Er hält die Zusammengehörigkeit der
Teile fest und markiert, wo das Feature beginnt und endet — genau die Information, die man
beim Eingrenzen mit `git bisect` braucht.

**Gemergt wird vom Nutzer.** Nur wenn er es hier im Gespräch ausspricht, und dann für
genau diesen einen Pull Request — nicht für den nächsten, nicht als Dauerregel.

## Mit welchem Konto

Drei Schichten, die unabhängig umschalten. Wer nur eine tauscht, bekommt ein Ergebnis,
das falsch aussieht, ohne dass es auffällt.

| Schicht | steuert | umgeschaltet über |
|---|---|---|
| `gh` | wer auf GitHub handelt | `GH_TOKEN` |
| `git push` | wer pushen darf | Credential-Helper (folgt `GH_TOKEN`) |
| Commit-Autor | was die Historie sagt | `user.name` / `user.email` |

**Gilt nur, wenn die Sitzung diese Konten überhaupt anmelden kann** — geprüft mit
`gh auth status`. Das ist bei einer lokalen Sitzung der Fall, nicht bei einer Sitzung, die
ausschließlich innerhalb eines GitHub-Workflows läuft (claude-api/GitHub Actions): die
handelt immer unter ihrem eigenen, vom Workflow bereitgestellten Token, hat keinen Zugriff
auf eines der unten gemeinten Konten und sollte diesen ganzen Abschnitt überspringen statt
einen Kontowechsel zu versuchen, der ins Leere läuft.

**Welche Konten das konkret sind, steht nicht hier.** Kontonamen sind personenbezogen;
dieses Repository ist öffentlich. Die tatsächliche Zuordnung — welches Konto Bot, welches
Admin, für welche Organisation — gehört in einen lokalen Skill außerhalb dieses
Repositories. Hier steht nur der Mechanismus, mit Platzhaltern.

**Laufende Arbeit** — Commits, Branches, Issues, Pull Requests, Tags und Releases —
unter dem Bot-Konto:

```bash
export GH_TOKEN=$(gh auth token --user <Bot-Konto>)
git -c user.name="<Bot-Konto>" \
    -c user.email="<GitHub-User-ID>+<Bot-Konto>@users.noreply.github.com" \
    commit -m "..."
```

Die noreply-Adresse ist geprüft: GitHub verknüpft damit erstellte Commits mit dem
Bot-Account, ohne dass eine private Adresse im Repository steht. Die User-ID liefert
`gh api users/<Bot-Konto> --jq .id`.

**Beim Ändern eines bestehenden Commits zusätzlich `--reset-author`:**

```bash
git -c user.name="…" -c user.email="…" commit --amend --reset-author --no-edit
```

`--amend` behält sonst den ursprünglichen **Autor** — die `-c`-Angaben setzen nur den
Committer. Ohne `--reset-author` steht der Commit weiterhin unter dem, der ihn zuerst
gemacht hat, und das fällt erst auf, wenn jemand die Historie liest. Nach dem Prüfen:
`git log -1 --format='%an <%ae>'`.

Damit `git push` demselben Token folgt, muss der Credential-Helper einmalig je Repository
gesetzt sein:

```bash
git config --local credential.https://github.com.helper ""
git config --local --add credential.https://github.com.helper "!gh auth git-credential"
```

Bewusst repo-lokal, nicht global — sonst laufen auch die eigenen Pushes des Nutzers über
`gh` und die Kontowahl wird ihm aus der Hand genommen.

Ein Release ist zwar eine Veröffentlichung, aber keine Verwaltungsarbeit: `push` genügt
dafür, und ausgelöst wird es ohnehin nur, wenn der Nutzer „Release bauen" sagt
(`semver-und-releases`). Es läuft deshalb unter dem Bot-Konto wie jeder Commit.

**Nicht mit dem Bot-Konto:** Repositories anlegen, Branch-Schutzregeln, Collaborators,
Label und Issue-Typen einrichten. Das Bot-Konto hat dafür bewusst keine Rechte (`write`,
kein `admin`). Solche Arbeiten laufen über das Admin-Konto und werden vorher angesprochen —
`GH_TOKEN=$(gh auth token --user <Admin-Konto>)`.

`gh auth switch` ist hier das falsche Werkzeug: Es setzt einen globalen Zustand, den eine
andere Sitzung verändert haben kann. Ein unbeaufsichtigter Lauf darf nicht davon abhängen.
