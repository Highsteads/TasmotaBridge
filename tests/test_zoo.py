#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_zoo.py
# Description: Drives the Tasmota device zoo (zoo_manifest.CASES). Per-animal
#              contract (discovery payload -> classifier (type, channel) and the
#              relay channel expansion) plus cross-cutting invariants the
#              classifier must never break.
# Author:      CliveS & Claude Opus 4.8
# Date:        13-06-2026

from __future__ import annotations

import pytest

from zoo_manifest import CASES

# Valid Tasmota device types the classifier may emit (from Devices.xml).
KNOWN_TYPES = {
    "tasmotaRelay", "tasmotaEnergyPlug", "tasmotaLight", "tasmotaShutter",
    "tasmotaButton", "tasmotaSensor",
}
_RELAY_TYPES = {"tasmotaRelay", "tasmotaEnergyPlug"}

_IDS = [c.name for c in CASES]


def _detect(plugin_mod, case):
    # _detect_device_type is an instance method but uses no `self`; call it
    # unbound with a throwaway self so the zoo tests the real plugin logic.
    return plugin_mod.Plugin._detect_device_type(None, case.config, case.sensors)


def _channels(plugin_mod, case):
    return plugin_mod.Plugin._relay_channels(None, case.config)


# ── Per-animal contract ──────────────────────────────────────────────────────

@pytest.mark.parametrize("case", CASES, ids=_IDS)
def test_zoo_classification(plugin_mod, case):
    """Each discovery payload classifies to the expected (type, channel)."""
    got = _detect(plugin_mod, case)
    assert got == (case.expect_type, case.expect_channel), (
        f"{case.name}: got {got}, expected {(case.expect_type, case.expect_channel)} ({case.note})"
    )


@pytest.mark.parametrize(
    "case", [c for c in CASES if c.expect_channels is not None],
    ids=[c.name for c in CASES if c.expect_channels is not None],
)
def test_zoo_channel_expansion(plugin_mod, case):
    """Multi-relay devices expand to exactly the active channels (one device each)."""
    assert _channels(plugin_mod, case) == case.expect_channels, (
        f"{case.name}: channels {_channels(plugin_mod, case)} != {case.expect_channels}"
    )


# ── Cross-cutting invariants ─────────────────────────────────────────────────

@pytest.mark.parametrize("case", CASES, ids=_IDS)
def test_invariant_only_known_types(plugin_mod, case):
    type_id, _ch = _detect(plugin_mod, case)
    assert type_id in KNOWN_TYPES, f"{case.name}: emitted unknown type {type_id!r}"


@pytest.mark.parametrize("case", CASES, ids=_IDS)
def test_invariant_deterministic(plugin_mod, case):
    assert _detect(plugin_mod, case) == _detect(plugin_mod, case), f"{case.name}: non-deterministic"


@pytest.mark.parametrize("case", CASES, ids=_IDS)
def test_invariant_energy_never_dropped(plugin_mod, case):
    """A device with at least one relay AND an ENERGY sensor must classify as an
    energy plug, never a plain relay — the metering capability must not be lost
    at creation (the Tasmota analogue of the battery/colour 'capability never
    dropped' rule)."""
    sn = (case.sensors or {}).get("sn", {})
    has_relay  = any(case.config.get("rl", []) or [])
    has_energy = isinstance(sn, dict) and "ENERGY" in sn
    if has_relay and has_energy:
        type_id, _ch = _detect(plugin_mod, case)
        assert type_id == "tasmotaEnergyPlug", (
            f"{case.name}: relay+ENERGY classified as {type_id}, lost metering"
        )


@pytest.mark.parametrize("case", CASES, ids=_IDS)
def test_invariant_shutter_and_light_beat_relay(plugin_mod, case):
    """A shutter (sht[]) or a light (lt_st>=dimmer) is never demoted to a relay
    even though it drives the same underlying relay hardware."""
    type_id, _ch = _detect(plugin_mod, case)
    if any(case.config.get("sht", []) or []):
        assert type_id == "tasmotaShutter", f"{case.name}: shutter classified as {type_id}"
    elif case.config.get("lt_st", 0) >= 1:
        assert type_id == "tasmotaLight", f"{case.name}: light classified as {type_id}"


@pytest.mark.parametrize(
    "case", [c for c in CASES if c.expect_channels is not None],
    ids=[c.name for c in CASES if c.expect_channels is not None],
)
def test_invariant_channels_match_relays(plugin_mod, case):
    """The expanded channel list matches every active relay in rl[] — no relay
    channel silently dropped, none invented."""
    rl = case.config.get("rl", []) or []
    expected = [i + 1 for i, v in enumerate(rl) if v]
    assert _channels(plugin_mod, case) == expected, (
        f"{case.name}: channels {_channels(plugin_mod, case)} != active relays {expected}"
    )
