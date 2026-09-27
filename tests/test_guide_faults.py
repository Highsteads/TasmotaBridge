#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_guide_faults.py
# Description: Regression tests for the faults found while writing the plain
#              English guide (0.8.0): button payload shapes, Log Level, Colour
#              Mode, undeclared report states, ESP32 variant firmware, the
#              Status reply, broker changes after a Configure save, and the
#              setting that never did anything. No broker, no hardware: each
#              test drives the plugin's own parsing and decision code against
#              fake devices whose states come from Devices.xml.
# Author:      CliveS & Claude Opus 5.5
# Date:        27-09-2026
# Version:     1.0

from __future__ import annotations

import ast
import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SERVER = Path(__file__).resolve().parents[1] / "TasmotaBridge.indigoPlugin" / "Contents" / "Server Plugin"

# States Indigo gives a device class itself, so Devices.xml never declares them.
_NATIVE = {
    "relay":  {"onOffState"},
    "dimmer": {"onOffState", "brightnessLevel"},
    "sensor": {"onOffState"},
    "custom": set(),
}


def _declared_states():
    root = ET.parse(SERVER / "Devices.xml").getroot()
    out = {}
    for d in root.iter("Device"):
        states = {s.get("id") for s in d.iter("State")}
        states |= _NATIVE.get(d.get("type"), set())
        if d.get("subType") == "kEnergyMeter":
            states |= {"curEnergyLevel", "accumEnergyTotal"}
        out[d.get("id")] = states
    return out


DECLARED = _declared_states()


class FakeDev:
    """A device that refuses a write to a state its type does not declare,
    as Indigo does (it logs and drops it)."""

    _next_id = 1000

    def __init__(self, type_id, topic="tasmota_000001", channel="1", props=None):
        FakeDev._next_id += 1
        self.id           = FakeDev._next_id
        self.name         = f"{type_id} {self.id}"
        self.deviceTypeId = type_id
        self.address      = "AABBCC000001"
        self.pluginProps  = {"topic": topic, "channel": channel, "address": "AABBCC000001"}
        self.pluginProps.update(props or {})
        self.states       = {k: "" for k in DECLARED[type_id]}
        self.written      = {}

    def updateStateOnServer(self, key, value, **_kw):
        if key not in DECLARED[self.deviceTypeId]:
            raise KeyError(f"{self.deviceTypeId} does not declare state {key!r}")
        self.written[key] = value
        self.states[key]  = value

    def updateStatesOnServer(self, updates):
        for u in updates:
            self.updateStateOnServer(u["key"], u["value"])

    def replacePluginPropsOnServer(self, props):
        self.pluginProps = dict(props)


class FakeDevices:
    def __init__(self, devs):
        self._devs = {d.id: d for d in devs}

    def iter(self, _filter=None):
        return list(self._devs.values())

    def __getitem__(self, dev_id):
        return self._devs[dev_id]

    def __contains__(self, dev_id):
        return dev_id in self._devs


@pytest.fixture
def make_plugin(plugin_mod, monkeypatch):
    """A Plugin instance built without Indigo's PluginBase.__init__."""

    def _make(devs=(), prefs=None):
        monkeypatch.setattr(plugin_mod.indigo, "devices", FakeDevices(devs))
        trig = MagicMock()
        monkeypatch.setattr(plugin_mod.indigo, "trigger", trig)
        p = object.__new__(plugin_mod.Plugin)
        p.logger            = MagicMock()
        p.pluginPrefs       = dict(prefs or {})
        p.event_triggers    = {}
        p.devices_by_mac    = {}
        p.last_seen         = {}
        p.discovery_cache   = {}
        p.mqtt_client       = None
        p.mqtt_connected    = False
        p.startup_time      = 0.0
        p.log_raw           = False
        p.auto_create       = True
        p.indigo_log_handler = logging.Handler()
        p._set_broker(plugin_mod.resolve_broker(prefs or {}))
        p.trigger_mock      = trig
        return p

    return _make


class FakeTrigger:
    def __init__(self, tid, action="", button="", address=""):
        self.id           = tid
        self.pluginTypeId = "buttonPressed"
        self.pluginProps  = {"targetAction": action, "targetButton": button, "targetAddress": address}


# ── Buttons ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("payload, expected", [
    ({"Button1": {"Action": "SINGLE"}}, [(1, "SINGLE")]),   # SetOption73 1 (Tasmota docs)
    ({"Button2": "hold"},              [(2, "HOLD")]),      # flat shape
    ({"Button3": {"Action": "DOUBLE"}, "Button4": "CLEAR"}, [(3, "DOUBLE"), (4, "CLEAR")]),
    ({"Button1": {}},                  []),
    ({"ButtonTopic": "0"},             []),
    ({"POWER": "ON"},                  []),
])
def test_parse_button_events_reads_both_shapes(plugin_mod, payload, expected):
    assert plugin_mod.parse_button_events(payload) == expected


def test_nested_button_press_sets_last_action_and_fires_filtered_trigger(make_plugin):
    btn = FakeDev("tasmotaButton")
    p = make_plugin([btn])
    p.event_triggers = {
        1: FakeTrigger(1, action="SINGLE"),
        2: FakeTrigger(2, action="DOUBLE"),
        3: FakeTrigger(3, action=""),
    }
    p._handle_stat("tasmota_000001", "RESULT", json.dumps({"Button1": {"Action": "SINGLE"}}))
    assert btn.written["lastAction"] == "SINGLE"
    assert btn.written["lastButton"] == 1
    fired = [c.args[0].id for c in p.trigger_mock.execute.call_args_list]
    assert sorted(fired) == [1, 3], "the SINGLE and Any-action triggers fire, DOUBLE does not"


# ── Log Level ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value, level", [
    ("DEBUG", logging.DEBUG), ("INFO", logging.INFO),
    ("WARNING", logging.WARNING), ("ERROR", logging.ERROR),
    ("", logging.INFO), (None, logging.INFO), ("nonsense", logging.INFO),
])
def test_log_level_for_every_menu_value(plugin_mod, value, level):
    assert plugin_mod.log_level_for(value) == level


def test_log_level_applied_at_start(make_plugin):
    p = make_plugin(prefs={"logLevel": "WARNING"})
    p.startup()   # no broker: returns after logging, but the level is set first
    assert p.indigo_log_handler.level == logging.WARNING


@pytest.mark.parametrize("value, level", [
    ("ERROR", logging.ERROR), ("WARNING", logging.WARNING), ("DEBUG", logging.DEBUG), ("INFO", logging.INFO),
])
def test_log_level_applied_on_save_without_restart(make_plugin, value, level):
    p = make_plugin()
    p.closedPrefsConfigUi({"logLevel": value}, False)
    assert p.indigo_log_handler.level == level


# ── Colour Mode ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("subtype, data, mode", [
    ("1", {"Dimmer": 40}, "dimmer"),
    ("2", {"CT": 300}, "ct"),
    ("3", {"Color": "FF0000"}, "rgb"),
    ("4", {"White": 0, "Color": "FF000000"}, "rgb"),
    ("4", {"White": 60}, "white"),
    ("5", {"White": 0}, "rgb"),
    ("5", {"White": 80, "CT": 250}, "ct"),
    ("5", {"Dimmer": 50}, None),          # no White value: cannot tell
    ("", {"Dimmer": 50}, None),
])
def test_light_colour_mode(plugin_mod, subtype, data, mode):
    assert plugin_mod.light_colour_mode(subtype, data) == mode


def test_colour_mode_is_written_from_a_light_result(make_plugin):
    light = FakeDev("tasmotaLight", props={"lightSubtype": "5"})
    p = make_plugin([light])
    p._handle_stat("tasmota_000001", "RESULT", json.dumps({"POWER": "ON", "Dimmer": 70, "White": 0, "Color": "FF00000000"}))
    assert light.written["colorMode"] == "rgb"
    p._handle_stat("tasmota_000001", "RESULT", json.dumps({"White": 70, "CT": 300}))
    assert light.written["colorMode"] == "ct"


# ── Regular report states declared on every type ─────────────────────────────

_STATE_REPORT = {
    "Time": "2026-09-27T12:00:00", "Uptime": "0T01:02:03", "RestartReason": "Power On",
    "POWER": "ON", "Dimmer": 50, "White": 0,
    "Wifi": {"RSSI": 80, "Signal": -60},
}


@pytest.mark.parametrize("type_id", sorted(DECLARED))
def test_regular_report_writes_only_declared_states(make_plugin, type_id):
    """Before 0.8.0 lights, buttons, sensors and shutters were sent signal,
    uptime and lastSeen (shutters rssi too) without declaring them, so Indigo
    dropped each write. FakeDev raises on an undeclared write."""
    dev = FakeDev(type_id, props={"lightSubtype": "5"})
    p = make_plugin([dev])
    p._handle_state(dev, json.dumps(_STATE_REPORT))
    for key in ("rssi", "signal", "uptime", "lastSeen", "restartReason"):
        assert key in dev.written, f"{type_id}: {key} not written"


# ── Firmware ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("hardware, family, file", [
    ("ESP8266EX", "ESP8266", "tasmota/release/tasmota.bin.gz"),
    ("ESP8285H16", "ESP8266", "tasmota/release/tasmota.bin.gz"),
    ("ESP32-D0WD-V3", "ESP32", "tasmota32/release/tasmota32.bin"),
    ("ESP32-D0WD-V3 v3.0", "ESP32", "tasmota32/release/tasmota32.bin"),
    ("ESP32-PICO-V3-02", "ESP32", "tasmota32/release/tasmota32.bin"),
    ("ESP32-S0WD", "ESP32-SOLO1", "tasmota32/release/tasmota32solo1.bin"),
    ("ESP32-C3 v0.4", "ESP32-C3", "tasmota32/release/tasmota32c3.bin"),
    ("ESP8685", "ESP32-C3", "tasmota32/release/tasmota32c3.bin"),
    ("ESP32-S3", "ESP32-S3", "tasmota32/release/tasmota32s3.bin"),
    ("ESP32-S3-PICO-1", "ESP32-S3", "tasmota32/release/tasmota32s3.bin"),
    ("ESP32-S2FH4", "ESP32-S2", "tasmota32/release/tasmota32s2.bin"),
    ("ESP32-C6", "ESP32-C6", "tasmota32/release/tasmota32c6.bin"),
    ("ESP32-C2", "ESP32-C2", "tasmota32/release/tasmota32c2.bin"),
])
def test_chip_family_picks_the_matching_firmware(plugin_mod, hardware, family, file):
    assert plugin_mod.chip_family(hardware) == family
    assert plugin_mod.OTA_URLS[family] == f"http://ota.tasmota.com/{file}"


@pytest.mark.parametrize("hardware", ["", None, "ESP32-C5", "ESP32-H2", "ESP32-P4", "RP2040"])
def test_unknown_chip_is_refused(plugin_mod, hardware):
    assert plugin_mod.chip_family(hardware) is None


def test_upgrade_refuses_an_unknown_chip_and_sends_nothing(make_plugin, monkeypatch):
    dev = FakeDev("tasmotaRelay", props={"ip": "192.168.1.50"})
    p = make_plugin([dev])
    monkeypatch.setattr(p, "_detect_device_architecture", lambda d: None)
    sent = []
    monkeypatch.setattr(p, "_publish_command", lambda d, c, pl="": sent.append((c, pl)))
    p.actionUpgradeFirmware(None, dev)
    assert sent == []
    assert p.logger.warning.called


def test_upgrade_sends_the_c3_firmware_to_a_c3(make_plugin, monkeypatch):
    dev = FakeDev("tasmotaRelay", props={"ip": "192.168.1.50", "chip": "ESP32-C3"})
    p = make_plugin([dev])
    sent = []
    monkeypatch.setattr(p, "_publish_command", lambda d, c, pl="": sent.append((c, pl)))
    p.actionUpgradeFirmware(None, dev)
    assert sent == [("Backlog", "OtaUrl http://ota.tasmota.com/tasmota32/release/tasmota32c3.bin; Upgrade 1")]


def test_old_esp32_cache_is_probed_again(make_plugin, monkeypatch):
    """0.7.x cached every ESP32 as plain 'ESP32'. That cannot tell a C3 from
    a classic ESP32, so it must not be trusted."""
    dev = FakeDev("tasmotaRelay", props={"ip": "192.168.1.50", "arch": "ESP32"})
    p = make_plugin([dev])
    probed = []

    class _Resp:
        status_code = 200

        def json(self):
            return {"StatusFWR": {"Hardware": "ESP32-C3 v0.4"}}

    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: probed.append(1) or _Resp())
    assert p._detect_device_architecture(dev) == "ESP32-C3"
    assert probed and dev.pluginProps["chip"] == "ESP32-C3"


def test_firmware_log_names_a_menu_item_that_exists():
    menu = {m.findtext("Name") for m in ET.parse(SERVER / "MenuItems.xml").getroot().iter("MenuItem")}
    src = (SERVER / "plugin.py").read_text(encoding="utf-8")
    assert "Open Tasmota Device Page..." not in src
    assert "Upgrade Tasmota Firmware..." in menu


# ── Request Status Update ────────────────────────────────────────────────────

def test_status0_reply_updates_states(make_plugin):
    plug = FakeDev("tasmotaEnergyPlug")
    p = make_plugin([plug])
    reply = {
        "Status": {"Topic": "tasmota_000001"},
        "StatusFWR": {"Version": "15.0.1(release-tasmota)", "Hardware": "ESP8285H16"},
        "StatusSNS": {"Time": "2026-09-27T12:00:00",
                      "ENERGY": {"Power": 42, "Total": 1.5, "Voltage": 240}},
        "StatusSTS": {"Time": "2026-09-27T12:00:00", "Uptime": "0T00:10:00",
                      "POWER": "ON", "Wifi": {"RSSI": 76, "Signal": -62}},
    }
    p._handle_stat("tasmota_000001", "STATUS0", json.dumps(reply))
    assert plug.written["onOffState"] is True
    assert plug.written["rssi"] == 76
    assert plug.written["signal"] == -62
    assert plug.written["uptime"] == "0T00:10:00"
    assert plug.written["curEnergyLevel"] == 42.0
    assert plug.written["voltage"] == 240.0


def test_older_split_status_replies_update_states(make_plugin):
    relay = FakeDev("tasmotaRelay")
    p = make_plugin([relay])
    p._handle_stat("tasmota_000001", "STATUS11",
                   json.dumps({"StatusSTS": {"POWER": "OFF", "Wifi": {"RSSI": 50, "Signal": -75}}}))
    assert relay.written["onOffState"] is False
    assert relay.written["rssi"] == 50


# ── Broker settings after a Configure save ───────────────────────────────────

_BASE = {"mqttHost": "192.168.1.20", "mqttPort": "1883", "mqttUsername": "u",
         "mqttPassword": "p", "mqttTLS": False}


@pytest.mark.parametrize("change", [
    {"mqttPort": "8883"}, {"mqttUsername": "other"}, {"mqttPassword": "new"}, {"mqttTLS": True},
    {"mqttHost": "192.168.1.21"},
])
def test_any_broker_change_reconnects(plugin_mod, make_plugin, monkeypatch, change):
    for name in ("MQTT_BROKER", "MQTT_USERNAME", "MQTT_PASSWORD"):
        monkeypatch.setattr(plugin_mod, name, "")
    p = make_plugin(prefs=_BASE)
    calls = []
    monkeypatch.setattr(p, "_mqtt_disconnect", lambda: calls.append("down"))
    monkeypatch.setattr(p, "_mqtt_connect", lambda: calls.append("up"))
    p.closedPrefsConfigUi({**_BASE, **change}, False)
    assert calls == ["down", "up"]
    assert plugin_mod.resolve_broker({**_BASE, **change}) == p._broker()


def test_unchanged_broker_does_not_reconnect(plugin_mod, make_plugin, monkeypatch):
    for name in ("MQTT_BROKER", "MQTT_USERNAME", "MQTT_PASSWORD"):
        monkeypatch.setattr(plugin_mod, name, "")
    p = make_plugin(prefs=_BASE)
    calls = []
    monkeypatch.setattr(p, "_mqtt_disconnect", lambda: calls.append("down"))
    monkeypatch.setattr(p, "_mqtt_connect", lambda: calls.append("up"))
    p.closedPrefsConfigUi(dict(_BASE, mqttPort=1883), False)   # same port, int not string
    assert calls == []


def test_secrets_still_beat_the_dialog_after_a_save(plugin_mod, make_plugin, monkeypatch):
    monkeypatch.setattr(plugin_mod, "MQTT_BROKER", "192.168.1.30")
    monkeypatch.setattr(plugin_mod, "MQTT_USERNAME", "secret-user")
    monkeypatch.setattr(plugin_mod, "MQTT_PASSWORD", "secret-pass")
    p = make_plugin(prefs=_BASE)
    assert p.mqtt_host == "192.168.1.30"
    monkeypatch.setattr(p, "_mqtt_disconnect", lambda: None)
    monkeypatch.setattr(p, "_mqtt_connect", lambda: None)
    p.closedPrefsConfigUi(dict(_BASE, mqttHost="192.168.1.99", mqttPort="8883"), False)
    assert p.mqtt_host == "192.168.1.30"
    assert p.mqtt_username == "secret-user"
    assert p.mqtt_port == 8883


# ── The setting that never did anything ──────────────────────────────────────

def test_force_discovery_setting_is_gone():
    """It was never read, and could not work: the plugin only sees devices
    that already publish discovery. Removed from the dialog in 0.8.0."""
    ids = {f.get("id") for f in ET.parse(SERVER / "PluginConfig.xml").getroot().iter("Field")}
    assert "forceHADiscoveryOnPair" not in ids


def test_every_plugin_config_field_is_read():
    """A field in the Configure dialog that plugin.py never mentions is a
    setting that does nothing, which is how the one above survived."""
    tree = ast.parse((SERVER / "plugin.py").read_text(encoding="utf-8"))
    literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    for f in ET.parse(SERVER / "PluginConfig.xml").getroot().iter("Field"):
        if f.get("type") in ("label", "separator"):
            continue
        assert f.get("id") in literals, f"PluginConfig field {f.get('id')!r} is never read"
