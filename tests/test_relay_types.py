#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_relay_types.py
# Description: RELAY_TYPES is the single owner of "which device types are
#              relays". It replaced a literal tuple written out in three places,
#              and these tests make sure it cannot drift from Devices.xml, which
#              is where the truth actually lives.
# Author:      CliveS & Claude Opus 5
# Date:        21-09-2026
# Version:     1.0

from __future__ import annotations

import ast
import xml.etree.ElementTree as ET
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1] / "TasmotaBridge.indigoPlugin" / "Contents" / "Server Plugin"


def _declared_relay_types():
    """Every device type Devices.xml declares as an Indigo relay."""
    root = ET.parse(SERVER / "Devices.xml").getroot()
    return {d.get("id") for d in root.iter("Device") if d.get("type") == "relay"}


def test_relay_types_matches_what_devices_xml_declares(plugin_mod):
    """The constant moved the duplication from three Python literals to one
    Python set and one XML file. This is the guard on the second pair: add a
    relay type to Devices.xml without adding it here and this fails, rather than
    shipping a device that is created per channel but never switched."""
    declared = _declared_relay_types()
    assert declared, "Devices.xml declares no relay types -- the parse is wrong, not the plugin"
    assert set(plugin_mod.RELAY_TYPES) == declared, (
        f"RELAY_TYPES {sorted(plugin_mod.RELAY_TYPES)} != Devices.xml relays {sorted(declared)}")


def test_relay_types_cannot_be_mutated(plugin_mod):
    """A module-level set can be changed by any caller; a frozenset cannot."""
    assert isinstance(plugin_mod.RELAY_TYPES, frozenset)


def test_no_literal_type_tuple_has_come_back():
    """The fault this replaced was a membership test against a LITERAL list of
    tasmota types. Walk the AST rather than grepping the text: a grep would also
    match the comment explaining why the literal went, and could not tell a live
    test from a dead one."""
    tree = ast.parse((SERVER / "plugin.py").read_text(encoding="utf-8"))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for op, right in zip(node.ops, node.comparators):
            if isinstance(op, (ast.In, ast.NotIn)) and isinstance(right, (ast.Tuple, ast.List, ast.Set)):
                names = [e.value for e in right.elts
                         if isinstance(e, ast.Constant) and isinstance(e.value, str)
                         and e.value.startswith("tasmota")]
                if len(names) >= 2:
                    offenders.append((node.lineno, names))
    assert not offenders, f"literal device-type lists are back: {offenders}"


def test_every_relay_type_is_used_where_it_matters():
    """All three places that USED the literal now name the constant. Counted
    from the AST, so a use inside a comment or a string does not count."""
    tree = ast.parse((SERVER / "plugin.py").read_text(encoding="utf-8"))
    uses = [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Compare)
            and any(isinstance(c, ast.Name) and c.id == "RELAY_TYPES" for c in n.comparators)]
    assert len(uses) == 3, f"expected RELAY_TYPES in 3 membership tests, found {len(uses)} at {uses}"
