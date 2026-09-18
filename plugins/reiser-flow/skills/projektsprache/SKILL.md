---
name: projektsprache
description: >
  Legt fest, in welcher Sprache ein Softwareprojekt nach außen kommuniziert: Commit-
  Nachrichten, Pull-Request- und Issue-Texte, Kommentare auf GitHub, Kommentare und
  Bezeichner im Code, Dokumentation und Chat-Antworten zum Projekt. Gilt IMMER und ohne
  besonderen Anlass — lade diesen Skill in jeder Sitzung an einem Softwareprojekt,
  unabhängig vom eigentlichen Thema. Überschreibbar durch einen gleichnamigen Skill im
  Projekt selbst.
---

# Projektsprache

**Deutsch** — für jedes Softwareprojekt, das reiser-flow verwendet, sofern das Projekt
nichts anderes festlegt (siehe unten).

Das gilt für alles, was sich an Menschen richtet: Commit-Nachrichten, Pull-Request- und
Issue-Texte (auch neu angelegte), Kommentare auf GitHub, Kommentare im Code,
Dokumentation (README/LIESMICH, `SKILL.md`, `CLAUDE.md`, Docstrings) — und für
Chat-Antworten, wenn es um dieses Projekt geht. Auch Bezeichner im Code (Variablen,
Funktionen, Module, Dateinamen), soweit die Sprache oder ein externes Werkzeug das nicht
verhindert.

**Ausgenommen**, weil dort eine andere Sprache technisch vorgegeben oder unausweichlich
ist:

- Schlüsselwörter und Syntax der Programmiersprache selbst.
- Namen, die eine externe Bibliothek, ein Framework oder eine API vorschreiben (eine
  überschriebene Methode heißt, wie die Basisklasse sie nennt; ein JSON-Feld heißt, wie
  die Gegenstelle es erwartet).
- Dateinamen, die ein Werkzeug fest erwartet (`README.md` für GitHubs eigene Anzeige,
  `.github/workflows/*.yml`, `package.json`, `LICENSE`).
- Wörtliche Zitate aus Fehlermeldungen oder Tool-/Bibliotheksausgaben.

## Andere Projektsprache

Ein Projekt legt seine eigene Sprache fest, indem es einen **eigenen Skill namens
`projektsprache`** mitbringt (z. B. unter `.claude/skills/projektsprache/`) — der
projekteigene Skill ist spezifischer und überlagert diesen hier.

Wer reiser-flow für ein eigenes, nicht-deutschsprachiges Umfeld übernimmt, ändert
stattdessen direkt die Sprache in dieser Datei — dann gilt sie für alle Projekte, die von
dort laden.
