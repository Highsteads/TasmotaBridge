#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    plugin.py
# Description: Indigo bridge for Tasmota MQTT devices (Sonoff, Athom, ESP-based).
#              Auto-discovery via tasmota/discovery/<MAC>/{config,sensors}.
# Author:      CliveS & Claude Opus 4.7
# Date:        19-05-2026
# Version:     0.1.0

try:
    import indigo
except ImportError:
    pass

import json
import os
import sys
import time
import threading
from datetime import datetime

sys.path.insert(0, os.getcwd())
try:
    from plugin_utils import log_startup_banner
except ImportError:
    log_startup_banner = None

sys.path.insert(0, "/Library/Application Support/Perceptive Automation")
try:
    from IndigoSecrets import MQTT_BROKER
except ImportError:
    MQTT_BROKER = ""
try:
    from IndigoSecrets import MQTT_PORT
except ImportError:
    MQTT_PORT = 1883
try:
    from IndigoSecrets import MQTT_USERNAME
except ImportError:
    MQTT_USERNAME = ""
try:
    from IndigoSecrets import MQTT_PASSWORD
except ImportError:
    MQTT_PASSWORD = ""

import paho.mqtt.client as mqtt


# ============================================================
# Constants
# ============================================================

PLUGIN_ID       = "com.clives.indigoplugin.tasmotabridge"
PLUGIN_VERSION  = "0.1.0"

# Tasmota discovery topic root - the plugin's anchor.
DISCOVERY_ROOT  = "tasmota/discovery"

# Telemetry / command prefixes (defaults; per-device may override via discovery.ft)
PREFIX_CMND     = "cmnd"
PREFIX_STAT     = "stat"
PREFIX_TELE     = "tele"

# Light subtypes (lt_st in discovery config)
LIGHT_NONE      = 0
LIGHT_DIMMER    = 1
LIGHT_CT        = 2
LIGHT_RGB       = 3
LIGHT_RGBW      = 4
LIGHT_RGBCW     = 5

# Offline-after-N-seconds-without-LWT (LWT is retained but we also watch telemetry)
OFFLINE_TIMEOUT_SEC = 600


# ============================================================
# Helpers
# ============================================================

def log(message, level="INFO"):
    indigo.server.log(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", level=level)


def normalise_mac(raw):
    """Convert any MAC representation to 12-char uppercase with no separators."""
    if not raw:
        return ""
    return "".join(c for c in raw.upper() if c in "0123456789ABCDEF")[:12]


def is_valid_state_id(key):
    """Indigo state IDs: ASCII alphanumeric only, must start with a letter."""
    if not key or not key[0].isascii() or not key[0].isalpha():
        return False
    return all(c.isascii() and c.isalnum() for c in key)


def snake_to_camel(snake):
    """Convert tasmota_field_name -> tasmotaFieldName for Indigo state IDs."""
    parts = snake.replace("-", "_").split("_")
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])


# ============================================================
# Plugin
# ============================================================

class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super().__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        self.debug = pluginPrefs.get("logLevel", "INFO") == "DEBUG"
        self.log_raw = bool(pluginPrefs.get("logRawPayloads", False))

        # Per-MAC discovery cache: {mac: {"config": {...}, "sensors": {...}}}
        self.discovery_cache = {}

        # Active Indigo devices keyed by MAC for fast routing
        self.devices_by_mac = {}    # {mac: indigo.Device}

        # Last-seen timestamps for availability tracking
        self.last_seen = {}         # {mac: epoch_ts}

        # Event trigger registry (for custom Events.xml events)
        self.event_triggers = {}    # {trigger.id: trigger}

        # MQTT client (configured in startup)
        self.mqtt_client = None
        self.mqtt_connected = False

        # Resolve broker config: IndigoSecrets > pluginPrefs
        self.mqtt_host     = MQTT_BROKER     or pluginPrefs.get("mqttHost", "")
        self.mqtt_port     = int(pluginPrefs.get("mqttPort", "0") or 0) or MQTT_PORT or 1883
        self.mqtt_username = MQTT_USERNAME   or pluginPrefs.get("mqttUsername", "")
        self.mqtt_password = MQTT_PASSWORD   or pluginPrefs.get("mqttPassword", "")
        self.mqtt_tls      = bool(pluginPrefs.get("mqttTLS", False))

        self.auto_create   = bool(pluginPrefs.get("autoCreateDevices", True))

        if log_startup_banner:
            log_startup_banner(pluginId, pluginDisplayName, pluginVersion, extras=[
                ("MQTT Broker:", f"{self.mqtt_host}:{self.mqtt_port}"),
                ("MQTT User:", self.mqtt_username or "(anonymous)"),
                ("Auto-create:", "yes" if self.auto_create else "no"),
            ])
        else:
            indigo.server.log(f"{pluginDisplayName} v{pluginVersion} starting")

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------

    def startup(self):
        if not self.mqtt_host:
            self.logger.error(
                "No MQTT broker configured. Set MQTT_BROKER in IndigoSecrets.py "
                "or fill Broker Host in Plugins -> Tasmota Bridge -> Configure..."
            )
            return
        self._mqtt_connect()

    def shutdown(self):
        self._mqtt_disconnect()

    # --------------------------------------------------------
    # MQTT
    # --------------------------------------------------------

    def _mqtt_connect(self):
        client_id = f"indigo_tasmotabridge_{int(time.time())}"
        try:
            self.mqtt_client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=client_id,
            )
        except AttributeError:
            # paho-mqtt < 2.0 fallback
            self.mqtt_client = mqtt.Client(client_id=client_id)

        if self.mqtt_username:
            self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
        if self.mqtt_tls:
            self.mqtt_client.tls_set()

        self.mqtt_client.on_connect    = self._on_connect
        self.mqtt_client.on_disconnect = self._on_disconnect
        self.mqtt_client.on_message    = self._on_message

        self.logger.info(f"MQTT connecting to {self.mqtt_host}:{self.mqtt_port}")
        self.mqtt_client.connect_async(self.mqtt_host, self.mqtt_port, keepalive=60)
        self.mqtt_client.loop_start()

    def _mqtt_disconnect(self):
        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception as exc:
                self.logger.debug(f"MQTT disconnect error: {exc}")
            self.mqtt_client = None
        self.mqtt_connected = False

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        rc = reason_code if isinstance(reason_code, int) else getattr(reason_code, "value", 0)
        if rc != 0:
            self.logger.error(f"MQTT connect failed (reason_code={reason_code})")
            return
        self.mqtt_connected = True
        self.logger.info(f"MQTT connected to {self.mqtt_host}:{self.mqtt_port}")

        # Subscribe to the Tasmota universe.
        subs = [
            (f"{DISCOVERY_ROOT}/#", 0),     # discovery configs + sensors
            (f"{PREFIX_TELE}/#", 0),        # STATE / SENSOR / LWT
            (f"{PREFIX_STAT}/#", 0),        # RESULT / POWER (command responses)
        ]
        for topic, qos in subs:
            client.subscribe(topic, qos)
            self.logger.debug(f"MQTT subscribed: {topic}")

    def _on_disconnect(self, client, userdata, *args, **kwargs):
        self.mqtt_connected = False
        self.logger.warning("MQTT disconnected (will auto-reconnect)")

    def _on_message(self, client, userdata, msg):
        try:
            self._process_message(msg.topic, msg.payload)
        except Exception:
            self.logger.exception(f"MQTT message handling failed for {msg.topic}")

    # --------------------------------------------------------
    # Topic dispatch
    # --------------------------------------------------------

    def _process_message(self, topic, payload_bytes):
        try:
            payload = payload_bytes.decode("utf-8")
        except UnicodeDecodeError:
            self.logger.debug(f"Non-UTF8 payload on {topic}, skipping")
            return

        if self.log_raw:
            self.logger.debug(f"MQTT << {topic}  {payload[:300]}")

        parts = topic.split("/")

        # Tasmota native discovery: tasmota/discovery/<MAC>/{config|sensors}
        if len(parts) == 4 and parts[0] == "tasmota" and parts[1] == "discovery":
            mac = normalise_mac(parts[2])
            kind = parts[3]
            self._handle_discovery(mac, kind, payload)
            return

        # Telemetry: tele/<topic>/{STATE|SENSOR|LWT}
        if len(parts) >= 3 and parts[0] == PREFIX_TELE:
            self._handle_tele(parts[1], parts[2], payload)
            return

        # Command result: stat/<topic>/{RESULT|POWER|POWERn|STATUSn|...}
        if len(parts) >= 3 and parts[0] == PREFIX_STAT:
            self._handle_stat(parts[1], parts[2], payload)
            return

    # --------------------------------------------------------
    # Discovery handling
    # --------------------------------------------------------

    def _handle_discovery(self, mac, kind, payload):
        if not mac:
            return
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            self.logger.warning(f"Discovery {kind} for {mac}: non-JSON payload")
            return

        entry = self.discovery_cache.setdefault(mac, {})
        first_config = "config" not in entry and kind == "config"
        entry[kind] = data

        if first_config:
            self.logger.info(
                f"Discovered Tasmota device {mac}: "
                f"{data.get('dn', '?')} ({data.get('md', '?')} fw {data.get('sw', '?')})"
            )
            if mac not in self.devices_by_mac:
                self._fire_event("newDeviceDiscovered", mac)

        # Only auto-create once we have BOTH config and sensors - they arrive
        # back-to-back on broker connect but order isn't guaranteed, and the
        # sensors payload determines whether a relay becomes a tasmotaEnergyPlug.
        if self.auto_create and "config" in entry and "sensors" in entry:
            self._auto_create_or_update_device(mac)

    def _detect_device_type(self, config, sensors):
        """Map discovery payload to Indigo deviceTypeId. Returns (type_id, channel)."""
        sht = config.get("sht", []) or []
        if any(sht):
            return ("tasmotaShutter", 1)

        lt_st = config.get("lt_st", 0)
        if lt_st >= LIGHT_DIMMER:
            return ("tasmotaLight", 1)

        rl = config.get("rl", []) or []
        relays_present = [i + 1 for i, v in enumerate(rl) if v]
        has_energy = bool(sensors and "sn" in sensors and "ENERGY" in sensors["sn"])

        if relays_present:
            if has_energy:
                return ("tasmotaEnergyPlug", relays_present[0])
            return ("tasmotaRelay", relays_present[0])

        # No relays, no light - must be sensor-only
        return ("tasmotaSensor", 0)

    def _auto_create_or_update_device(self, mac):
        entry = self.discovery_cache.get(mac, {})
        config = entry.get("config")
        sensors = entry.get("sensors", {})
        if not config:
            return

        existing = self._find_device_by_address(mac)
        if existing:
            self.devices_by_mac[mac] = existing
            self._refresh_device_props(existing, config, sensors)
            return

        type_id, channel = self._detect_device_type(config, sensors)
        name = config.get("dn") or config.get("hn") or f"Tasmota {mac[-6:]}"

        props = {
            "address":   mac,
            "topic":     config.get("t", ""),
            "channel":   str(channel),
            "ip":        config.get("ip", ""),
            "model":     config.get("md", ""),
            "firmware":  config.get("sw", ""),
        }
        if type_id == "tasmotaEnergyPlug":
            props["SupportsEnergyMeter"]         = True
            props["SupportsEnergyMeterCurPower"] = True
        if type_id == "tasmotaLight":
            props["lightSubtype"] = str(config.get("lt_st", 0))
            props["SupportsColor"]            = config.get("lt_st", 0) >= LIGHT_RGB
            props["SupportsRGB"]              = config.get("lt_st", 0) >= LIGHT_RGB
            props["SupportsWhite"]            = config.get("lt_st", 0) in (LIGHT_CT, LIGHT_RGBW, LIGHT_RGBCW)
            props["SupportsWhiteTemperature"] = config.get("lt_st", 0) in (LIGHT_CT, LIGHT_RGBCW)
        if type_id == "tasmotaSensor" and sensors.get("sn"):
            props["sensorTypes"] = ", ".join(k for k in sensors["sn"].keys() if k != "Time")

        try:
            dev = indigo.device.create(
                protocol=indigo.kProtocol.Plugin,
                address=mac,
                name=name,
                deviceTypeId=type_id,
                props=props,
                folder=0,
            )
            self.devices_by_mac[mac] = dev
            self.logger.info(f"Created Indigo device: {dev.name} (type={type_id}, address={mac})")
        except Exception:
            self.logger.exception(f"Failed to create Indigo device for MAC {mac}")

    def _refresh_device_props(self, dev, config, sensors):
        """Update read-only props (model/firmware/IP) from latest discovery."""
        props = dict(dev.pluginProps)
        changed = False
        for src_key, prop_key in (("md", "model"), ("sw", "firmware"), ("ip", "ip")):
            val = config.get(src_key, "")
            if val and props.get(prop_key, "") != val:
                props[prop_key] = val
                changed = True
        if changed:
            dev.replacePluginPropsOnServer(props)

    def _find_device_by_address(self, mac):
        for dev in indigo.devices.iter(f"self"):
            if dev.address == mac:
                return dev
        return None

    # --------------------------------------------------------
    # Telemetry handling
    # --------------------------------------------------------

    def _handle_tele(self, topic_name, kind, payload):
        dev = self._find_device_by_topic(topic_name)
        if not dev:
            return

        kind = kind.upper()
        if kind == "LWT":
            self._handle_lwt(dev, payload)
        elif kind == "STATE":
            self._handle_state(dev, payload)
        elif kind == "SENSOR":
            self._handle_sensor(dev, payload)

    def _handle_stat(self, topic_name, kind, payload):
        dev = self._find_device_by_topic(topic_name)
        if not dev:
            return

        if kind.upper().startswith("POWER"):
            # Plain text "ON"/"OFF" - relay state change
            on = payload.strip().upper() == "ON"
            self._update_relay_state(dev, on)
        elif kind.upper() == "RESULT":
            # JSON with command result
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                return
            self._handle_result(dev, data)

    def _find_device_by_topic(self, topic_name):
        """Look up an Indigo device by its Tasmota base topic."""
        for dev in self.devices_by_mac.values():
            if dev.pluginProps.get("topic") == topic_name:
                return dev
        # Slow path - rescan all plugin devices
        for dev in indigo.devices.iter("self"):
            if dev.pluginProps.get("topic") == topic_name:
                mac = dev.pluginProps.get("address", "")
                if mac:
                    self.devices_by_mac[mac] = dev
                return dev
        return None

    def _handle_lwt(self, dev, payload):
        availability = payload.strip()
        dev.updateStateOnServer("availability", availability)
        mac = dev.pluginProps.get("address", "")
        if mac:
            if availability == "Online":
                self.last_seen[mac] = time.time()
                self._fire_event("deviceOnline", mac)
            else:
                self._fire_event("deviceOffline", mac)

    def _handle_state(self, dev, payload):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return

        mac = dev.pluginProps.get("address", "")
        if mac:
            self.last_seen[mac] = time.time()

        # POWER (or POWER1..POWER8) - relay state
        channel = dev.pluginProps.get("channel", "1")
        power_key = "POWER" if channel == "1" else f"POWER{channel}"
        if power_key in data:
            self._update_relay_state(dev, data[power_key] == "ON")
        elif "POWER" in data and channel == "1":
            self._update_relay_state(dev, data["POWER"] == "ON")

        # Wi-Fi diagnostics
        wifi = data.get("Wifi", {})
        if "RSSI" in wifi:
            dev.updateStateOnServer("rssi", int(wifi["RSSI"]))
        if "Signal" in wifi:
            dev.updateStateOnServer("signal", int(wifi["Signal"]))
        if "Uptime" in data:
            dev.updateStateOnServer("uptime", data["Uptime"])
        dev.updateStateOnServer("lastSeen", data.get("Time", datetime.now().isoformat()))

    def _handle_sensor(self, dev, payload):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return

        mac = dev.pluginProps.get("address", "")
        if mac:
            self.last_seen[mac] = time.time()

        energy = data.get("ENERGY")
        if energy and dev.deviceTypeId == "tasmotaEnergyPlug":
            updates = []
            if "Power" in energy:         updates.append({"key": "curEnergyLevel",   "value": float(energy["Power"]),         "uiValue": f"{energy['Power']} W"})
            if "Total" in energy:         updates.append({"key": "accumEnergyTotal", "value": float(energy["Total"]),         "uiValue": f"{energy['Total']:.3f} kWh"})
            if "Voltage" in energy:       updates.append({"key": "voltage",          "value": float(energy["Voltage"])})
            if "Current" in energy:       updates.append({"key": "current",          "value": float(energy["Current"])})
            if "ApparentPower" in energy: updates.append({"key": "apparentPower",    "value": float(energy["ApparentPower"])})
            if "ReactivePower" in energy: updates.append({"key": "reactivePower",    "value": float(energy["ReactivePower"])})
            if "Factor" in energy:        updates.append({"key": "powerFactor",      "value": float(energy["Factor"])})
            if "Today" in energy:         updates.append({"key": "energyToday",      "value": float(energy["Today"])})
            if "Yesterday" in energy:     updates.append({"key": "energyYesterday",  "value": float(energy["Yesterday"])})
            if updates:
                dev.updateStatesOnServer(updates)

        # TODO: handle DS18B20-N, BME280, AM2301, etc. via dynamic state declaration

    def _handle_result(self, dev, data):
        # Command results - useful for confirming dimmer / colour changes
        # TODO: parse Dimmer, Color, CT, ShutterPosition responses
        pass

    def _update_relay_state(self, dev, on_state):
        if dev.deviceTypeId in ("tasmotaRelay", "tasmotaEnergyPlug"):
            dev.updateStateOnServer("onOffState", on_state)
        elif dev.deviceTypeId == "tasmotaLight":
            dev.updateStateOnServer("onOffState", on_state)

    # --------------------------------------------------------
    # Outbound commands
    # --------------------------------------------------------

    def _publish_command(self, dev, command, payload=""):
        if not self.mqtt_connected or not self.mqtt_client:
            self.logger.warning(f"MQTT not connected - dropping cmd {command} for {dev.name}")
            return
        topic = dev.pluginProps.get("topic", "")
        if not topic:
            self.logger.warning(f"No MQTT topic on {dev.name} - cannot send command")
            return
        full = f"{PREFIX_CMND}/{topic}/{command}"
        self.mqtt_client.publish(full, payload)
        self.logger.debug(f"MQTT >> {full}  {payload}")

    # --------------------------------------------------------
    # Device lifecycle
    # --------------------------------------------------------

    def deviceStartComm(self, dev):
        mac = dev.pluginProps.get("address", "")
        if mac:
            self.devices_by_mac[mac] = dev
        # Force state-list refresh in case we added states retroactively
        dev.stateListOrDisplayStateIdChanged()
        self.logger.debug(f"deviceStartComm: {dev.name} (MAC {mac})")

    def deviceStopComm(self, dev):
        mac = dev.pluginProps.get("address", "")
        if mac and mac in self.devices_by_mac:
            del self.devices_by_mac[mac]
        self.logger.debug(f"deviceStopComm: {dev.name}")

    # --------------------------------------------------------
    # Indigo native control callbacks (relay/dimmer)
    # --------------------------------------------------------

    def actionControlDevice(self, action, dev):
        """Relay on/off/toggle handler - Indigo calls this for native relay devices."""
        channel = dev.pluginProps.get("channel", "1")
        cmd = "POWER" if channel == "1" else f"POWER{channel}"
        if action.deviceAction == indigo.kDeviceAction.TurnOn:
            self._publish_command(dev, cmd, "ON")
        elif action.deviceAction == indigo.kDeviceAction.TurnOff:
            self._publish_command(dev, cmd, "OFF")
        elif action.deviceAction == indigo.kDeviceAction.Toggle:
            self._publish_command(dev, cmd, "TOGGLE")
        else:
            self.logger.debug(f"Unhandled device action {action.deviceAction} on {dev.name}")

    def actionControlDimmer(self, action, dev):
        """Dimmer/light handler - Indigo calls this for native dimmer devices."""
        channel = dev.pluginProps.get("channel", "1")
        cmd_power = "POWER" if channel == "1" else f"POWER{channel}"

        if action.deviceAction == indigo.kDeviceAction.TurnOn:
            self._publish_command(dev, cmd_power, "ON")
        elif action.deviceAction == indigo.kDeviceAction.TurnOff:
            self._publish_command(dev, cmd_power, "OFF")
        elif action.deviceAction == indigo.kDeviceAction.Toggle:
            self._publish_command(dev, cmd_power, "TOGGLE")
        elif action.deviceAction == indigo.kDeviceAction.SetBrightness:
            level = int(action.actionValue)
            self._publish_command(dev, "Dimmer", str(level))
        elif action.deviceAction in (
            indigo.kDeviceAction.BrightenBy,
            indigo.kDeviceAction.DimBy,
        ):
            current = dev.brightness or 0
            delta = int(action.actionValue)
            if action.deviceAction == indigo.kDeviceAction.DimBy:
                delta = -delta
            new_level = max(0, min(100, current + delta))
            self._publish_command(dev, "Dimmer", str(new_level))
        else:
            self.logger.debug(f"Unhandled dimmer action {action.deviceAction} on {dev.name}")

    # --------------------------------------------------------
    # Custom action callbacks (Actions.xml)
    # --------------------------------------------------------

    def actionSendRawCommand(self, action, dev):
        raw = action.props.get("command", "").strip()
        if not raw:
            return
        # Split first word as the Tasmota command, rest as payload
        parts = raw.split(" ", 1)
        cmd = parts[0]
        payload = parts[1] if len(parts) > 1 else ""
        self._publish_command(dev, cmd, payload)

    def actionSetHSBColor(self, action, dev):
        h = int(action.props.get("hue", 0))
        s = int(action.props.get("saturation", 100))
        b = int(action.props.get("brightness", 100))
        self._publish_command(dev, "HSBColor", f"{h},{s},{b}")

    def actionSetColorTemp(self, action, dev):
        m = int(action.props.get("mired", 300))
        self._publish_command(dev, "CT", str(m))

    def actionShutterOpen(self, action, dev):
        idx = dev.pluginProps.get("shutterIndex", "1")
        self._publish_command(dev, f"ShutterOpen{idx}")

    def actionShutterClose(self, action, dev):
        idx = dev.pluginProps.get("shutterIndex", "1")
        self._publish_command(dev, f"ShutterClose{idx}")

    def actionShutterStop(self, action, dev):
        idx = dev.pluginProps.get("shutterIndex", "1")
        self._publish_command(dev, f"ShutterStop{idx}")

    def actionRequestStatus(self, action, dev):
        self._publish_command(dev, "Status", "0")

    # --------------------------------------------------------
    # Trigger lifecycle (for custom Events.xml events)
    # --------------------------------------------------------

    def triggerStartProcessing(self, trigger):
        self.event_triggers[trigger.id] = trigger

    def triggerStopProcessing(self, trigger):
        self.event_triggers.pop(trigger.id, None)

    def _fire_event(self, event_type, mac):
        for trigger in self.event_triggers.values():
            if trigger.pluginTypeId != event_type:
                continue
            target = trigger.pluginProps.get("targetAddress", "").strip()
            if target and normalise_mac(target) != mac:
                continue
            indigo.trigger.execute(trigger)

    # --------------------------------------------------------
    # runConcurrentThread - LWT timeout watcher
    # --------------------------------------------------------

    def runConcurrentThread(self):
        try:
            while True:
                now = time.time()
                for mac, ts in list(self.last_seen.items()):
                    if now - ts > OFFLINE_TIMEOUT_SEC:
                        dev = self.devices_by_mac.get(mac)
                        if dev and dev.states.get("availability") != "Offline":
                            dev.updateStateOnServer("availability", "Offline")
                            self._fire_event("deviceOffline", mac)
                self.sleep(30)
        except self.StopThread:
            pass

    # --------------------------------------------------------
    # Plugin preferences
    # --------------------------------------------------------

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if userCancelled:
            return
        # Re-read prefs that affect runtime behaviour
        self.log_raw   = bool(valuesDict.get("logRawPayloads", False))
        self.auto_create = bool(valuesDict.get("autoCreateDevices", True))
        new_host = valuesDict.get("mqttHost", "") or MQTT_BROKER
        if new_host != self.mqtt_host:
            self.logger.info("Broker config changed - reconnecting MQTT")
            self._mqtt_disconnect()
            self.mqtt_host     = new_host
            self.mqtt_port     = int(valuesDict.get("mqttPort", "1883") or 1883)
            self.mqtt_username = valuesDict.get("mqttUsername", "") or MQTT_USERNAME
            self.mqtt_password = valuesDict.get("mqttPassword", "") or MQTT_PASSWORD
            self.mqtt_tls      = bool(valuesDict.get("mqttTLS", False))
            self._mqtt_connect()

    # --------------------------------------------------------
    # Menu handlers
    # --------------------------------------------------------

    def discoverDevices(self, valuesDict=None, typeId=None):
        """Re-request retained discovery messages by re-subscribing."""
        if not self.mqtt_connected:
            self.logger.warning("Not connected to MQTT - cannot trigger discovery refresh")
            return
        # Re-subscribe pulls retained messages again
        self.mqtt_client.unsubscribe(f"{DISCOVERY_ROOT}/#")
        self.mqtt_client.subscribe(f"{DISCOVERY_ROOT}/#", 0)
        self.logger.info("Re-subscribed to discovery topic - retained messages will replay")

    def listSeenDevices(self, valuesDict=None, typeId=None):
        if not self.discovery_cache:
            indigo.server.log("No Tasmota devices discovered yet")
            return
        for mac, entry in sorted(self.discovery_cache.items()):
            cfg = entry.get("config", {})
            sn  = entry.get("sensors", {}).get("sn", {})
            sensors_str = ", ".join(k for k in sn.keys() if k != "Time") or "none"
            indigo.server.log(
                f"  {mac}  {cfg.get('dn', '?'):<35}  "
                f"{cfg.get('md', '?'):<22}  fw {cfg.get('sw', '?'):<10}  "
                f"sensors={sensors_str}"
            )

    def dumpDiscoveryCache(self, valuesDict=None, typeId=None):
        indigo.server.log("=== Tasmota Discovery Cache ===")
        indigo.server.log(json.dumps(self.discovery_cache, indent=2, default=str))

    def showPluginInfo(self, valuesDict=None, typeId=None):
        if log_startup_banner:
            log_startup_banner(self.pluginId, self.pluginDisplayName, self.pluginVersion, extras=[
                ("MQTT Broker:", f"{self.mqtt_host}:{self.mqtt_port}"),
                ("MQTT Connected:", "yes" if self.mqtt_connected else "no"),
                ("Devices discovered:", str(len(self.discovery_cache))),
                ("Devices in Indigo:", str(len(self.devices_by_mac))),
            ])
        else:
            indigo.server.log(f"{self.pluginDisplayName} v{self.pluginVersion}")
