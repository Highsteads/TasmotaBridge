#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    plugin.py
# Description: Indigo bridge for Tasmota MQTT devices (Sonoff, Athom, ESP-based).
#              Auto-discovery via tasmota/discovery/<MAC>/{config,sensors}.
# Author:      CliveS & Claude Opus 5.5
# Date:        27-09-2026
# Version:     0.8.0
#
# v0.8.0 (27-09-2026): faults found writing the guide - both button payload shapes,
# every Log Level applied at start and on save, colorMode filled, report states
# declared on every type, ESP32 firmware by chip (and .bin, not the 404 .bin.gz),
# the Status reply read, any broker change reconnects, dead setting removed.
#
# v0.7.7 (08-08-2026): REQUIRED Info.plist KEY. `CFBundleURLTypes` was MISSING,
# so the plugin had no support URL for its "About" menu item — one of the SIX
# keys the official Developer's Guide lists as required. Found by an estate
# check. No plugin logic changed.
#
# v0.7.3 (23-05-2026): Millisecond timestamp [HH:MM:SS.mmm] prefix on every
# log line via plugin_utils.install_timestamp_filter() — matches Device
# Activity Monitor convention. Module-level log() helper bumped to ms.
# New "Toggle Timestamps in Log" menu item.

try:
    import indigo
except ImportError:
    pass

import json
import logging
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.getcwd())
try:
    from plugin_utils import log_startup_banner
except ImportError:
    log_startup_banner = None
try:
    from plugin_utils import install_timestamp_filter
except ImportError:
    install_timestamp_filter = None

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
PLUGIN_VERSION  = "0.8.0"


def _as_int(value, default):
    """Coerce to int, returning default on blank/non-numeric (config + action props)."""
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return default


def _as_bool(value, default=False):
    """A checkbox pref is a real bool once saved, but a value can also arrive
    as the strings "true"/"false" - and bool("false") is True."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def resolve_broker(prefs):
    """The broker settings, in the one order used at start AND after a
    Configure save: IndigoSecrets.py first for host, user name and password,
    the Configure box first for the port, and TLS from the Configure box.

    Before 0.8.0 the save path had its own copy with the order reversed for the
    host, so after a save the dialog's address beat IndigoSecrets.py until the
    next restart."""
    prefs = prefs or {}
    return {
        "host":     MQTT_BROKER   or prefs.get("mqttHost", "") or "",
        "port":     _as_int(prefs.get("mqttPort"), 0) or _as_int(MQTT_PORT, 0) or 1883,
        "username": MQTT_USERNAME or prefs.get("mqttUsername", "") or "",
        "password": MQTT_PASSWORD or prefs.get("mqttPassword", "") or "",
        "tls":      _as_bool(prefs.get("mqttTLS"), False),
    }


def log_level_for(value):
    """Map the Log Level menu value to a logging level; anything unknown is INFO."""
    return _LOG_LEVELS.get(str(value or "").strip().upper(), logging.INFO)


def parse_button_events(data):
    """Return [(button_number, ACTION), ...] from a stat/<topic>/RESULT payload.

    Tasmota sends a button press in two shapes. With SetOption73 1 (buttons
    detached from the relays) it is {"Button1":{"Action":"SINGLE"}}, which is
    what the Tasmota docs show. A flat {"Button1":"SINGLE"} is also accepted,
    as a rule can publish one. Anything else is ignored."""
    events = []
    if not isinstance(data, dict):
        return events
    for key, val in data.items():
        if not (isinstance(key, str) and key.startswith("Button") and key[6:].isdigit()):
            continue
        if isinstance(val, dict):
            val = val.get("Action")
        if not isinstance(val, str) or not val.strip():
            continue
        events.append((int(key[6:]), val.strip().upper()))
    return events


def light_colour_mode(light_subtype, data):
    """The mode a Tasmota light is in, from its subtype (lt_st) and a report.

    Tasmota has no mode field. A light with only one kind of output is always
    in that mode. A light with both colour and white (4 = RGBW, 5 = RGBCW)
    runs one or the other, and its White value says which: 0 means colour.
    Returns None when the report cannot tell (no White value)."""
    subtype = _as_int(light_subtype, 0)
    if subtype == 1:
        return "dimmer"
    if subtype == 2:
        return "ct"
    if subtype == 3:
        return "rgb"
    if subtype in (4, 5):
        white = data.get("White") if isinstance(data, dict) else None
        if white is None:
            return None
        if _as_int(white, 0) == 0:
            return "rgb"
        return "white" if subtype == 4 else "ct"
    return None


# Official Tasmota OTA files by chip, from ota.tasmota.com. The ESP8266 build
# is served gzipped; the ESP32 builds are not (tasmota32.bin.gz is a 404).
_OTA_BASE_8266 = "http://ota.tasmota.com/tasmota/release"
_OTA_BASE_32   = "http://ota.tasmota.com/tasmota32/release"
OTA_URLS = {
    "ESP8266":     f"{_OTA_BASE_8266}/tasmota.bin.gz",
    "ESP32":       f"{_OTA_BASE_32}/tasmota32.bin",
    "ESP32-SOLO1": f"{_OTA_BASE_32}/tasmota32solo1.bin",
    "ESP32-S2":    f"{_OTA_BASE_32}/tasmota32s2.bin",
    "ESP32-S3":    f"{_OTA_BASE_32}/tasmota32s3.bin",
    "ESP32-C2":    f"{_OTA_BASE_32}/tasmota32c2.bin",
    "ESP32-C3":    f"{_OTA_BASE_32}/tasmota32c3.bin",
    "ESP32-C6":    f"{_OTA_BASE_32}/tasmota32c6.bin",
}


def chip_family(hardware):
    """Map Tasmota's Status 2 "Hardware" string to a key of OTA_URLS, or None.

    The strings are the ones Tasmota's GetDeviceHardware() returns, sometimes
    with a revision after them ("ESP32-C3 v0.4"). A chip this does not
    recognise returns None, and the plugin then refuses to upgrade rather than
    send the wrong firmware."""
    hw = (hardware or "").strip().upper()
    if not hw:
        return None
    if "ESP8266" in hw or "ESP8285" in hw:
        return "ESP8266"
    if hw.startswith(("ESP8685", "ESP8686")) or hw.startswith("ESP32-C3"):
        return "ESP32-C3"
    if hw.startswith(("ESP8684", "ESP32-C2")):
        return "ESP32-C2"
    for prefix in ("ESP32-S3", "ESP32-S2", "ESP32-C6"):
        if hw.startswith(prefix):
            return prefix
    # The original ESP32: single-core parts need the solo1 build.
    if hw.startswith(("ESP32-S0WD", "ESP32-U4WDH-S")):
        return "ESP32-SOLO1"
    if hw.split()[0] == "ESP32" or hw.startswith(("ESP32-D0WD", "ESP32-D2WD", "ESP32-PICO", "ESP32-U4WDH-D")):
        return "ESP32"
    return None

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

# Folder name for auto-created devices
DEVICE_FOLDER_NAME = "Tasmota"

# Device types whose output is a relay: switched on and off, one Indigo device
# per channel on a multi-relay board. ONE owner for the rule. It used to be
# written out as a literal tuple in three places -- creating the per-channel
# devices, writing onOffState, and handling TurnOn/TurnOff -- so a relay type
# added to one and missed in another would create devices that could not be
# switched, or switch devices that never report their state (21-09-2026).
RELAY_TYPES = frozenset({"tasmotaRelay", "tasmotaEnergyPlug"})


# ============================================================
# Helpers
# ============================================================

_LOG_LEVELS = {
    "DEBUG":    logging.DEBUG,
    "INFO":     logging.INFO,
    "WARNING":  logging.WARNING,
    "ERROR":    logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _lvl(level):
    """Map a level NAME to a Python logging int.

    indigo.server.log(level=...) wants an int. A STRING is silently ignored
    and the line logs as plain Info, which hides every WARNING and ERROR.
    """
    if isinstance(level, int):
        return level
    return _LOG_LEVELS.get(str(level).upper(), logging.INFO)


def log(message, level="INFO"):
    indigo.server.log(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {message}", level=_lvl(level))


def normalise_mac(raw):
    """Convert any MAC representation to 12-char uppercase with no separators."""
    if not raw:
        return ""
    return "".join(c for c in raw.upper() if c in "0123456789ABCDEF")[:12]


def is_valid_state_id(key):
    """Indigo state IDs: ASCII alphanumeric only, must start with a letter.
    See feedback_indigo_state_id_naming_rules - underscores not allowed."""
    if not key or not key[0].isascii() or not key[0].isalpha():
        return False
    return all(c.isascii() and c.isalnum() for c in key)


def snake_to_camel(snake):
    """Convert tasmota_field_name or Tasmota-name -> tasmotaFieldName for
    Indigo state IDs. Indigo rejects underscores and hyphens in state IDs."""
    parts = snake.replace("-", "_").split("_")
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])


def sensor_state_id(sensor_name, field_name):
    """Build a state ID for a sensor field. e.g. ('DS18B20-1','Temperature')
    -> 'ds18b201Temperature'. Validates the result is a legal Indigo state ID."""
    base = snake_to_camel(sensor_name)
    suffix = field_name[0].upper() + field_name[1:] if field_name else ""
    candidate = base + suffix
    return candidate if is_valid_state_id(candidate) else None


# ============================================================
# Plugin
# ============================================================

class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super().__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        # Log Level is applied in startup() and on every Configure save.
        self.log_raw = bool(pluginPrefs.get("logRawPayloads", False))
        self.timestamp_enabled = bool(pluginPrefs.get("timestampEnabled", True))

        if install_timestamp_filter:
            self._ts_filter = install_timestamp_filter(self, enabled=self.timestamp_enabled)
        else:
            self._ts_filter = None

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

        # Resolve broker config - one owner of the order, shared with the
        # Configure-save path (see resolve_broker).
        self._set_broker(resolve_broker(pluginPrefs))

        self.auto_create   = bool(pluginPrefs.get("autoCreateDevices", True))

        # GitHub release cache for firmware update checks - {"tag": "15.0.1", "ts": epoch}
        self.gh_release_cache = {"tag": None, "ts": 0}

        # One-shot firmware check after devices are discovered (set in startup())
        self.initial_firmware_check_done = False
        self.startup_time = 0.0

        # Synchronous fetch of latest Tasmota release for the banner. Short
        # timeout so unreachable GitHub doesn't delay plugin startup.
        latest_tasmota = self._fetch_tasmota_latest(timeout=5)
        if latest_tasmota:
            self.gh_release_cache = {"tag": latest_tasmota, "ts": time.time()}

        # Startup banner moved to showPluginInfo on demand (revised 25-May-2026 per Jay).

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------

    def startup(self):
        self._apply_log_level(self.pluginPrefs.get("logLevel", "INFO"))
        if not self.mqtt_host:
            self.logger.error(
                "No MQTT broker configured. Set MQTT_BROKER in IndigoSecrets.py "
                "or fill Broker Host in Plugins -> Tasmota Bridge -> Configure..."
            )
            return
        self.startup_time = time.time()
        self._mqtt_connect()

    def shutdown(self):
        self._mqtt_disconnect()

    def _apply_log_level(self, value):
        """Apply the Log Level pref to the EVENT LOG handler only, so the
        plugin's own log file keeps its debug lines whatever is chosen.
        Before 0.8.0 only Debug was honoured, and only after a restart."""
        handler = getattr(self, "indigo_log_handler", None)
        if handler is None:
            return
        try:
            handler.setLevel(log_level_for(value))
        except Exception as exc:
            self.logger.debug(f"Could not set the log level: {exc}")

    def _broker(self):
        return {
            "host":     self.mqtt_host,
            "port":     self.mqtt_port,
            "username": self.mqtt_username,
            "password": self.mqtt_password,
            "tls":      self.mqtt_tls,
        }

    def _set_broker(self, broker):
        self.mqtt_host     = broker["host"]
        self.mqtt_port     = broker["port"]
        self.mqtt_username = broker["username"]
        self.mqtt_password = broker["password"]
        self.mqtt_tls      = broker["tls"]

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
        """Map discovery payload to Indigo deviceTypeId. Returns (type_id, channel).

        Single-channel devices return channel=1 (or the first non-zero rl[]).
        Multi-channel devices return type for the FIRST channel; the caller is
        responsible for spawning sibling devices for channels 2..N.
        """
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
            # Only the first-channel device carries energy states. Sibling
            # channels created later are plain tasmotaRelay regardless of
            # whether the parent monitors energy.
            if has_energy:
                return ("tasmotaEnergyPlug", relays_present[0])
            return ("tasmotaRelay", relays_present[0])

        # No relays, no light - buttons-only or sensor-only
        btn = config.get("btn", []) or []
        if any(btn):
            return ("tasmotaButton", 1)

        return ("tasmotaSensor", 0)

    def _relay_channels(self, config):
        """Return list of channel numbers (1..N) that have an active relay."""
        rl = config.get("rl", []) or []
        return [i + 1 for i, v in enumerate(rl) if v]

    def _sibling_address(self, base_mac, channel):
        """Address scheme:
           - channel 0 (sensor-only) keeps the bare MAC
           - channel 1 (primary / single-relay) keeps the bare MAC
           - channels 2+ get MAC-N suffix to be unique per Indigo device
        """
        if channel <= 1:
            return base_mac
        return f"{base_mac}-{channel}"

    def _sibling_name(self, base_name, channel, total_channels):
        """Naming scheme for sibling devices."""
        if total_channels <= 1:
            return base_name
        return f"{base_name} - Ch {channel}"

    def _auto_create_or_update_device(self, mac):
        entry = self.discovery_cache.get(mac, {})
        config = entry.get("config")
        sensors = entry.get("sensors", {})
        if not config:
            return

        existing = self._find_device_by_address(mac)
        if existing:
            # IMPORTANT: do not touch folderId on existing devices. The folder
            # is the user's choice once they organise devices into rooms.
            # _refresh_device_props only updates model/firmware/ip/subModel.
            self.devices_by_mac[mac] = existing
            self._refresh_device_props(existing, config, sensors)
            return

        type_id, channel = self._detect_device_type(config, sensors)
        base_name = config.get("dn") or config.get("hn") or f"Tasmota {mac[-6:]}"
        channels  = self._relay_channels(config) if type_id in RELAY_TYPES else [channel]
        total     = len(channels)

        for n in channels:
            # Channel 1 keeps the primary type (may be tasmotaEnergyPlug);
            # additional channels are always plain tasmotaRelay since
            # ENERGY metering is per-device not per-channel in Tasmota.
            ch_type    = type_id if n == channels[0] else "tasmotaRelay"
            ch_address = self._sibling_address(mac, n)
            ch_name    = self._sibling_name(base_name, n, total)
            self._create_one_device(
                mac=mac, address=ch_address, name=ch_name, channel=n,
                type_id=ch_type, config=config, sensors=sensors,
            )

    def _create_one_device(self, mac, address, name, channel, type_id, config, sensors):
        """Create a single Indigo device. mac is used as the routing key
        (always the bare MAC); address is what Indigo stores (MAC for ch1,
        MAC-N for siblings).
        """
        props = {
            "address":   address,
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
            folder_id = self._ensure_device_folder(DEVICE_FOLDER_NAME)
            dev = indigo.device.create(
                protocol=indigo.kProtocol.Plugin,
                pluginId=self.pluginId,
                address=address,
                name=name,
                deviceTypeId=type_id,
                props=props,
                folder=folder_id,
            )
            ip    = config.get("ip", "")
            model = config.get("md", "")
            sub   = f"{ip} - {model}" if ip and model else (ip or model)
            if sub:
                dev.subModel = sub
                dev.replaceOnServer()
            # Cache by bare MAC for routing - all sibling channels live under
            # the same MAC key; lookup-by-topic+channel happens in handlers.
            self.devices_by_mac.setdefault(mac, dev)
            self.logger.info(
                f"Created Indigo device: {dev.name} (type={type_id}, "
                f"address={address}, ch={channel}) in folder '{DEVICE_FOLDER_NAME}'"
            )
        except Exception:
            self.logger.exception(f"Failed to create Indigo device for address {address}")

    def _refresh_device_props(self, dev, config, sensors):
        """Update read-only props (model/firmware/IP) from latest discovery,
        and keep subModel (the line shown in the device list) in sync."""
        props = dict(dev.pluginProps)
        changed = False
        for src_key, prop_key in (("md", "model"), ("sw", "firmware"), ("ip", "ip")):
            val = config.get(src_key, "")
            if val and props.get(prop_key, "") != val:
                props[prop_key] = val
                changed = True
        if changed:
            dev.replacePluginPropsOnServer(props)

        ip    = config.get("ip", "")
        model = config.get("md", "")
        sub   = f"{ip} - {model}" if ip and model else (ip or model)
        if sub and dev.subModel != sub:
            dev.subModel = sub
            dev.replaceOnServer()

    def _find_device_by_address(self, mac):
        for dev in indigo.devices.iter("self"):
            if dev.address == mac:
                return dev
        return None

    def _ensure_device_folder(self, name):
        """Return id of named device folder, creating it if absent."""
        for folder in indigo.devices.folders:
            if folder.name == name:
                return folder.id
        new_folder = indigo.devices.folder.create(name)
        self.logger.info(f"Created device folder: '{name}'")
        return new_folder.id

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
        kind_u = kind.upper()
        if kind_u.startswith("POWER"):
            # Plain "ON"/"OFF" - relay state change. POWER (no number) is
            # channel 1; POWER1..POWER8 are explicit channel numbers.
            channel = 1
            suffix = kind_u[5:]
            if suffix and suffix.isdigit():
                channel = int(suffix)
            dev = self._find_device_by_topic_channel(topic_name, channel)
            if dev:
                on = payload.strip().upper() == "ON"
                self._update_relay_state(dev, on)
            return

        # Non-POWER stat messages route to the primary (channel 1) device
        dev = self._find_device_by_topic(topic_name)
        if not dev:
            return
        if kind_u == "RESULT":
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                return
            self._handle_result(dev, data)
        elif kind_u.startswith("STATUS"):
            # The reply to "Status 0" (Request Status Update). Current Tasmota
            # sends it as one STATUS0 message; older firmware sends STATUS,
            # STATUS1 .. STATUS11 separately. Either way the regular report's
            # contents are under StatusSTS and the sensor readings under
            # StatusSNS, so they go through the same code as tele/STATE and
            # tele/SENSOR. Before 0.8.0 the reply was never read.
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                return
            if not isinstance(data, dict):
                return
            if isinstance(data.get("StatusSTS"), dict):
                self._apply_state(dev, data["StatusSTS"])
            if isinstance(data.get("StatusSNS"), dict):
                self._apply_sensor(dev, data["StatusSNS"])

    def _find_device_by_topic_channel(self, topic_name, channel):
        """Look up an Indigo device by Tasmota topic AND relay channel.
        Falls back to topic-only match (channel 1) if no match."""
        target_ch = str(channel)
        for dev in indigo.devices.iter("self"):
            if dev.pluginProps.get("topic") == topic_name \
                    and dev.pluginProps.get("channel", "1") == target_ch:
                return dev
        return None

    def _bare_mac(self, dev):
        """Return the bare MAC address with any '-N' sibling suffix stripped.
        Multi-relay siblings store addresses like 'MAC-2', 'MAC-3'; this gives
        the physical-device identifier shared across all siblings."""
        addr = dev.pluginProps.get("address", "") or (dev.address or "")
        return addr.split("-")[0]

    def _all_siblings_for_topic(self, topic_name):
        """Return every Indigo device that shares this Tasmota topic
        (channel-1 plus all multi-relay siblings)."""
        return [
            d for d in indigo.devices.iter("self")
            if d.pluginProps.get("topic") == topic_name
        ]

    def _all_siblings_for_mac(self, bare_mac):
        """Return every device whose bare MAC matches the given MAC."""
        if not bare_mac:
            return []
        return [
            d for d in indigo.devices.iter("self")
            if self._bare_mac(d) == bare_mac
        ]

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
        """LWT messages affect the whole physical device. Update availability
        on every Indigo sibling that shares the same MQTT topic, and fire
        the trigger with the bare MAC so user filters match."""
        availability = payload.strip()
        topic_name   = dev.pluginProps.get("topic", "")
        bare_mac     = self._bare_mac(dev)

        siblings = self._all_siblings_for_topic(topic_name) if topic_name else [dev]
        for sibling in siblings:
            try:
                sibling.updateStateOnServer("availability", availability)
            except Exception as exc:
                self.logger.debug(f"availability write failed on {sibling.name}: {exc}")

        if bare_mac:
            if availability == "Online":
                self.last_seen[bare_mac] = time.time()
                self._fire_event("deviceOnline", bare_mac)
            else:
                self._fire_event("deviceOffline", bare_mac)

    def _handle_state(self, dev, payload):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return
        if isinstance(data, dict):
            self._apply_state(dev, data)

    def _apply_state(self, dev, data):
        """Apply a STATE report: tele/<topic>/STATE, or StatusSTS in a Status reply."""
        bare_mac = self._bare_mac(dev)
        if bare_mac:
            self.last_seen[bare_mac] = time.time()

        # POWER and POWER1..POWERn keys - route each to the matching channel's
        # sibling device. For single-channel devices, the channel-1 sibling
        # IS the primary so this loop just updates `dev` itself.
        topic_name = dev.pluginProps.get("topic", "")
        for key, val in data.items():
            if not key.startswith("POWER"):
                continue
            suffix = key[5:]
            channel = int(suffix) if suffix.isdigit() else 1
            sibling = self._find_device_by_topic_channel(topic_name, channel) or dev
            self._update_relay_state(sibling, val == "ON")

        # Wi-Fi diagnostics
        wifi = data.get("Wifi", {})
        if "RSSI" in wifi:
            dev.updateStateOnServer("rssi", int(wifi["RSSI"]))
        if "Signal" in wifi:
            dev.updateStateOnServer("signal", int(wifi["Signal"]))
        if "Uptime" in data:
            dev.updateStateOnServer("uptime", data["Uptime"])
        if "RestartReason" in data:
            dev.updateStateOnServer("restartReason", data["RestartReason"])
        dev.updateStateOnServer("lastSeen", data.get("Time", datetime.now().isoformat()))

        # A light's STATE carries its Dimmer / Color / CT / White too.
        if dev.deviceTypeId == "tasmotaLight":
            self._apply_light_fields(dev, data)

    def _handle_sensor(self, dev, payload):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return
        if isinstance(data, dict):
            self._apply_sensor(dev, data)

    def _apply_sensor(self, dev, data):
        """Apply a SENSOR report: tele/<topic>/SENSOR, or StatusSNS in a Status reply."""
        bare_mac = self._bare_mac(dev)
        if bare_mac:
            self.last_seen[bare_mac] = time.time()

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

        # Dynamic capture of any other sensors. Tasmota publishes sensor
        # readings under named keys at the top level of the SENSOR payload:
        #   "DS18B20-1": {"Id":"...", "Temperature": 21.4}
        #   "BME280":    {"Temperature": 22.1, "Humidity": 55, "Pressure": 1013}
        #   "AM2301":    {"Temperature": 21.0, "Humidity": 48, "DewPoint": 9.9}
        # We flatten each into camelCase state IDs (bme280Temperature,
        # bme280Humidity, etc.) and use a declare-then-write cycle so the
        # very first message's values land too.
        skip_top_level = {"Time", "TempUnit", "PressureUnit", "ENERGY"}
        pending = []      # [(state_id, value), ...]
        for sensor_name, sub_payload in data.items():
            if sensor_name in skip_top_level or not isinstance(sub_payload, dict):
                continue
            for field_name, val in sub_payload.items():
                if field_name in ("Id", "Type"):
                    continue
                state_id = sensor_state_id(sensor_name, field_name)
                if not state_id:
                    continue
                pending.append((state_id, val))

        # Declare-before-write: find unknown state IDs, register them via
        # stateListOrDisplayStateIdChanged, re-fetch device, then write.
        # Without this, the first message that introduces a state would lose
        # its values (write fails with 'state not defined', we'd then declare
        # but never retry the write).
        unknown = [sid for sid, _ in pending if sid not in dev.states]
        if unknown:
            self._refresh_state_list_for_new_states(dev, unknown)
            dev = indigo.devices[dev.id]   # re-fetch with updated state list

        for state_id, val in pending:
            self._capture_dynamic_state(dev, state_id, val, [])

    def _handle_result(self, dev, data):
        """Parse a stat/<topic>/RESULT JSON payload.

        Tasmota sends a wide variety of RESULT shapes here. We handle the
        main ones explicitly and let the rest fall through unhandled.
        """
        # Button events: {"Button1":{"Action":"SINGLE"}} (SetOption73 1), or
        # the flat {"Button1":"SINGLE"}. Before 0.8.0 only the flat shape was
        # read, so the documented one reached lastAction and the trigger's
        # Action filter as the text of a whole dictionary.
        for button_num, action in parse_button_events(data):
            self._fire_button_event(dev, button_num, action)

        if dev.deviceTypeId == "tasmotaLight":
            self._apply_light_fields(dev, data)

        # Shutter position: {"Shutter1":{"Position":50, "Direction":0, ...}}
        for k, v in data.items():
            if k.startswith("Shutter") and isinstance(v, dict) and dev.deviceTypeId == "tasmotaShutter":
                if "Position" in v:
                    try:
                        dev.updateStateOnServer("brightnessLevel", int(v["Position"]))
                    except (TypeError, ValueError):
                        pass
                if "Direction" in v:
                    direction_map = {-1: "closing", 0: "stopped", 1: "opening"}
                    try:
                        dev.updateStateOnServer("direction", direction_map.get(int(v["Direction"]), str(v["Direction"])))
                    except (TypeError, ValueError):
                        pass

    def _apply_light_fields(self, dev, data):
        """Brightness, colour and colour mode from a light's RESULT or STATE."""
        # Dimmer: {"POWER":"ON","Dimmer":50}
        if "Dimmer" in data:
            try:
                level = int(data["Dimmer"])
                dev.updateStateOnServer("brightnessLevel", max(0, min(100, level)))
            except (TypeError, ValueError):
                pass

        # CT (mireds): {"CT": 300}
        if "CT" in data:
            try:
                dev.updateStateOnServer("colorTemp", int(data["CT"]))
            except (TypeError, ValueError):
                pass

        # HSBColor: "0,100,100"
        if "HSBColor" in data:
            dev.updateStateOnServer("hsbColor", str(data["HSBColor"]))

        # Color: "#RRGGBB" or "RRGGBB"
        if "Color" in data:
            dev.updateStateOnServer("hsbColor", str(data["Color"]))

        # Colour mode, declared since the first version and never written
        # until 0.8.0. Only written when the report says something.
        if any(k in data for k in ("Dimmer", "CT", "HSBColor", "Color", "White")):
            mode = light_colour_mode(dev.pluginProps.get("lightSubtype"), data)
            if mode:
                dev.updateStateOnServer("colorMode", mode)

    def _fire_button_event(self, dev, button_num, action):
        """Update device button states and fire buttonPressed triggers.

        State writes (lastButton, lastAction, pressCount) only apply to
        tasmotaButton-type devices. For devices that have buttons in addition
        to a primary relay (e.g. Sonoff Basic), we skip the state writes
        since those states aren't declared, but still fire the trigger so
        user automation works.
        """
        if dev.deviceTypeId == "tasmotaButton":
            try:
                count = int(dev.states.get("pressCount", 0) or 0) + 1
            except (TypeError, ValueError):
                count = 1
            try:
                dev.updateStatesOnServer([
                    {"key": "lastButton",  "value": button_num},
                    {"key": "lastAction",  "value": action},
                    {"key": "pressCount",  "value": count},
                ])
            except Exception as exc:
                self.logger.debug(f"Button state write on {dev.name} failed: {exc}")
        self.logger.debug(f"{dev.name}: Button{button_num} {action}")

        # Fire matching triggers regardless of device type
        bare_mac = self._bare_mac(dev)
        for trigger in self.event_triggers.values():
            if trigger.pluginTypeId != "buttonPressed":
                continue
            tprops    = trigger.pluginProps
            t_mac     = (tprops.get("targetAddress") or "").strip()
            t_btn_str = (tprops.get("targetButton")  or "").strip()
            t_action  = (tprops.get("targetAction")  or "").strip()
            if t_mac and normalise_mac(t_mac) != bare_mac:
                continue
            if t_btn_str:
                try:
                    if int(t_btn_str) != button_num:
                        continue
                except ValueError:
                    continue
            if t_action and t_action.upper() != action:
                continue
            indigo.trigger.execute(trigger)

    def _update_relay_state(self, dev, on_state):
        if dev.deviceTypeId in RELAY_TYPES:
            dev.updateStateOnServer("onOffState", on_state)
        elif dev.deviceTypeId == "tasmotaLight":
            dev.updateStateOnServer("onOffState", on_state)

    # --------------------------------------------------------
    # Dynamic state declaration (z2mbridge v1.7 pattern)
    # --------------------------------------------------------
    # Any unhandled sensor field becomes a custom state on the device, so
    # exotic Tasmota sensor combinations work without code changes.

    def _capture_dynamic_state(self, dev, state_id, value, new_states):
        """Write a dynamic state. If state didn't exist before, append to
        new_states so the caller can refresh the device's state list."""
        seen_key = "seenDynamicKeys"
        seen = (dev.pluginProps.get(seen_key) or "").split(",")
        is_new = state_id not in dev.states and state_id not in seen
        try:
            if isinstance(value, bool):
                dev.updateStateOnServer(state_id, bool(value))
            elif isinstance(value, int):
                dev.updateStateOnServer(state_id, int(value))
            elif isinstance(value, float):
                dev.updateStateOnServer(state_id, float(value))
            elif isinstance(value, (dict, list)):
                dev.updateStateOnServer(state_id, json.dumps(value))
            elif value is None:
                dev.updateStateOnServer(state_id, "")
            else:
                dev.updateStateOnServer(state_id, str(value))
            if is_new:
                new_states.append(state_id)
        except Exception as exc:
            # State not declared yet - record so we can refresh state list
            if "not defined" in str(exc).lower():
                new_states.append(state_id)
            else:
                self.logger.debug(f"Failed to set {state_id}={value!r} on {dev.name}: {exc}")

    def _refresh_state_list_for_new_states(self, dev, new_states):
        """Persist newly-seen state IDs in pluginProps and ask Indigo to
        refresh the device's state list so they become visible."""
        seen_key = "seenDynamicKeys"
        existing = set((dev.pluginProps.get(seen_key) or "").split(","))
        existing.discard("")
        updated = existing | set(new_states)
        if updated == existing:
            return
        props = dict(dev.pluginProps)
        props[seen_key] = ",".join(sorted(updated))
        try:
            dev.replacePluginPropsOnServer(props)
            dev.stateListOrDisplayStateIdChanged()
        except Exception as exc:
            self.logger.debug(f"State-list refresh on {dev.name} failed: {exc}")

    def getDeviceStateList(self, dev):
        """Override to advertise dynamically-captured states to Indigo so
        they appear in the device's Custom States panel and trigger menus.

        IMPORTANT: PluginBase.getDeviceStateList returns a LIVE reference,
        not a copy - mutating it corrupts the parser cache. Always copy.
        """
        state_list = list(indigo.PluginBase.getDeviceStateList(self, dev) or [])
        seen = (dev.pluginProps.get("seenDynamicKeys") or "").split(",")
        already_declared = {s.get("Key") for s in state_list if isinstance(s, dict)}
        for state_id in seen:
            if not state_id or state_id in already_declared:
                continue
            # Default to String type - actual value coercion happens at write.
            # Number/Integer-typed states would be nicer for triggers but we
            # don't always know the type up front. String works for everything.
            state_list.append(
                self.getDeviceStateDictForStringType(state_id, state_id, state_id)
            )
        return state_list

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

    @staticmethod
    def didDeviceCommPropertyChange(oldDevice, newDevice):
        """Restart comm only for props that affect MQTT routing or action dispatch.

        `topic` is the device's MQTT topic root; `channel` selects which relay
        on multi-channel devices; `shutterIndex` picks the shutter on
        roller-shutter firmware. `address` (MAC), `ip`, `model`, `firmware`
        are display-only metadata refreshed from the discovery payload — not
        connection-defining, so cosmetic changes shouldn't cycle comm.
        """
        keys = ("topic", "channel", "shutterIndex")
        return any(oldDevice.pluginProps.get(k) != newDevice.pluginProps.get(k) for k in keys)

    # --------------------------------------------------------
    # Indigo native control callbacks (relay/dimmer)
    # --------------------------------------------------------

    def actionControlSensor(self, action, dev):
        # tasmotaSensor + tasmotaButton are type="sensor"; without this a Send Status Request
        # logs "plugin does not define method actionControlSensor" and drops the action.
        if action.sensorAction == indigo.kSensorAction.RequestStatus:
            self._publish_command(dev, "Status", "0")
        else:
            self.logger.warning(f"{dev.name}: unsupported sensor action {action.sensorAction}")

    def actionControlDevice(self, action, dev):
        """Single dispatcher for relay AND dimmer AND shutter actions.

        Indigo's canonical SDK uses ONE actionControlDevice method for all
        device-control callbacks (TurnOn / TurnOff / Toggle / SetBrightness /
        BrightenBy / DimBy). A separate `actionControlDimmer` method is NOT
        in the modern SDK and is silently ignored - we used to have one,
        which meant tasmotaLight dimmer commands no-op'd. Merged here.
        See feedback_indigo_action_control_device_single_dispatcher memory.
        """
        channel = dev.pluginProps.get("channel", "1")
        cmd_power = "POWER" if channel == "1" else f"POWER{channel}"
        da = action.deviceAction

        # ----- Relay / Energy plug -----
        if dev.deviceTypeId in RELAY_TYPES:
            if da == indigo.kDeviceAction.TurnOn:
                self._publish_command(dev, cmd_power, "ON")
            elif da == indigo.kDeviceAction.TurnOff:
                self._publish_command(dev, cmd_power, "OFF")
            elif da == indigo.kDeviceAction.Toggle:
                self._publish_command(dev, cmd_power, "TOGGLE")
            else:
                self.logger.debug(f"Unhandled relay action {da} on {dev.name}")
            return

        # ----- Light (dimmer / CT / RGB) -----
        if dev.deviceTypeId == "tasmotaLight":
            if da == indigo.kDeviceAction.TurnOn:
                self._publish_command(dev, cmd_power, "ON")
            elif da == indigo.kDeviceAction.TurnOff:
                self._publish_command(dev, cmd_power, "OFF")
            elif da == indigo.kDeviceAction.Toggle:
                self._publish_command(dev, cmd_power, "TOGGLE")
            elif da == indigo.kDeviceAction.SetBrightness:
                level = int(action.actionValue)
                self._publish_command(dev, "Dimmer", str(level))
            elif da in (indigo.kDeviceAction.BrightenBy, indigo.kDeviceAction.DimBy):
                current = dev.brightness or 0
                delta = int(action.actionValue)
                if da == indigo.kDeviceAction.DimBy:
                    delta = -delta
                new_level = max(0, min(100, current + delta))
                self._publish_command(dev, "Dimmer", str(new_level))
            else:
                self.logger.debug(f"Unhandled light action {da} on {dev.name}")
            return

        # ----- Shutter -----
        # Indigo's dimmer slider on a tasmotaShutter sets the position 0-100.
        # TurnOn = fully open (ShutterOpenN), TurnOff = fully closed (ShutterCloseN).
        if dev.deviceTypeId == "tasmotaShutter":
            idx = dev.pluginProps.get("shutterIndex", "1")
            if da == indigo.kDeviceAction.TurnOn:
                self._publish_command(dev, f"ShutterOpen{idx}")
            elif da == indigo.kDeviceAction.TurnOff:
                self._publish_command(dev, f"ShutterClose{idx}")
            elif da == indigo.kDeviceAction.SetBrightness:
                level = int(action.actionValue)
                self._publish_command(dev, f"ShutterPosition{idx}", str(level))
            elif da in (indigo.kDeviceAction.BrightenBy, indigo.kDeviceAction.DimBy):
                current = dev.brightness or 0
                delta = int(action.actionValue)
                if da == indigo.kDeviceAction.DimBy:
                    delta = -delta
                new_level = max(0, min(100, current + delta))
                self._publish_command(dev, f"ShutterPosition{idx}", str(new_level))
            else:
                self.logger.debug(f"Unhandled shutter action {da} on {dev.name}")
            return

        self.logger.debug(f"actionControlDevice: no handler for type {dev.deviceTypeId} on {dev.name}")

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
        h = _as_int(action.props.get("hue"), 0)
        s = _as_int(action.props.get("saturation"), 100)
        b = _as_int(action.props.get("brightness"), 100)
        self._publish_command(dev, "HSBColor", f"{h},{s},{b}")

    def actionSetColorTemp(self, action, dev):
        m = _as_int(action.props.get("mired"), 300)
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

    def actionReboot(self, action, dev):
        """Publish cmnd/topic/Restart 1 - device reboots within a second.
        Reconnects to MQTT after ~5-10s. Useful for troubleshooting flaky
        devices or applying a setting change that requires a reboot."""
        self.logger.info(f"{dev.name}: rebooting (cmnd Restart 1)")
        self._publish_command(dev, "Restart", "1")

    # --------------------------------------------------------
    # One-click firmware upgrade
    # --------------------------------------------------------

    def _detect_device_architecture(self, dev):
        """Determine the device's chip family, a key of OTA_URLS ('ESP8266',
        'ESP32', 'ESP32-C3', 'ESP32-S3' ...), or None when the probe fails or
        the chip is not one we know the firmware for. Cached in the 'chip'
        prop so later upgrades skip the HTTP probe.

        Before 0.8.0 every ESP32 was cached as plain 'ESP32' in the 'arch'
        prop and sent the standard ESP32 firmware, which is wrong for a C3 or
        S3. That old cache is only trusted for 'ESP8266', which it got right;
        an old 'ESP32' is probed again.
        """
        cached = dev.pluginProps.get("chip", "")
        if cached in OTA_URLS:
            return cached
        if dev.pluginProps.get("arch", "") == "ESP8266":
            return "ESP8266"

        ip = dev.pluginProps.get("ip", "")
        if not ip:
            return None
        try:
            import requests
            resp = requests.get(
                f"http://{ip}/cm",
                params={"cmnd": "Status 2"},
                timeout=5,
            )
            if resp.status_code != 200:
                return None
            hw = resp.json().get("StatusFWR", {}).get("Hardware", "") or ""
        except Exception as exc:
            self.logger.debug(f"Architecture probe of {ip} failed: {exc}")
            return None
        chip = chip_family(hw)
        if not chip:
            self.logger.warning(
                f"{dev.name}: the device reports its chip as '{hw}', which this "
                "plugin does not know the Tasmota firmware for"
            )
            return None
        props = dict(dev.pluginProps)
        props["chip"] = chip
        dev.replacePluginPropsOnServer(props)
        return chip

    def actionUpgradeFirmware(self, action, dev):
        """Detect ESP architecture, set OTA URL to the matching official
        Tasmota release, and trigger Upgrade 1. The device reboots and
        reconnects to MQTT within ~30-60 seconds.
        """
        ip    = dev.pluginProps.get("ip", "")
        topic = dev.pluginProps.get("topic", "")
        if not topic:
            self.logger.warning(f"{dev.name}: no MQTT topic; cannot trigger upgrade")
            return
        if not ip:
            self.logger.warning(
                f"{dev.name}: no IP recorded; cannot probe architecture for OTA URL"
            )
            return

        arch = self._detect_device_architecture(dev)
        ota_url = OTA_URLS.get(arch or "")
        if not ota_url:
            self.logger.warning(
                f"{dev.name}: not upgraded - could not tell which Tasmota firmware "
                "this chip needs. Upgrade it from its own page with the "
                "Open Firmware Upgrade Page action."
            )
            return

        self.logger.info(
            f"{dev.name}: setting OTA URL to {ota_url} and triggering upgrade ({arch})"
        )
        # Backlog runs multiple commands in sequence. Tasmota will reboot
        # mid-Backlog after Upgrade 1 - that's fine, the OtaUrl was persisted
        # before reboot so it survives.
        self._publish_command(dev, "Backlog", f"OtaUrl {ota_url}; Upgrade 1")
        self.logger.info(
            f"{dev.name}: upgrade triggered. Device will reboot and reconnect to "
            "MQTT in ~30-60s. firmwareStatus will refresh on next plugin start."
        )

    # Menu picker - lists all Tasmota devices with firmware status in the label.
    # Multi-relay devices: only the channel-1 (primary) sibling is listed,
    # since firmware is per-physical-device, not per-channel. Picking ch 1
    # upgrades the device as a whole.
    def pickTasmotaDeviceWithStatus(self, filter="", valuesDict=None, typeId="", targetId=0):
        devs = sorted(
            (d for d in indigo.devices.iter("self")
             if d.pluginId == self.pluginId
             and "-" not in (d.pluginProps.get("address") or d.address or "")),
            key=lambda d: d.name,
        )
        out = []
        for d in devs:
            status = d.states.get("firmwareStatus", "") or "(not yet checked)"
            out.append((str(d.id), f"{d.name}   [{status}]"))
        return out

    def menuUpgradeFirmware(self, valuesDict=None, typeId=None):
        """Menu callback - resolves the picked device and delegates to
        actionUpgradeFirmware. Picking a device + clicking the Upgrade
        button is treated as intent, no extra confirm step.
        """
        try:
            devid = int(valuesDict.get("targetDevice", "0"))
        except (TypeError, ValueError):
            devid = 0
        if not devid or devid not in indigo.devices:
            self.logger.warning("Upgrade: no device selected")
            return False
        dev = indigo.devices[devid]

        # Wrap a minimal action-like object for the shared callback
        class _A: pass
        a = _A()
        a.props = {}
        self.actionUpgradeFirmware(a, dev)
        return True

    def _open_url_locally(self, url):
        """Open a URL in the default browser ON THE INDIGO MAC. For remote
        Indigo clients (Touch / reflector / different Mac) this opens on
        the server, not on the user's screen - in that case they should
        copy the URL from the log instead."""
        import webbrowser
        try:
            webbrowser.open(url, new=2)
            self.logger.info(f"Opened {url} in default browser on the Indigo Mac")
        except Exception as exc:
            self.logger.warning(f"Could not open {url}: {exc}")

    def actionOpenWebUI(self, action, dev):
        ip = dev.pluginProps.get("ip", "")
        if not ip:
            self.logger.warning(f"{dev.name}: no IP recorded; cannot open web UI")
            return
        self._open_url_locally(f"http://{ip}/")

    def actionOpenFirmwarePage(self, action, dev):
        ip = dev.pluginProps.get("ip", "")
        if not ip:
            self.logger.warning(f"{dev.name}: no IP recorded; cannot open firmware page")
            return
        self._open_url_locally(f"http://{ip}/up")

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

                # One-shot firmware check ~15s after startup, once devices
                # have appeared via MQTT discovery. Gives up at 60s if no
                # devices appear (e.g. fresh install with nothing yet on MQTT).
                if not self.initial_firmware_check_done and self.startup_time:
                    elapsed = now - self.startup_time
                    if elapsed >= 15 and self.devices_by_mac:
                        self.checkFirmwareUpdates()
                        self.initial_firmware_check_done = True
                    elif elapsed >= 60:
                        self.initial_firmware_check_done = True   # skip

                # LWT timeout watcher - mark all siblings offline together
                for bare_mac, ts in list(self.last_seen.items()):
                    if now - ts > OFFLINE_TIMEOUT_SEC:
                        siblings = self._all_siblings_for_mac(bare_mac)
                        changed = False
                        for dev in siblings:
                            if dev.states.get("availability") != "Offline":
                                dev.updateStateOnServer("availability", "Offline")
                                changed = True
                        if changed:
                            self._fire_event("deviceOffline", bare_mac)
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
        self._apply_log_level(valuesDict.get("logLevel", "INFO"))
        self.log_raw   = bool(valuesDict.get("logRawPayloads", False))
        self.auto_create = bool(valuesDict.get("autoCreateDevices", True))

        # Reconnect on ANY broker change, resolved in the same order as at
        # start. Before 0.8.0 only a new host reconnected, and the save path
        # put the dialog's host ahead of IndigoSecrets.py.
        broker = resolve_broker(valuesDict)
        if broker == self._broker():
            return
        self.logger.info("Broker settings changed - reconnecting MQTT")
        self._mqtt_disconnect()
        self._set_broker(broker)
        if not self.mqtt_host:
            self.logger.error(
                "No MQTT broker configured. Set MQTT_BROKER in IndigoSecrets.py "
                "or fill Broker Host in Plugins -> Tasmota Bridge -> Configure..."
            )
            return
        if not self.startup_time:
            # startup() found no broker and never started the clock that the
            # one-shot firmware check waits on.
            self.startup_time = time.time()
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

    # --------------------------------------------------------
    # Open Device Page (Plugins menu, device picker)
    # --------------------------------------------------------

    def pickTasmotaDevice(self, filter="", valuesDict=None, typeId="", targetId=0):
        """List-method callback - dropdown source for the device picker."""
        devs = sorted(
            (d for d in indigo.devices.iter("self") if d.pluginId == self.pluginId),
            key=lambda d: d.name,
        )
        return [(str(d.id), d.name) for d in devs]

    def menuOpenDevicePage(self, valuesDict=None, typeId=None):
        """Menu callback - open the chosen device's main Tasmota web page
        in the default browser on the Indigo Mac. Firmware upgrade has its
        own dedicated menu, so this only opens the main page.
        """
        try:
            devid = int(valuesDict.get("targetDevice", "0"))
        except (TypeError, ValueError):
            devid = 0
        if not devid or devid not in indigo.devices:
            self.logger.warning("Open device page: no device selected")
            return False
        dev = indigo.devices[devid]
        ip  = dev.pluginProps.get("ip", "")
        if not ip:
            self.logger.warning(f"{dev.name}: no IP recorded; cannot open page")
            return False
        self._open_url_locally(f"http://{ip}/")
        return True

    # --------------------------------------------------------
    # Firmware update check
    # --------------------------------------------------------

    def _parse_version(self, s):
        """Parse a Tasmota version string into a tuple of ints for comparison.

        Accepts: '15.0.1(release-tasmota)', 'v15.0.1.4', '15.0.1', etc.
        Strips parenthetical suffix and leading 'v', then splits on dots.
        Returns None if no numeric components are parseable.
        """
        if not s:
            return None
        s = str(s).split("(")[0].strip().lstrip("v")
        parts = []
        for p in s.split("."):
            try:
                parts.append(int(p))
            except ValueError:
                break
        return tuple(parts) if parts else None

    @staticmethod
    def _fetch_tasmota_latest(timeout=10):
        """Fetch latest Tasmota tag from GitHub releases. Returns string or None.

        Standalone - no self.logger, no cache. Safe to call from __init__
        before the plugin is fully constructed. Callers handle caching.
        """
        try:
            import requests
            resp = requests.get(
                "https://api.github.com/repos/arendst/Tasmota/releases/latest",
                timeout=timeout,
                headers={
                    "Accept":     "application/vnd.github+json",
                    "User-Agent": "Indigo-TasmotaBridge",
                },
            )
            if resp.status_code != 200:
                return None
            tag = (resp.json().get("tag_name", "") or "").lstrip("v")
            return tag or None
        except Exception:
            return None

    def _get_tasmota_latest_release(self):
        """Return latest Tasmota tag, 24h-cached. Calls _fetch_tasmota_latest on miss."""
        now = time.time()
        if self.gh_release_cache["tag"] and (now - self.gh_release_cache["ts"]) < 86400:
            return self.gh_release_cache["tag"]
        tag = self._fetch_tasmota_latest()
        if tag:
            self.gh_release_cache = {"tag": tag, "ts": now}
        else:
            self.logger.warning("Could not retrieve latest Tasmota release from GitHub")
        return tag

    def checkFirmwareUpdates(self, valuesDict=None, typeId=None):
        """Menu callback - report each Tasmota device's firmware against the
        latest GitHub release. Bordered, sectioned output for readability.
        Also called once at startup by runConcurrentThread.
        """
        latest_str = self._get_tasmota_latest_release()
        if not latest_str:
            return
        latest = self._parse_version(latest_str)

        devices = [
            d for d in indigo.devices.iter("self")
            if d.pluginId == self.pluginId
        ]
        if not devices:
            indigo.server.log("Tasmota Firmware Check: no Tasmota devices in Indigo yet")
            return

        # Bucket each device by status AND write the persistent firmwareStatus
        # state so it shows in the device's Custom States panel.
        up_to_date  = []
        out_of_date = []
        unknown     = []
        for dev in sorted(devices, key=lambda d: d.name):
            cur_str = dev.pluginProps.get("firmware", "")
            ip      = dev.pluginProps.get("ip", "")
            cur     = self._parse_version(cur_str)
            if not cur or not latest:
                unknown.append((dev.name, cur_str))
                status = "unknown"
            elif cur >= latest:
                up_to_date.append((dev.name, cur_str))
                status = "up-to-date"
            else:
                out_of_date.append((dev.name, cur_str, ip))
                status = f"update available: {latest_str}"
            try:
                dev.updateStateOnServer("firmwareStatus", status)
            except Exception as exc:
                self.logger.debug(f"Could not write firmwareStatus on {dev.name}: {exc}")

        # ---- Render lean summary ----
        # Goal: 1-4 lines. Latest version was already announced in the
        # startup banner, so don't repeat it. Each device gets its
        # firmwareStatus state set (above) for persistent visibility.
        if out_of_date:
            self.logger.info(
                f"{len(out_of_date)} Tasmota device{'s' if len(out_of_date) != 1 else ''} "
                f"{'have' if len(out_of_date) != 1 else 'has'} updates available:"
            )
            for name, cur_str, _ in out_of_date:
                self.logger.info(f"  {name}  ({cur_str} -> {latest_str})")
            self.logger.info(
                "Use 'Plugins -> Tasmota Bridge -> Upgrade Tasmota Firmware...' "
                "to upgrade each one."
            )
        elif up_to_date and not unknown:
            self.logger.info(
                f"All {len(up_to_date)} Tasmota device{'s' if len(up_to_date) != 1 else ''} "
                f"on latest firmware ({latest_str})."
            )

        if unknown:
            self.logger.info(
                f"{len(unknown)} Tasmota device(s) with unparseable firmware version - "
                "check their pluginProps."
            )

    # --------------------------------------------------------
    # Show Plugin Info
    # --------------------------------------------------------

    def showPluginInfo(self, valuesDict=None, typeId=None):
        extras = [
            ("MQTT Broker:",        f"{self.mqtt_host}:{self.mqtt_port}"),
            ("MQTT Connected:",     "yes" if self.mqtt_connected else "no"),
            ("Devices discovered:", str(len(self.discovery_cache))),
            ("Devices in Indigo:",  str(len(self.devices_by_mac))),
            ("Timestamps in Log:",  "ON" if self.timestamp_enabled else "OFF"),
        ]
        if log_startup_banner:
            log_startup_banner(self.pluginId, self.pluginDisplayName, self.pluginVersion, extras=extras)
        else:
            indigo.server.log(f"{self.pluginDisplayName} v{self.pluginVersion}")
            for label, value in extras:
                indigo.server.log(f"  {label} {value}")

    def menuToggleTimestamps(self):
        self.timestamp_enabled = not self.timestamp_enabled
        self.pluginPrefs["timestampEnabled"] = self.timestamp_enabled
        if self._ts_filter:
            self._ts_filter.enabled = self.timestamp_enabled
        state = "ON" if self.timestamp_enabled else "OFF"
        indigo.server.log(f"[{self.pluginDisplayName}] Timestamps in Log -> {state}")
