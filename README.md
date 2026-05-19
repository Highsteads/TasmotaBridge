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

## License

MIT
