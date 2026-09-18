#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scoped Labels nach dem Vorbild von GitLab: "Scope::Wert"."""
import sys

TRENNER = "::"


def scope(label):
    """Der Teil vor "::", oder None, wenn das Label nicht gescoped ist."""
    kopf, trenner, _ = label.partition(TRENNER)
    if not trenner or not kopf:
        return None
    return kopf


def wert(label):
    """Der Teil hinter "::", oder None, wenn das Label nicht gescoped ist."""
    kopf, trenner, rest = label.partition(TRENNER)
    if not trenner or not kopf:
        return None
    return rest


def geschwister_im_scope(alle_labels, neues_label):
    """Andere Label aus alle_labels mit demselben Scope wie neues_label.

    GitLab-Vorbild: pro Scope gilt gleichzeitig hoechstens ein Wert. Ein nicht
    gescoptes Label (z.B. "Einarbeiten") hat nie Geschwister.
    """
    s = scope(neues_label)
    if s is None:
        return []
    return [l for l in alle_labels if l != neues_label and scope(l) == s]


def selbsttest():
    fehler = []

    def pruefe(label, erwarteter_scope, erwarteter_wert):
        s = scope(label)
        w = wert(label)
        if (s, w) != (erwarteter_scope, erwarteter_wert):
            fehler.append("%r: (%r, %r) statt (%r, %r)"
                          % (label, s, w, erwarteter_scope, erwarteter_wert))

    pruefe("Modell::Opus", "Modell", "Opus")
    pruefe("v::5", "v", "5")
    pruefe("Aufwand::extra hoch", "Aufwand", "extra hoch")
    #  Ein Scope, den weder geschuetzt.py noch modellwahl.py kennen - die
    #  Erkennung selbst darf trotzdem nichts von den beiden wissen.
    pruefe("Prioritaet::hoch", "Prioritaet", "hoch")

    #  Nicht gescoped: kein Trenner, oder Trenner am Rand.
    pruefe("Einarbeiten", None, None)
    pruefe("", None, None)
    pruefe("::ohne-scope", None, None)
    pruefe("ohne-wert::", "ohne-wert", "")

    #  Mehrfaches "::" gehoert komplett zum Wert - nur die erste Trennung zaehlt.
    pruefe("v::5::6", "v", "5::6")

    def pruefe_geschwister(alle_labels, neues_label, erwartet):
        e = geschwister_im_scope(alle_labels, neues_label)
        if sorted(e) != sorted(erwartet):
            fehler.append("geschwister_im_scope(%r, %r): %r statt %r"
                          % (alle_labels, neues_label, e, erwartet))

    pruefe_geschwister(
        ["Einarbeiten", "Modell::Opus", "Modell::Sonnet"], "Modell::Sonnet",
        ["Modell::Opus"],
    )
    #  Das neue Label selbst ist kein Geschwister von sich.
    pruefe_geschwister(["Modell::Sonnet"], "Modell::Sonnet", [])
    #  Nicht gescopt: nie Geschwister, unabhaengig vom Rest der Liste.
    pruefe_geschwister(["Einarbeiten", "Untersuche"], "Einarbeiten", [])
    #  Andere Scopes bleiben unberuehrt.
    pruefe_geschwister(
        ["Modell::Sonnet", "Aufwand::hoch", "v::5"], "Modell::Sonnet", [],
    )
    #  Mehrere Geschwister im selben Scope werden alle gefunden.
    pruefe_geschwister(
        ["Aufwand::niedrig", "Aufwand::hoch", "Aufwand::maximal"],
        "Aufwand::maximal",
        ["Aufwand::niedrig", "Aufwand::hoch"],
    )

    gesamt = 14
    for f in fehler:
        print("FEHLER: " + f)
    print("%d von %d Pruefungen bestanden." % (gesamt - len(fehler), gesamt))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(selbsttest())
