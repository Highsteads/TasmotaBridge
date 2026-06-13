#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    zoo_manifest.py
# Description: The Tasmota "device zoo" — a declarative contract table mapping a
#              Tasmota discovery payload (config + sensors, as published retained
#              to tasmota/discovery/<MAC>/config and .../sensors) to the Indigo
#              device the classifier `Plugin._detect_device_type` must produce,
#              and (for relays) the channel list `_relay_channels` must expand.
#              Driven by test_zoo.py (per-case contract + cross-cutting invariants).
#
#              REAL captures (real=True) come from CliveS's live broker; the
#              estate's two Tasmota devices are both single-relay energy plugs,
#              so the other classes (shutter/light/plain-relay/multi-relay/
#              button/sensor) are SYNTHETIC, modelled on the documented Tasmota
#              discovery shape (rl[]=relays, sht[]=shutters, lt_st=light subtype,
#              btn[]=buttons, sensors.sn.ENERGY=metering).
# Author:      CliveS & Claude Opus 4.8
# Date:        13-06-2026
# Version:     1.0

from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TasmotaCase:
    """One zoo animal: a Tasmota discovery payload and the device it must yield.
    ``expect_type`` / ``expect_channel`` are the classifier's (type_id, channel);
    ``expect_channels`` (when given) is the full active-relay channel list the
    multi-device expansion must produce."""
    name:            str
    config:          dict
    sensors:         dict
    expect_type:     str
    expect_channel:  int
    expect_channels: list = None
    real:            bool = False
    note:            str = ""


_REAL_DIR = os.path.join(os.path.dirname(__file__), "zoo_real")


def _real(stem, expect_type, expect_channel, expect_channels=None, note=""):
    with open(os.path.join(_REAL_DIR, f"{stem}.json"), encoding="utf-8") as fh:
        d = json.load(fh)
    return TasmotaCase(f"real_{stem}", d["config"], d.get("sensors", {}),
                       expect_type, expect_channel, expect_channels, real=True, note=note)


def _rl(*active):
    """Build a 32-slot rl[] list with 1s at the given 1-based channel positions."""
    out = [0] * 32
    for ch in active:
        out[ch - 1] = 1
    return out


_ENERGY = {"sn": {"ENERGY": {"Power": 0, "Total": 1.2}, "Time": "2026-06-13T12:00:00"}}
_PLAIN  = {"sn": {"Time": "2026-06-13T12:00:00"}}


CASES = [
    # ── Real captures (both single-relay energy plugs) ───────────────────────
    _real("kitchen_extractor_power_switch", "tasmotaEnergyPlug", 1, [1],
          note="real: 1 relay + ENERGY -> energy plug"),
    _real("garage_qashqai_power_switch", "tasmotaEnergyPlug", 1, [1],
          note="real: 1 relay + ENERGY -> energy plug"),

    # ── Synthetic: the rest of the classifier table ──────────────────────────
    TasmotaCase("relay_plain", {"rl": _rl(1)}, _PLAIN,
                "tasmotaRelay", 1, [1], note="1 relay, no energy -> plain relay"),
    TasmotaCase("relay_4ch", {"rl": _rl(1, 2, 3, 4)}, _PLAIN,
                "tasmotaRelay", 1, [1, 2, 3, 4],
                note="4-gang relay -> 4 channels (one device each)"),
    TasmotaCase("energy_plug", {"rl": _rl(1)}, _ENERGY,
                "tasmotaEnergyPlug", 1, [1],
                note="1 relay + ENERGY -> energy plug (the metering invariant)"),
    TasmotaCase("energy_2ch", {"rl": _rl(1, 2)}, _ENERGY,
                "tasmotaEnergyPlug", 1, [1, 2],
                note="2 relays + ENERGY -> energy plug on ch1, plain relay ch2"),
    TasmotaCase("shutter", {"sht": [1], "rl": _rl(1, 2)}, _PLAIN,
                "tasmotaShutter", 1, note="shutter wins over the relays it uses"),
    TasmotaCase("light_dimmer", {"lt_st": 1}, _PLAIN,
                "tasmotaLight", 1, note="dimmer light"),
    TasmotaCase("light_rgb", {"lt_st": 3}, _PLAIN,
                "tasmotaLight", 1, note="RGB light"),
    TasmotaCase("light_over_relay", {"lt_st": 1, "rl": _rl(1)}, _PLAIN,
                "tasmotaLight", 1, note="light wins over a relay leaf"),
    TasmotaCase("button_only", {"btn": [1]}, _PLAIN,
                "tasmotaButton", 1, note="buttons, no relay/light/shutter -> button"),
    TasmotaCase("sensor_only", {}, _ENERGY,
                "tasmotaSensor", 0, note="no relay/light/shutter/button -> sensor (ch 0)"),
    TasmotaCase("empty", {}, {},
                "tasmotaSensor", 0, note="defensive: empty config -> sensor, no crash"),
]
