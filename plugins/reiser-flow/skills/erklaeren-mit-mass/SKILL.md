---
name: erklaeren-mit-mass
description: >
  Prüft jede Erklärung darauf, ob sie ihren Platz verdient — in Code-Kommentaren,
  Commit-Meldungen, Pull-Request-Texten, Issue-Kommentaren, README- und Doku-Dateien.
  Grundsatz: WARUM statt WAS, und so wenig wie möglich, weil jede Zeile Dokumentation
  gelesen und gepflegt werden muss — von Nutzern, die dafür oft keine Zeit haben. Lade
  diesen Skill AKTIV vor jedem Kommentar, jeder Commit-Meldung, jedem PR-Text, Issue
  oder Doku-Abschnitt, auch ungefragt — nicht erst, wenn er zufällig schon geladen ist
  oder jemand nachfragt. Ebenso, wenn zu entscheiden ist, ob etwas überhaupt
  dokumentiert gehört, und wenn Text gekürzt oder von Füllmaterial befreit werden soll.
---

# Erklären mit Maß

## Der Maßstab

Zwei Regeln, die zusammen gehören und einzeln in die Irre führen:

1. **WARUM statt WAS.** Was der Code tut, steht im Code. Was ihn erklärt, sind die
   Gründe: eine versteckte Bedingung, ein Vorfall, eine verworfene Alternative.
2. **So wenig wie möglich.** Dokumentation ist kein Gratisgewinn. Sie wird gelesen,
   veraltet und muss gepflegt werden. Jede Zeile, die nichts trägt, macht die
   tragenden Zeilen schwerer auffindbar.

Regel 1 allein erzeugt die typische Fehlform: lange, gut begründete Absätze, die
niemand liest. Erst Regel 2 macht sie brauchbar.

## Die Probe

Vor jedem Absatz, den du schreiben willst:

**Was verliert der Leser, wenn das hier fehlt?** Fällt die Antwort schwer, streich ihn.

Und danach: **Was davon steht schon woanders?** Ein Verweis ist billiger als eine
zweite Fassung — und die zweite Fassung ist die, die veraltet.

## Woran man zu viel erkennt

- Der Text erklärt die eigene Entscheidung, statt die Sache zu benennen
  („hier bewusst keine Zahl, die beim nächsten Mal schon wieder falsch ist")
- Er begründet, was niemand in Frage gestellt hat
- Er wiederholt in Prosa, was die darunterstehende Tabelle, Signatur oder Liste zeigt
- Er erzählt den Weg statt das Ergebnis („zuerst habe ich …, dann …")
- Dieselbe Begründung steht an mehreren Stellen zugleich (Code-Kommentar UND
  Commit-Meldung UND PR-Text) statt an der einen, die laut Tabelle unten zuständig ist
- Doku im Repo setzt einen Kontrast zur eigenen Vorgeschichte voraus, den nur versteht,
  wer sie miterlebt hat

**Beispiel.** Statt

> Wie viele Prüfungen es sind, steht in der Schlusszeile dieses Berichts
> („Ergebnis: … bestanden, … durchgefallen"), die Abschnitte sind darin einzeln
> überschrieben — hier bewusst keine Zahl, die beim nächsten neuen Check schon
> wieder falsch ist.

reicht

> Anzahl und Ergebnis stehen am Ende des Berichts.

Der Rest war Begründung für eine Entscheidung, die niemand nachvollziehen muss —
die gehört, wenn überhaupt, in die Commit-Meldung.

**Beispiel für den Historienbezug.** Statt

> Das Bot-Konto ist keiner mehr — es ist eine eigene GitHub App.

reicht

> Das Bot-Konto ist eine eigene GitHub App.

Der Kontrast zum früheren Konto ergibt nur für jemanden Sinn, der die eigene Historie
kennt — ein Projekt, das reiser-flow neu einbindet, hatte nie ein anderes Bot-Konto.
Das gilt nur für Doku im Repo, die auch fremde Projekte lesen: In Commit-Meldung und
Pull Request gehört Vorgeschichte gerade hin (siehe Tabelle unten).

## Wo was hingehört

| | trägt |
|---|---|
| Code-Kommentar | die nicht offensichtliche Bedingung, der Fallstrick, der Grund für eine ungewöhnliche Lösung |
| Commit-Meldung | warum diese Änderung, was sie ersetzt, welche Alternative verworfen wurde |
| Pull Request | was ein Prüfer wissen muss, um zuzustimmen; alles Weitere als Verweis aufs Issue |
| Issue | die Sache selbst, die Entscheidung, der Stand |
| Doku im Repo | was länger gilt als ein Commit |

## Wenn es länger sein darf

Kürze ist kein Selbstzweck. Länger darf werden, was Schaden verhindert: ein Fallstrick,
der schon einmal Zeit gekostet hat, eine Reihenfolge, deren Vertauschen Daten zerstört,
eine Regel, die ohne ihren Grund willkürlich wirkt und deshalb umgangen würde.

Der Unterschied ist nicht die Länge, sondern ob jemand ohne den Text einen Fehler macht.
