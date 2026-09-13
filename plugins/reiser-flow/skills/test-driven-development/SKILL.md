---
name: test-driven-development
description: >
  Testgetriebenes Vorgehen als Voreinstellung für alle Softwareprojekte dieses Nutzers:
  erst den Test bauen und ihn rot nachweisen, dann die Funktionalität — immer zwei Runden,
  nie eine. Auch dann, wenn der Test in der eigenen Umgebung gar nicht ausgeführt werden
  kann; dann wird der Rot-Nachweis ausdrücklich angefordert. Enthält außerdem, wie eine
  bestehende Testsuite per Mutationstest auf ihre Wirksamkeit geprüft wird und wie man
  Tests baut, die nicht denselben blinden Fleck haben wie der Code. Nutze diesen Skill bei
  jeder neuen Funktion, bei jedem gemeldeten Fehler, bevor du eine Zeile Produktivcode
  schreibst, und wenn zu klären ist, ob ein bestehender Test überhaupt etwas prüft.
---

# Testgetrieben arbeiten

Voreinstellung für alle Softwareprojekte dieses Nutzers. Immer ZWEI Runden, nie eine.

## Runde 1 — der Test, und der Nachweis, dass er rot ist

1. Verstehen, was die Funktion leisten soll (bzw. was der gemeldete Fehler ist).
2. Den Test schreiben, der genau das prüft.
3. **Den Test rot sehen.** Nicht vermuten, dass er rot wäre — laufen lassen.
4. Erst melden „Test steht und schlägt fehl", dann weiter.

Ohne Schritt 3 ist der Test wertlos. Ein Test, der noch nie rot war, prüft möglicherweise
gar nichts.

### Wenn die Umgebung fehlt

Manchmal lässt sich der Test hier nicht ausführen — Excel/VBA, eine proprietäre
Toolchain, Hardware, eine fremde Cloud. Dann **nicht stillschweigend weiterbauen**,
sondern:

- den Test ausliefern,
- ausdrücklich schreiben, **welcher** Test **mit welcher Meldung** fehlschlagen MUSS,
- den Nutzer den Rot-Nachweis führen lassen und auf sein Ergebnis warten,
- erst danach die Funktionalität bauen.

Will der Nutzer den Zwischenschritt nicht, sagt er das — dann beides in einem Aufwasch,
aber mit der Erwartung ausdrücklich dokumentiert.

## Runde 2 — die Funktionalität

So lange bauen, bis der Test grün ist. **Nicht den Test anpassen, damit er passt.** War
der Test falsch, ist das ein eigener Befund und wird als solcher benannt.

## Bei einem gemeldeten Fehler

Dieselbe Reihenfolge, verschärft: zuerst die Prüfung schreiben, die den Fehler **am
echten Artefakt des Nutzers** rot macht — seiner Datei, seinem Datensatz, seinem Log.
Nicht an einem konstruierten Minimalbeispiel. Ein nachgebautes Beispiel bestätigt meist
nur die eigene Fehlannahme. Erst wenn die Prüfung den gemeldeten Zustand reproduziert,
wird repariert.

## Der gefährlichste Fall: der Test mit demselben blinden Fleck

Entstehen Test und Code aus derselben Annahme, ist der Test grün und der Code falsch.
Wie oft das schon passiert ist und woran man es erkennt: `fremde-gegenlese`.

**Gegenmittel im eigenen Kopf:** den Test aus einer ANDEREN Richtung bauen als den Code.
Andere API, andere Datenquelle, andere Blickrichtung. Rechnet der Code vorwärts, prüft
der Test rückwärts. Konkret: *Bestimmt der Code eine Größe mit einer Funktion, darf der
Test sie nicht mit derselben Funktion nachprüfen.*

**Gegenmittel von außen:** `fremde-gegenlese`, wenn der Nutzer sie anfordert. Der eigene
Kopf kommt an diesen Fehler nicht zuverlässig heran — er ist der Fehler. Genau deshalb
wiegt das Gegenmittel im eigenen Kopf hier umso schwerer: Es ist im Regelfall das
einzige.

## Bestehende Testsuiten: Mutationstest

Soll eine vorhandene Testsuite Vertrauen tragen, prüfe den Prüfer: definierte Fehler
einbauen und verlangen, dass GENAU der zuständige Test rot wird — und nach dem
Zurücknehmen wieder grün.

**Jede Prüfung hat eine Mutation, oder sie zählt nicht.**

Drei Fallen dabei:

- Vor dem ersten Eingriff sicherstellen, dass alles grün ist. Ein Test, der schon vorher
  rot war, „erkennt" jede Sabotage.
- Nur an Prüfungen ohne Nebenwirkung ansetzen. Ein Abschnitt, der selbst repariert, hebt
  die Sabotage vor der Prüfung wieder auf.
- Eine Rücknahme darf ihr Ziel NIE über eine Eigenschaft suchen, die die Sabotage selbst
  verändert hat — sonst trifft sie das falsche Objekt.

Eine Mutation, die auf jedem System gleich wirkt, ist mehr wert als eine raffinierte: ein
eingebauter Backslash schlägt auf Linux an und auf Windows nicht, und dann prüft die
Mutation das Betriebssystem statt den Test.

## Statische Prüfer

Jede neue Regel doppelt gegenprüfen: an einem künstlich eingebauten Fehler (schlägt an)
UND an korrektem Code (schlägt nicht an). Eine Regel, die auf beides anspringt, ist
genauso wertlos wie eine, die auf nichts anspringt.

Achte dabei auf Prüfungen, die aus struktureller Ursache **immer** anschlagen — etwa
wenn der Prüfling in einem temporären Verzeichnis unter einem anderen Namen liegt und
eine Regel am Dateinamen hängt. Solche Regeln sind dauerhaft rot oder dauerhaft grün,
und beide Mutationen dazu sind leer.

## Was NICHT gemeint ist

- Kein Testgerüst für einen Einzeiler, eine Frage oder eine Wegwerfanalyse.
- Keine Tests um der Abdeckung willen. Jeder Test hat einen Anlass, und der Anlass gehört
  als Kommentar dazu.
