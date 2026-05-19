# Tasmota Bridge — Indigo Plugin

Bridges [Tasmota](https://tasmota.github.io/docs/) MQTT devices (Sonoff, Athom, ESP8266/ESP32-based)
into Indigo 2025.2+ as native device types via any Mosquitto MQTT broker.

Designed to complement the [SMLight Hub](https://smlight.tech/), which runs both
Zigbee2MQTT and Mosquitto natively on-device — pair this plugin with
[Zigbee2MQTTBridge](https://github.com/Highsteads/Zigbee2MQTTBridge) and
[ShellyDirect](https://github.com/Highsteads/ShellyDirect) for a complete
multi-protocol home automation broker setup.

## Status

**Pre-release / scaffold.** Currently in development. Use at your own risk.

## Features (planned)

- **Auto-discovery** via Tasmota's native `tasmota/discovery/<MAC>/` topic
  (enabled by default in Tasmota 11+ via SetOption147)
- **Native Indigo device types** — relays, dimmers, RGB/RGBW lights, energy plugs,
  environmental sensors, shutters
- **HTTP control fallback** when MQTT is unavailable
- **Dynamic state capture** — every unknown payload field becomes a queryable
  device state automatically
- **No cloud, no third-party servers** — purely local MQTT

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
