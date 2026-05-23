# Tasmota Bridge — Indigo Plugin

Bridges [Tasmota](https://tasmota.github.io/docs/) MQTT devices into
[Indigo Domotics](https://www.indigodomo.com/) 2025.2+ as native device
types. Designed to work locally over any Mosquitto MQTT broker — pairs
naturally with the [SMLight Hub](https://smlight.tech/) (which ships
Mosquitto on-device alongside Zigbee2MQTT), the Mosquitto broker that
runs natively on the Indigo Mac, or any other broker on your LAN.

**No cloud. No phone-home. Purely local MQTT.**

---

## Table of Contents

- [Status](#status)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Broker Configuration](#broker-configuration)
- [Setting Up Tasmota Devices](#setting-up-tasmota-devices)
- [Supported Device Types](#supported-device-types)
  - [tasmotaRelay](#tasmotarelay--single-channel-switch--plug)
  - [tasmotaEnergyPlug](#tasmotaenergyplug--energy-monitoring-plug)
  - [tasmotaLight](#tasmotalight--dimmer--ct--rgb)
  - [tasmotaSensor](#tasmotasensor--environmental--multi-purpose-sensor)
  - [tasmotaShutter](#tasmotashutter--blinds--rollers)
  - [tasmotaButton](#tasmotabutton--wall-switch--scene-controller)
- [Multi-Relay Devices](#multi-relay-devices)
- [Custom Actions](#custom-actions)
- [Custom Events (Triggers)](#custom-events-triggers)
- [Plugin Menu Items](#plugin-menu-items)
- [Firmware Management](#firmware-management)
- [How Discovery Works](#how-discovery-works)
- [Dynamic Sensor Capture](#dynamic-sensor-capture)
- [Architecture Overview](#architecture-overview)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Beta Tester Checklist](#beta-tester-checklist)
- [Contributing](#contributing)
- [License](#license)

---

## Status

**Public beta (v0.7.x).** The core relay + energy paths are fully
validated on Athom plugs running Tasmota 15.4.0. Multi-relay, sensors,
buttons, lights, and shutters have working code that passes simulation
tests but has not been validated against real hardware — testers
welcome. Report issues at the
[GitHub repo](https://github.com/Highsteads/TasmotaBridge/issues).

---

## Quick Start

1. **Install the plugin** — download `TasmotaBridge.indigoPlugin.zip`
   from the [Releases](https://github.com/Highsteads/TasmotaBridge/releases)
   page, unzip, double-click. Indigo installs it automatically.
2. **Configure the broker** — `Plugins → Tasmota Bridge → Configure...`,
   enter the IP/hostname, port, username, and password of your MQTT broker.
   (Or skip this if you have an `IndigoSecrets.py` file — see below.)
3. **Configure Tasmota devices** — point each device's MQTT setting at
   the same broker. Tasmota's native discovery (`SetOption147`, on by
   default in modern firmware) handles the rest.
4. **Watch devices appear** — Indigo's device list grows a `Tasmota`
   folder and populates it as devices come online.

That's it. Relay control via `Turn On / Turn Off`, energy telemetry as
native Indigo `curEnergyLevel` / `accumEnergyTotal` states, sensor
readings as Custom States, all working out of the box.

---

## Installation

1. Go to the
   [Releases page](https://github.com/Highsteads/TasmotaBridge/releases)
   and download the latest `TasmotaBridge.indigoPlugin.zip`
2. Unzip the file — you'll get `TasmotaBridge.indigoPlugin`
3. Double-click — Indigo installs it
4. Open `Plugins` menu — `Tasmota Bridge` submenu appears
5. Configure via `Plugins → Tasmota Bridge → Configure...`

The plugin auto-installs its only Python dependency (`paho-mqtt`) on
first launch — Indigo runs `pip install -r requirements.txt` into the
plugin's `Contents/Packages/` directory.

---

## Broker Configuration

The plugin reads MQTT broker credentials in this order of precedence:

1. **`IndigoSecrets.py`** at
   `/Library/Application Support/Perceptive Automation/` (preferred)
2. **PluginConfig** dialog (`Plugins → Tasmota Bridge → Configure...`)

### `IndigoSecrets.py` keys

```python
MQTT_BROKER   = "192.168.1.20"   # broker IP or hostname
MQTT_PORT     = 1883
MQTT_USERNAME = "your-user"
MQTT_PASSWORD = "your-password"
```

If `IndigoSecrets.py` is absent, fill the same values in the PluginConfig
dialog. Either path works equally well — the dialog is mainly for users
who don't already use CliveS's `IndigoSecrets.py` convention for their
other plugins.

### TLS

Tick the **Use TLS** checkbox in PluginConfig for brokers running on TLS
(typically port 8883). Note: Tasmota itself defaults to plain MQTT on
port 1883 — TLS is uncommon for local LAN deployments.

---

## Setting Up Tasmota Devices

On each Tasmota device (open its web UI at `http://<device-ip>`):

1. **Configuration → Configure MQTT**
   - **Host:** your Mosquitto broker IP
   - **Port:** 1883 (or 8883 for TLS)
   - **User / Password:** broker credentials
   - **Topic:** any unique name (the plugin uses MAC for identification,
     not topic name)
   - **Full Topic:** leave at `%prefix%/%topic%/` (default)
2. Click **Save** — device reboots

That's it. The plugin's discovery is **automatic** in modern Tasmota
(11+) via `SetOption147`. To verify on the device's Console:

```
SetOption147
```

Should return `{"SetOption147":"OFF"}`. Counter-intuitively, **"OFF"
means discovery is enabled** — Tasmota's flag is named backwards. If it
says `ON`, run `SetOption147 0` to enable discovery.

### Factory-default (AP-mode) devices

Brand-new Tasmota devices broadcast their own Wi-Fi access point
(SSID `tasmota_XXXXXX-1234`) and serve a setup page at `http://192.168.4.1`.
These **cannot** be auto-discovered by this plugin — they're not on
your LAN yet. Onboard them through the device's captive portal first,
then they'll appear in Indigo automatically.

---

## Supported Device Types

The plugin auto-detects device type from Tasmota's discovery payload
and creates the matching Indigo device. You don't need to manually pick
a type — it just works.

### `tasmotaRelay` — single-channel switch / plug

**Detected when:** `rl[0]=1` and no ENERGY sensor present.

**Examples:** Sonoff Basic, Athom plain plug, generic ESP8266+relay.

**Indigo class:** `relay` device.

**States:**
- `onOffState` (native) — relay state (True / False)
- `availability` — `Online` / `Offline` from LWT
- `rssi`, `signal` — Wi-Fi metrics
- `uptime` — device uptime string from Tasmota
- `lastSeen` — last telemetry timestamp
- `restartReason` — why the device last rebooted
- `firmwareStatus` — `up-to-date` or `update available: 15.4.0`

**Indigo controls:** `Turn On`, `Turn Off`, `Toggle` (native).

---

### `tasmotaEnergyPlug` — energy-monitoring plug

**Detected when:** `rl[0]=1` AND ENERGY sensor present in discovery sensors.

**Examples:** Sonoff POW (R1/R2/R3), Athom Smart Plug (PG04, PG11),
Athom PG04-UK16A.

**Indigo class:** `relay` with `subType=kEnergyMeter`.

**States:**
- `onOffState` (native)
- `curEnergyLevel` (native) — instantaneous power in watts
- `accumEnergyTotal` (native) — lifetime energy in kWh
- `voltage`, `current`, `apparentPower`, `reactivePower`, `powerFactor`
- `energyToday`, `energyYesterday` — daily totals
- Plus all the diagnostics from `tasmotaRelay` (availability, rssi, etc.)

**Indigo controls:** Turn On / Off / Toggle. Energy values shown
inline in the device list.

---

### `tasmotaLight` — dimmer / CT / RGB

**Detected when:** `lt_st >= 1` in discovery config.

`lt_st` values:
| `lt_st` | Meaning |
|---|---|
| 1 | Plain dimmer (single white channel) |
| 2 | CT (colour-temperature white) |
| 3 | RGB |
| 4 | RGBW |
| 5 | RGBCW (RGB + cool/warm white) |

**Examples:** Athom RGB / CT bulbs, MagicHome controllers, generic
Wi-Fi bulbs flashed with Tasmota.

**Indigo class:** `dimmer` device.

**States:**
- `onOffState`, `brightnessLevel` (native)
- `colorMode` — current Tasmota colour mode
- `colorTemp` — colour temperature in mireds (153 = cool, 500 = warm)
- `hsbColor` — last HSB value as `"H,S,B"`
- Diagnostics: availability, rssi, etc.

**Capability flags** set automatically from `lt_st`:
- `SupportsColor`, `SupportsRGB` — set for `lt_st >= 3`
- `SupportsWhite` — set for CT / RGBW / RGBCW
- `SupportsWhiteTemperature` — set for CT / RGBCW

**Indigo controls:** Turn On / Off, Brightness slider (native dimmer
controls). For colour and CT, use the **Set HSB Color** and
**Set Colour Temperature** custom actions.

---

### `tasmotaSensor` — environmental / multi-purpose sensor

**Detected when:** no relays, no light, but the discovery sensors
payload has named sensor blocks.

**Examples:** ESP with DS18B20, BME280, AM2301, DHT22, AHT10, SHT3x, etc.

**Indigo class:** `sensor` device.

**States:** Dynamic — every named sensor block in the SENSOR telemetry
becomes a series of states. For example, a BME280 generates:
- `bme280Temperature`
- `bme280Humidity`
- `bme280Pressure`
- `bme280DewPoint`

DS18B20 temperature probes:
- `ds18b201Temperature` (first probe)
- `ds18b202Temperature` (second probe, if multiple)

See [Dynamic Sensor Capture](#dynamic-sensor-capture) for the rules.

---

### `tasmotaShutter` — blinds / rollers

**Detected when:** `sht[]` has at least one non-zero entry.

**Examples:** Sonoff Dual R2 / R3 in shutter mode, MJ-SD01.

**Indigo class:** `dimmer` device (0% = closed, 100% = open).

**States:**
- `brightnessLevel` (native) — current position 0–100
- `direction` — `opening` / `closing` / `stopped`
- Plus standard diagnostics.

**Indigo controls:** Brightness slider sets shutter position. Or use
the **Open Shutter / Close Shutter / Stop Shutter** custom actions.

---

### `tasmotaButton` — wall switch / scene controller

**Detected when:** `btn[]` has non-zero entries AND no relays.

**Examples:** Sonoff T1/T2/T3 wall switches (input-only mode), Sonoff
4-button scene controller, generic GPIO-button DIY devices.

**Indigo class:** `sensor` device (input-only).

**States:**
- `lastButton` — number of the most recently pressed button (1–8)
- `lastAction` — `SINGLE` / `DOUBLE` / `TRIPLE` / `QUAD` / `PENTA` / `HOLD` / `CLEAR`
- `pressCount` — total press count (monotonically increasing — increments
  on every press so triggers fire even for repeated identical presses)

To react to button presses, create a Trigger using the
[**Tasmota Button Pressed** event](#tasmota-button-pressed).

---

## Multi-Relay Devices

For devices with multiple relays (e.g. Sonoff 4CH), the plugin creates
**one Indigo device per active channel**. Naming convention:

- Single-channel device: `<dn>` (e.g. `Kitchen Plug`)
- Multi-channel device: `<dn> - Ch 1`, `<dn> - Ch 2`, `<dn> - Ch 3`, `<dn> - Ch 4`

Address scheme:
- **Channel 1** keeps the bare MAC: `2462AB6CDC64`
- **Channels 2+** get a suffix: `2462AB6CDC64-2`, `2462AB6CDC64-3`, ...

The plugin routes `POWER1` to channel 1, `POWER2` to channel 2, etc.
Each sibling controls its own relay independently via Indigo's native
Turn On / Turn Off.

**Energy monitoring on multi-relay devices** is attached to the channel-1
sibling (Tasmota reports ENERGY at the device level, not per channel).

**LWT (availability) and firmware status** are synced across all siblings
of the same physical device — if the physical device goes offline,
**all** its Indigo siblings show `availability = Offline` together.

---

## Custom Actions

Available via `Action Group` editor and per-device action menus.

| Action | Devices | Description |
|---|---|---|
| **Send Raw Tasmota Command** | All | Send any Tasmota command. Free-form text e.g. `Power TOGGLE`, `Dimmer 50`, `Backlog Power ON; Delay 100; Dimmer 75`. |
| **Set HSB Color** | tasmotaLight | Set hue (0–360), saturation (0–100), brightness (0–100). |
| **Set Colour Temperature** | tasmotaLight | Set colour temperature in mireds (153 = cool ~6500K, 500 = warm ~2000K). |
| **Open Shutter** | tasmotaShutter | Publish `ShutterOpen<n>`. |
| **Close Shutter** | tasmotaShutter | Publish `ShutterClose<n>`. |
| **Stop Shutter** | tasmotaShutter | Publish `ShutterStop<n>`. |
| **Request Status Update** | All | Publish `Status 0` — device republishes full status to MQTT. |
| **Open Tasmota Web UI** | All | Opens `http://<ip>/` in the default browser on the Indigo Mac. |
| **Open Firmware Upgrade Page** | All | Opens `http://<ip>/up` in the default browser on the Indigo Mac. |
| **Upgrade Firmware (one-click)** | All | Auto-detects ESP architecture, sets OTA URL, triggers `Upgrade 1`. Device reboots and reflashes. |
| **Reboot Device** | All | Publishes `Restart 1`. Device reboots within a second; reconnects to MQTT in ~5–10s. |

---

## Custom Events (Triggers)

Available via `Triggers → New Trigger`.

### Tasmota Device Came Online

Fires when a device's LWT changes to `Online`.

**Filter fields:**
- **MAC Address** — leave blank to match any Tasmota device

### Tasmota Device Went Offline

Fires when a device's LWT changes to `Offline`, OR when no telemetry
has been received for 10 minutes (offline watchdog).

**Filter fields:**
- **MAC Address** — leave blank to match any Tasmota device

### New Tasmota Device Discovered

Fires when a previously-unseen MAC publishes a discovery config payload
for the first time. Useful for "send me a notification when a new
Tasmota device joins the network" automations.

### Tasmota Button Pressed

Fires when a `Button<n>` event arrives in a `stat/<topic>/RESULT` payload.

**Filter fields:**
- **MAC Address** — leave blank to match any device
- **Button Number** — 1–8, blank for any
- **Action** — `SINGLE` / `DOUBLE` / `TRIPLE` / `QUAD` / `PENTA` /
  `HOLD` / `CLEAR`, or blank for any

The trigger filter is OR-less — all populated fields must match.

---

## Plugin Menu Items

Available under `Plugins → Tasmota Bridge`:

| Menu item | Purpose |
|---|---|
| **Discover Tasmota Devices** | Re-subscribe to the discovery topic; retained discovery messages replay. Use this if a device seems missing. |
| **List Seen Devices** | Print a one-line summary of every discovered device to the event log. |
| **Dump Discovery Cache to Log** | Print the full JSON discovery cache. Verbose; for debugging. |
| **Upgrade Tasmota Firmware...** | Picker dialog. Auto-detects ESP architecture, sets OTA URL, triggers upgrade. |
| **Open Tasmota Device Web UI...** | Picker dialog. Opens the chosen device's main web page in the default browser on the Indigo Mac. |
| **Show Plugin Info** | Re-print the startup banner with current MQTT broker, connection status, and device counts. |

---

## Firmware Management

On every plugin start, ~15 seconds after MQTT connects:

1. The plugin queries
   `https://api.github.com/repos/arendst/Tasmota/releases/latest` to find
   the current Tasmota release (cached for 24h to be polite to the API).
2. Each known device's installed firmware (from the discovery payload's
   `sw` field) is compared against the latest release.
3. The device's `firmwareStatus` state is written:
   - `up-to-date`
   - `update available: <version>`
   - `unknown` (rare)
4. A concise summary is logged:
   ```
   All 2 Tasmota devices on latest firmware (15.4.0).
   ```
   or
   ```
   1 Tasmota device has updates available:
     Kitchen Extractor Power Switch  (15.0.1 -> 15.4.0)
   Use 'Plugins -> Tasmota Bridge -> Open Tasmota Device Page...' to open each device's firmware page.
   ```

The latest Tasmota release version is also surfaced in the startup
banner extras (`Latest Tasmota: 15.4.0`).

### One-click upgrade

`Plugins → Tasmota Bridge → Upgrade Tasmota Firmware...` opens a picker
showing each Tasmota device with its current `firmwareStatus`. Pick a
device, click **Upgrade**:

1. Plugin probes the device's `Status 2` over HTTP, reads
   `StatusFWR.Hardware` (e.g. `ESP8285H16`).
2. Picks the matching official Tasmota OTA URL:
   - ESP8266/8285 → `http://ota.tasmota.com/tasmota/release/tasmota.bin.gz`
   - ESP32 → `http://ota.tasmota.com/tasmota32/release/tasmota32.bin.gz`
3. Publishes `cmnd/<topic>/Backlog OtaUrl <url>; Upgrade 1` via MQTT.
4. Device reboots, downloads firmware (~600 KB), reflashes, reconnects.
5. ~30–60s later it republishes discovery; plugin auto-refreshes the
   `firmware` prop and `firmwareStatus` state.

The detected architecture is cached in the device's `pluginProps['arch']`
so subsequent upgrades skip the HTTP probe.

---

## How Discovery Works

Tasmota firmware 11+ publishes two retained MQTT topics on every boot:

```
tasmota/discovery/<MAC>/config    — device capabilities (relays, lights, sensors, etc.)
tasmota/discovery/<MAC>/sensors   — current sensor readings
```

Both arrive back-to-back when the plugin subscribes to
`tasmota/discovery/#`. The plugin waits for **both** before classifying
the device type (so it can tell a plain `tasmotaRelay` apart from a
`tasmotaEnergyPlug` — the distinction lives in the sensors payload).

`SetOption147` controls discovery on the device side. Default is OFF
(yes, "OFF" means enabled — Tasmota's flag is named in reverse). If you
ever need to force a device to republish its discovery, run from its
Console:

```
SetOption147 1
SetOption147 0
```

Toggling resets the retained message, so the plugin sees it as new on
its next subscribe.

---

## Dynamic Sensor Capture

`tasmotaSensor` devices use a **dynamic state declaration** pattern
inherited from CliveS's
[Zigbee2MQTTBridge](https://github.com/Highsteads/Zigbee2MQTTBridge):
the plugin doesn't need to know about every sensor type. Instead, on
every `tele/<topic>/SENSOR` message, it scans for named sensor blocks
and turns each field into a custom Indigo state automatically.

### Naming rule

Sensor names and field names get camelCased into Indigo state IDs:
- `BME280.Temperature` → `bme280Temperature`
- `BME280.Pressure` → `bme280Pressure`
- `BME280.DewPoint` → `bme280DewPoint`
- `DS18B20-1.Temperature` → `ds18b201Temperature`
- `AM2301.Humidity` → `am2301Humidity`

Indigo state IDs must be ASCII camelCase with no underscores or hyphens
(an Indigo rule, not ours) — the plugin sanitises automatically.

### Declare-before-write

The first SENSOR message that introduces a new sensor field would
otherwise lose its value (write fails with "state not defined", the
state list updates, but the value is never retried). The plugin
handles this by pre-scanning the payload for unknown state IDs,
declaring them all via `stateListOrDisplayStateIdChanged()`, then
writing values. Result: **first-message values land correctly**.

### Filtered fields

These top-level keys in the SENSOR payload are NOT treated as sensor
blocks: `Time`, `TempUnit`, `PressureUnit`, `ENERGY` (ENERGY has its
own dedicated state mapping).

Inside each sensor block, `Id` and `Type` fields are skipped (they're
identifiers, not measurements).

---

## Architecture Overview

```
+--------------------+    MQTT (paho-mqtt)    +-----------------------+
| Tasmota devices    | <----- discovery ----- |                       |
| (on LAN, any IP)   |                        |   TasmotaBridge       |
|                    | -----  telemetry ----> |   Indigo plugin       |
|                    | <----  commands  ----- |                       |
+--------------------+                        +-----------+-----------+
                                                          |
                                                          | Indigo IOM
                                                          v
                                              +-----------------------+
                                              |  Indigo Server        |
                                              |  - devices            |
                                              |  - states / triggers  |
                                              |  - actions            |
                                              +-----------------------+
```

- **Single paho-mqtt client**, persistent connection to the broker.
- Subscribed topics: `tasmota/discovery/#`, `tele/#`, `stat/#`.
- Discovery cache lives in memory keyed by MAC.
- Auto-create devices into a `Tasmota` folder (folder is the user's
  choice once moved — plugin never touches `folderId` after creation).
- `runConcurrentThread` runs an LWT-timeout watchdog every 30 seconds
  and triggers the one-shot startup firmware check ~15s after start.

For implementation details, browse
[plugin.py](TasmotaBridge.indigoPlugin/Contents/Server%20Plugin/plugin.py)
— the file is documented with comments at each major code section.

---

## Troubleshooting

### A new Tasmota device hasn't appeared in Indigo

1. **Check MQTT is configured on the device.** Open the device's web UI
   (e.g. `http://192.168.4.144`) → Configuration → Configure MQTT.
   Confirm Host points at your Mosquitto broker and credentials are
   correct.
2. **Check discovery is enabled.** From the device's Console:
   `SetOption147` should return `OFF` (means enabled — Tasmota's flag
   is named in reverse). If it says `ON`, run `SetOption147 0`.
3. **Check the broker received it.** From any machine with `mosquitto_sub`:
   ```
   mosquitto_sub -h <broker-ip> -u <user> -P <pass> -v -t 'tasmota/discovery/#'
   ```
   You should see the device's `config` and `sensors` topics replay
   immediately (they are retained).
4. **Force a republish.** From the device's Console:
   `SetOption147 1; SetOption147 0` (toggle off then on). Or use the
   plugin's `Plugins → Tasmota Bridge → Discover Tasmota Devices` menu —
   it re-subscribes to the discovery topic and pulls retained messages
   again.
5. **Check the plugin log.** `Plugins → Tasmota Bridge → Show Plugin Info`
   prints connection status and device counts.

### Device appears but states aren't updating

Check the event log for messages like
`device "X" state key Y not defined (ignoring update request)`.

If you see these, the device is publishing a key the plugin doesn't
yet know about. For sensor devices this should auto-resolve after the
second telemetry cycle (see [Dynamic Sensor Capture](#dynamic-sensor-capture)).
If it persists, file an issue with the payload.

### Multi-relay device only has one channel

Check the discovery config payload via `Plugins → Tasmota Bridge →
Dump Discovery Cache to Log`. Look for the `rl` array in your device's
entry. If it shows `[1,0,0,0,...]` but you expect more channels, your
device is currently configured as a single-relay device in Tasmota
(Configure Module / Template settings).

### Firmware upgrade gets stuck on the upload screen

Tasmota's OTA mechanism downloads from the URL listed in the device's
OTA Url field. If that URL is unreachable (e.g. an old MQTT server's
firmware-hosting path that no longer exists), the upgrade silently
fails. The plugin's **Upgrade Firmware** menu overrides OTA URL to the
official `ota.tasmota.com` URL before triggering upgrade, so this
shouldn't happen with the one-click path.

If you see the upload screen hang, check the device's Console for OTA
log lines.

### Factory-default device (broadcasting its own Wi-Fi)

Plugin can't see these — they're not on your LAN. Onboard via the
device's captive portal first:

1. Connect your phone/laptop to the device's `tasmota_XXXXXX-1234` SSID
2. Open `http://192.168.4.1`
3. Enter your real Wi-Fi credentials AND your MQTT broker details on
   the same page
4. Save — device reboots, joins your Wi-Fi, plugin picks it up

---

## FAQ

**Q: Does this plugin require Zigbee2MQTT or any other software?**
A: No. It only needs an MQTT broker (Mosquitto recommended, but any
MQTT 3.1.1+ broker works). The Mosquitto that ships natively on the
SMLight Hub is a great no-extra-hardware option.

**Q: Can I use a different MQTT broker per device?**
A: No, the plugin connects to a single broker. All Tasmota devices
must point at the same broker.

**Q: Does the plugin work over a remote Indigo client (iPad, reflector,
remote Mac)?**
A: Yes for everything except the `Open Tasmota Device Web UI` / `Open
Firmware Upgrade Page` actions. Those open a browser tab on the
Indigo Mac (where the plugin runs), not on the viewing client. Use
`mosquitto_pub` from the remote machine or open the device's IP
directly if you need browser access on a remote client.

**Q: What happens if the broker goes down?**
A: paho-mqtt automatically reconnects. Device commands queued during
the outage are lost; sensor readings during the outage are also lost.
Once the broker comes back, retained discovery and LWT messages
replay so the plugin re-syncs.

**Q: How do I rename a device?**
A: Edit the device in Indigo (`Edit` button or double-click). Renames
in Indigo don't affect the Tasmota device's own name. To rename the
Tasmota device itself, use its web UI: Configuration → Configure
Other → Friendly Name 1.

**Q: I moved a device from the `Tasmota` folder to a room folder. Will
the plugin move it back?**
A: No. The plugin only assigns folder at initial device creation. After
that, the folder is your choice and the plugin never touches it.

**Q: Why does the plugin not have a "Scan Network for Tasmota Devices"
menu?**
A: Earlier beta builds had one, but it was removed in v0.3.0. The
plugin only works with devices that are on MQTT anyway — if a device
isn't on MQTT, the plugin can't use it regardless of whether we found
it via HTTP scan. The scan was solving a non-problem and added ~150
lines of code (threading, subnet detection, dialog, etc.) for
negligible value.

**Q: My device has both buttons and relays (e.g. Sonoff Basic). What
type does it become?**
A: It becomes the relay/energy type, since that's the primary
function. The button presses still fire `Tasmota Button Pressed`
triggers correctly — the button events are routed by MAC, not by
device type.

---

## Beta Tester Checklist

If you have hardware in any of the 🟡 categories from the Status
section, here's what would help most:

1. **Multi-relay devices** (Sonoff 4CH, dual-channel plugs):
   - Confirm 4 (or N) Indigo devices are auto-created
   - Confirm each channel's `Turn On / Turn Off` controls the right relay
   - Confirm all channels go offline together when the physical device is
     powered down

2. **Environmental sensors** (DS18B20, BME280, AM2301, DHT22):
   - Confirm sensor states appear under the right camelCased names
   - Confirm values update on the first telemetry message (not just the
     second — declare-before-write fix)
   - Report any sensor field names that don't parse cleanly

3. **Wall switches / scene controllers**:
   - Create a `Tasmota Button Pressed` trigger with no filter
   - Press each button single / double / hold, confirm the trigger
     fires with the right action
   - Confirm `lastButton` / `lastAction` / `pressCount` states update
     correctly

4. **Dimmer / RGB / CT lights**:
   - Confirm Indigo's native brightness slider sets the right level
   - Test the `Set HSB Color` and `Set Colour Temperature` actions
   - Report any colour mode mismatches

5. **Shutters / blinds**:
   - Confirm Indigo's brightness slider sets the shutter position
   - Test the Open / Close / Stop actions
   - Confirm the `direction` state reflects movement

File reports at <https://github.com/Highsteads/TasmotaBridge/issues>
with the device model, firmware version, and the discovery payload
(use `Plugins → Tasmota Bridge → Dump Discovery Cache to Log`).

---

## Contributing

Pull requests welcome at
<https://github.com/Highsteads/TasmotaBridge>.

Code conventions:
- Python 3.13 (Indigo 2025.2 embedded)
- 4-space indent, no tabs
- snake_case for vars/functions, PascalCase for classes,
  UPPER_SNAKE for constants
- Custom `log()` helper, not `print()` or `indigo.server.log()` directly
- Maximum error checking — never assume success
- `try` / `except` around dynamic-state writes (Indigo can reject)

When adding a new device type, also update:
- `Contents/Server Plugin/Devices.xml` — define the device
- `Contents/Server Plugin/plugin.py` — add detection logic to
  `_detect_device_type` and handler logic
- `README.md` — add a section to [Supported Device Types](#supported-device-types)
- The README's [Beta Tester Checklist](#beta-tester-checklist) if the
  device class is untested

---

## Logging

Every log line is prefixed with a millisecond timestamp `[HH:MM:SS.mmm]` so
events can be correlated tightly with other CliveS plugins (Device Activity
Monitor uses the same convention).

To turn the prefix off (or back on) at any time:

**Plugins → Tasmota Bridge → Toggle Timestamps in Log (on/off)**

The setting is stored in `pluginPrefs` (`timestampEnabled`) and persists across
restarts. Defaults to ON.

---

## License

MIT. See `LICENSE` (forthcoming — pending v1.0).
