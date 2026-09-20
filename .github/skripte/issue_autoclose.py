#!/usr/bin/env python3
"""Schliesst Issues automatisch, wenn ein Pull Request sie durch Merge erledigt hat,
oder wenn eines der Endzustand-Label gesetzt ist (f-reiser/reiser-flow#55).

Erkennung ueber den Branchnamen (`issue-<nr>-<slug>`, siehe git-branch-strategie),
nicht ueber GitHub-Cross-References: die schlagen auch bei PRs an, die ein Issue nur
beilaeufig erwaehnen, ohne es zu loesen (siehe Doku im Pull Request dieser Datei).

Ausdruecklich NICHT automatisiert: ein geschlossener, nicht gemergter Pull Request
schliesst das Issue nie. Das bleibt eine Entscheidung des Maintainers.

ENDZUSTAND-LABEL
    "Verworfen" und "Duplikat" heissen beide: an diesem Issue wird nicht mehr
    weitergearbeitet - der Nutzer hat das schon entschieden, indem er das Label
    gesetzt hat. Ein weiterer manueller Schritt (Schliessen) wuerde ihm nichts
    mehr sagen, was das Label nicht schon gesagt hat.
"""
import argparse
import json
import os
import re
import subprocess
import sys

BRANCH_ISSUE = re.compile(r"^issue-(\d+)-")

#  Labelnamen nach der Umbenennung aus f-reiser/reiser-flow#54 ("WontDone" ->
#  "Verworfen", "Duplicate"/"duplicate" -> "Duplikat"). Ein Repository, das
#  diese Umbenennung noch nicht ausgerollt hat, traegt diese Label schlicht
#  noch nicht - dann greift hier nichts, ohne dass das ein Fehler waere.
ENDZUSTAND_LABEL = ("Verworfen", "Duplikat")

ISSUES_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    issues(states: OPEN, first: 100, after: $cursor) {
      nodes { number labels(first: 20) { nodes { name } } }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""

MERGED_PRS_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(states: MERGED, first: 100, after: $cursor,
                  orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes { number headRefName merged mergedBy { login } }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""


def issue_nummer_aus_branch(branch):
    treffer = BRANCH_ISSUE.match(branch)
    return int(treffer.group(1)) if treffer else None


def entscheidung(pr, maintainer_login):
    """Liefert die Issue-Nummer, die dieser PR erledigt hat, sonst None.

    Nur ein gemergter PR auf einem `issue-<nr>-*`-Branch zaehlt, und nur, wenn
    der Merge vom Maintainer-Konto kam. Ein geschlossener, nicht gemergter PR
    liefert immer None - das Issue zu schliessen bleibt dann eine Entscheidung
    des Maintainers, keine automatische Folge.
    """
    if not pr.get("merged"):
        return None
    merged_by = pr.get("mergedBy") or {}
    if merged_by.get("login") != maintainer_login:
        return None
    return issue_nummer_aus_branch(pr["headRefName"])


def zu_schliessende_issues(prs, maintainer_login):
    """{Issue-Nummer: PR-Nummer} fuer alle PRs, die ein Issue erledigt haben."""
    ergebnis = {}
    for pr in prs:
        issue_nr = entscheidung(pr, maintainer_login)
        if issue_nr is not None:
            ergebnis[issue_nr] = pr["number"]
    return ergebnis


def wegen_label_zu_schliessende_issues(issues):
    """{Issue-Nummer: Labelname} fuer offene Issues mit einem Endzustand-Label.

    issues: [(nummer, [labelname, ...]), ...]. Traegt ein Issue mehrere
    Endzustand-Label gleichzeitig (kommt praktisch nicht vor), zaehlt das
    zuerst in ENDZUSTAND_LABEL genannte - irgendeine feste Regel ist hier
    noetig, und welche, ist gleichgueltig: beide fuehren zum selben Schluss.
    """
    ergebnis = {}
    for nr, labels in issues:
        for kandidat in ENDZUSTAND_LABEL:
            if kandidat in labels:
                ergebnis[nr] = kandidat
                break
    return ergebnis


def selbsttest():
    faelle = []

    def fall(name, ergebnis, erwartet):
        faelle.append((name, ergebnis, erwartet))

    fall(
        "gemergt vom Maintainer, Branch passt -> Issue 31",
        entscheidung(
            {"headRefName": "issue-31-foo", "merged": True,
             "mergedBy": {"login": "ReiserFlorian"}},
            "ReiserFlorian",
        ),
        31,
    )
    fall(
        "gemergt, aber von jemand anderem -> keine Schliessung",
        entscheidung(
            {"headRefName": "issue-31-foo", "merged": True,
             "mergedBy": {"login": "reiser-claude-agent"}},
            "ReiserFlorian",
        ),
        None,
    )
    fall(
        "nicht gemergt (offen ODER geschlossen ohne Merge) -> keine Schliessung, "
        "das entscheidet der Maintainer",
        entscheidung(
            {"headRefName": "issue-31-foo", "merged": False,
             "mergedBy": None},
            "ReiserFlorian",
        ),
        None,
    )
    fall(
        "Branch ohne issue-<nr>-Praefix -> keine Zuordnung",
        entscheidung(
            {"headRefName": "arbeit-fruehzeitig-sichern", "merged": True,
             "mergedBy": {"login": "ReiserFlorian"}},
            "ReiserFlorian",
        ),
        None,
    )
    fall(
        "Nummer ohne trennenden Bindestrich dahinter -> keine Zuordnung",
        entscheidung(
            {"headRefName": "issue-31foo", "merged": True,
             "mergedBy": {"login": "ReiserFlorian"}},
            "ReiserFlorian",
        ),
        None,
    )
    fall(
        "mehrstellige Nummer wird vollstaendig gelesen, nicht nur die erste Ziffer",
        issue_nummer_aus_branch("issue-312-lange-nummer"),
        312,
    )
    fall(
        "Grossschreibung im Praefix zaehlt nicht (Konvention ist immer klein)",
        entscheidung(
            {"headRefName": "Issue-31-foo", "merged": True,
             "mergedBy": {"login": "ReiserFlorian"}},
            "ReiserFlorian",
        ),
        None,
    )
    fall(
        "zwei PRs, nur einer qualifiziert -> nur der landet in der Zuordnung",
        zu_schliessende_issues(
            [
                {"number": 55, "headRefName": "arbeit-fruehzeitig-sichern",
                 "merged": True, "mergedBy": {"login": "ReiserFlorian"}},
                {"number": 59, "headRefName": "issue-31-nutzer-auf-fehlerhafte-bezuege",
                 "merged": True, "mergedBy": {"login": "ReiserFlorian"}},
            ],
            "ReiserFlorian",
        ),
        {31: 59},
    )

    fall(
        "Verworfen -> wird zum Schliessen vorgemerkt",
        wegen_label_zu_schliessende_issues([(12, ["Verworfen"])]),
        {12: "Verworfen"},
    )
    fall(
        "Duplikat -> wird zum Schliessen vorgemerkt",
        wegen_label_zu_schliessende_issues([(13, ["Duplikat", "Dokumentation"])]),
        {13: "Duplikat"},
    )
    fall(
        "weder Verworfen noch Duplikat -> keine Vormerkung",
        wegen_label_zu_schliessende_issues([(14, ["Einarbeiten"])]),
        {},
    )
    fall(
        "mehrere Issues, nur die betroffenen landen in der Zuordnung",
        wegen_label_zu_schliessende_issues(
            [(1, ["Rückfrage"]), (2, ["Verworfen"]), (3, [])]
        ),
        {2: "Verworfen"},
    )
    fall(
        "altes WontDone (vor der Umbenennung aus #54) loest noch nichts aus",
        wegen_label_zu_schliessende_issues([(15, ["WontDone"])]),
        {},
    )

    fehler = [f"{name}: erwartet {erwartet!r}, bekommen {ergebnis!r}"
              for name, ergebnis, erwartet in faelle if ergebnis != erwartet]

    if fehler:
        print(f"SELBSTTEST FEHLGESCHLAGEN ({len(fehler)}/{len(faelle)}):")
        for f in fehler:
            print(f"  - {f}")
        return False

    print(f"Selbsttest: alle {len(faelle)} Faelle bestanden.")
    return True


def graphql_alle_seiten(query, owner, name):
    knoten = []
    cursor = None
    while True:
        args = ["gh", "api", "graphql", "-f", f"query={query}",
                "-f", f"owner={owner}", "-f", f"name={name}"]
        if cursor is not None:
            args += ["-f", f"cursor={cursor}"]
        lauf = subprocess.run(args, capture_output=True, text=True, check=True)
        antwort = json.loads(lauf.stdout)["data"]["repository"]
        verbindung = next(iter(antwort.values()))
        knoten.extend(verbindung["nodes"])
        if not verbindung["pageInfo"]["hasNextPage"]:
            return knoten
        cursor = verbindung["pageInfo"]["endCursor"]


def schliessen(repo, issue_nr, pr_nr, maintainer_login):
    kommentar = (
        f"Automatisch geschlossen: Pull Request #{pr_nr} wurde von "
        f"@{maintainer_login} gemergt."
    )
    subprocess.run(
        ["gh", "issue", "close", str(issue_nr), "--repo", repo,
         "--comment", kommentar],
        check=True,
    )
    print(f"Issue #{issue_nr} geschlossen (Pull Request #{pr_nr}).")


def schliessen_wegen_label(repo, issue_nr, label):
    kommentar = f"Automatisch geschlossen: Label `{label}` gesetzt."
    subprocess.run(
        ["gh", "issue", "close", str(issue_nr), "--repo", repo,
         "--comment", kommentar],
        check=True,
    )
    print(f"Issue #{issue_nr} geschlossen (Label {label}).")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selbsttest", action="store_true")
    parser.add_argument(
        "--trockenlauf", action="store_true",
        help="nur anzeigen, was geschlossen wuerde, nichts auf GitHub aendern",
    )
    args = parser.parse_args()

    if args.selbsttest:
        sys.exit(0 if selbsttest() else 1)

    repo = os.environ["GITHUB_REPOSITORY"]
    owner, name = repo.split("/", 1)
    maintainer_login = os.environ["MAINTAINER_LOGIN"]

    offene_issues_roh = graphql_alle_seiten(ISSUES_QUERY, owner, name)
    offene_issues = {n["number"] for n in offene_issues_roh}
    offene_issues_mit_labels = [
        (n["number"], [l["name"] for l in n["labels"]["nodes"]])
        for n in offene_issues_roh
    ]

    gemergte_prs = graphql_alle_seiten(MERGED_PRS_QUERY, owner, name)
    zuordnung = zu_schliessende_issues(gemergte_prs, maintainer_login)
    zu_tun_pr = {nr: pr for nr, pr in zuordnung.items() if nr in offene_issues}

    #  Ein Issue, das schon ueber den PR-Merge geschlossen wird, braucht keinen
    #  zweiten Grund - der Merge ist das staerkere Signal (tatsaechlich erledigt,
    #  nicht nur als "nicht weiter verfolgt" markiert).
    zuordnung_label = wegen_label_zu_schliessende_issues(offene_issues_mit_labels)
    zu_tun_label = {nr: label for nr, label in zuordnung_label.items()
                     if nr not in zu_tun_pr}

    if not zu_tun_pr and not zu_tun_label:
        print("Nichts zu tun: kein offenes Issue mit gemergtem Pull Request oder "
              "Endzustand-Label.")
        return

    for issue_nr, pr_nr in sorted(zu_tun_pr.items()):
        if args.trockenlauf:
            print(f"Trockenlauf: Issue #{issue_nr} wuerde geschlossen "
                  f"(Pull Request #{pr_nr}).")
        else:
            schliessen(repo, issue_nr, pr_nr, maintainer_login)

    for issue_nr, label in sorted(zu_tun_label.items()):
        if args.trockenlauf:
            print(f"Trockenlauf: Issue #{issue_nr} wuerde geschlossen "
                  f"(Label {label}).")
        else:
            schliessen_wegen_label(repo, issue_nr, label)


if __name__ == "__main__":
    main()
