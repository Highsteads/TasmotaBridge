# Tasmota Bridge — Indigo Plugin

Bridges [Tasmota](https://tasmota.github.io/docs/) MQTT devices (Sonoff, Athom, ESP8266/ESP32-based)
into Indigo 2025.2+ as native device types via any Mosquitto MQTT broker.

Designed to complement the [SMLight Hub](https://smlight.tech/), which runs both
Zigbee2MQTT and Mosquitto natively on-device — pair this plugin with
[Zigbee2MQTTBridge](https://github.com/Highsteads/Zigbee2MQTTBridge) and
[ShellyDirect](https://github.com/Highsteads/ShellyDirect) for a complete
multi-protocol home automation broker setup.

## Status

**Public beta (v0.7.x).** The core relay + energy paths are fully validated
on Athom plugs running Tasmota 15.4.0. Other device types compile and
respond to commands but have not been validated against real hardware yet —
testers welcome (see Supported Devices below). Report issues at the GitHub
repo.

## Features

- **Auto-discovery** via Tasmota's native `tasmota/discovery/<MAC>/` topic
  (enabled by default in Tasmota 11+ via SetOption147)
- **Native Indigo device types** — relays, energy plugs, lights, sensors,
  shutters, buttons
- **Multi-relay devices** — Sonoff 4CH and similar create one Indigo device
  per active relay channel automatically
- **Dynamic sensor capture** — DS18B20, BME280, AM2301, DHT22, etc. — every
  field in the SENSOR payload becomes a custom Indigo state automatically,
  no plugin code changes needed
- **Firmware monitoring** — startup banner shows latest Tasmota release from
  GitHub, per-device `firmwareStatus` state, summary at boot of which devices
  need updating
- **One-click firmware upgrade** — Plugins menu picker auto-detects ESP
  architecture and triggers `Backlog OtaUrl <correct-url>; Upgrade 1`
- **Button triggers** — Tasmota wall switches and scene controllers surface
  SINGLE / DOUBLE / TRIPLE / HOLD / etc. as Indigo triggers, with per-device
  and per-button filters
- **Restart reason tracking** — `restartReason` state shows why each device
  last rebooted (Power On, Software, Watchdog, etc.)
- **No cloud, no third-party servers** — purely local MQTT

## Supported Devices

| Class | Status | Examples |
|---|---|---|
| Single-relay plug | ✅ Validated | Sonoff Basic, Athom plug, generic ESP8266+relay |
| Energy-monitoring plug | ✅ Validated | Sonoff POW (R1/R2/R3), Athom PG04-UK16A, Athom Smart Plug |
| Multi-relay device | 🟡 Code complete, beta-test welcome | Sonoff 4CH, dual-channel plugs |
| Environmental sensors | 🟡 Dynamic capture wired, beta-test welcome | Sonoff TH (DS18B20), BME280, AM2301, DHT22, AHT10 |
| Wall switches / buttons | 🟡 Code complete, beta-test welcome | Sonoff T1/T2/T3, Sonoff 4-button, generic GPIO-button devices |
| Dimmer | 🟡 Best-effort, beta-test welcome | Athom dimmer, MagicHome dimmer |
| RGB / RGBW / RGBCW bulbs | 🟡 Best-effort, beta-test welcome | Athom bulbs, generic Wi-Fi bulbs flashed with Tasmota |
| Shutters / blinds | 🟡 Best-effort, beta-test welcome | Sonoff Dual R2 / R3 in shutter mode, MJ-SD01 |

✅ = author tested against real hardware
🟡 = code written from Tasmota documentation but not yet validated against the device class; expect rough edges

## Compatibility

| Component | Tested With |
|---|---|
| Indigo | 2025.2 (API 3.0+) |
| Python | 3.13 (Indigo embedded) |
| Tasmota | 11.x+ (15.0.1 confirmed) |
| Broker | Mosquitto on Indigo Mac, SMLight Hub native broker, any Mosquitto |
| Hardware | Sonoff Basic/POW R2/R3, Athom plugs (PG04-UK16A), Shelly Plus 1/2.5, generic ESP8266/8285/32 |

## Installation

1. Go to the [Releases page](https://github.com/Highsteads/TasmotaBridge/releases)
   and download `TasmotaBridge.indigoPlugin.zip`
2. Unzip the downloaded file — you will get `TasmotaBridge.indigoPlugin`
3. Double-click `TasmotaBridge.indigoPlugin` — Indigo will install it automatically
4. Configure via `Plugins → Tasmota Bridge → Configure...`

## Configuration

The plugin reads MQTT broker credentials in this order:
1. `IndigoSecrets.py` at `/Library/Application Support/Perceptive Automation/` (preferred)
2. PluginConfig (entered in the Indigo GUI)

### `IndigoSecrets.py` keys

```python
MQTT_BROKER   = "192.168.x.x"   # broker IP or hostname
MQTT_PORT     = 1883
MQTT_USERNAME = "your-user"
MQTT_PASSWORD = "your-password"
```

If not present, fill the same values via Plugins → Tasmota Bridge → Configure...

## On your Tasmota devices

In the Tasmota web UI (Configuration → Configure MQTT):
- **Host:** your Mosquitto broker IP
- **Port:** 1883 (or 8883 for TLS)
- **User / Password:** broker credentials
- **Topic:** any unique name (the plugin uses MAC for identification, not topic)
- **Full Topic:** leave at `%prefix%/%topic%/` (default)

Discovery is on by default in modern Tasmota. To verify:
```
http://<device-ip>/cm?cmnd=SetOption147
```
Should return `{"SetOption147":"OFF"}` (off means discovery enabled — naming
quirk in Tasmota). If `ON`, run `SetOption147 0` to enable discovery.

## Troubleshooting

### A new Tasmota device hasn't appeared in Indigo

1. **Check MQTT is configured on the device.** Open the device's web UI
   (e.g. `http://192.168.4.144`) → Configuration → Configure MQTT.
   Confirm Host points at your Mosquitto broker and credentials are correct.
2. **Check discovery is enabled.** From the device's Console, run
   `SetOption147` — should return `OFF` (counter-intuitive naming:
   "OFF" means discovery is **enabled**). If it says `ON`, run
   `SetOption147 0` to enable discovery.
3. **Check the broker received it.** From the Indigo Mac:
   ```
   mosquitto_sub -h <broker-ip> -u <user> -P <pass> -v -t 'tasmota/discovery/#'
   ```
   You should see the device's `config` and `sensors` topics replay
   immediately (they are retained).
4. **Force the device to republish discovery.** From its Console:
   `SetOption147 1; SetOption147 0` (toggle off then on). Or use the
   plugin's `Plugins → Tasmota Bridge → Discover Tasmota Devices` menu
   which re-subscribes and pulls retained messages again.

### Factory-default device (never connected to WiFi)

These can't be auto-discovered — they're broadcasting their own AP and
aren't on your LAN. Onboard them via the device's own captive portal:
connect your phone or laptop to the device's `tasmota_XXXXXX-1234` SSID,
open `http://192.168.4.1`, and enter your WiFi credentials **and** your
MQTT broker details on the same page. After reboot, the device joins
your LAN and the plugin picks it up automatically.

## License

MIT
