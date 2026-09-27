# Tasmota Bridge for Indigo

**Brings your Tasmota plugs, switches, lights and sensors into Indigo, through your own MQTT broker.**

**Version:** 0.8.0 | **Author:** CliveS & Claude | **Needs:** Indigo 2025.2 or later, and an MQTT broker on your network

**[Read the full guide](https://highsteads.github.io/TasmotaBridge/)** — setting up, what everything means, and what to do when something goes wrong.

---

## What it does

This plugin lets [Indigo](https://www.indigodomo.com) control devices that run [Tasmota](https://tasmota.github.io/docs/), the free firmware many people put on Wi-Fi plugs, switches and bulbs in place of the maker's own. The devices and the plugin pass their messages through an **MQTT broker** on your home network, such as Mosquitto, so there is no cloud account involved.

- **Finds your devices by itself.** Each Tasmota device announces what it is to the broker, and the plugin creates the matching Indigo device in a folder called **Tasmota**.
- **Switches plugs and relays** from Indigo, a control page, a schedule or a trigger, and shows the change as soon as the device reports it, however it was switched.
- **Reads energy-monitoring plugs** — the power being drawn now, today's and yesterday's use, the running total, the voltage and more.
- **Dims lights and sets their colour**, and moves blinds and shutters to a position.
- **Records every reading from a sensor**, even from sensors the plugin has never been told about.
- **Makes one Indigo device per relay** on a board with several relays.
- **Tells you when a device goes offline**, and can run a trigger when it does or when it comes back.
- **Checks each device's firmware** against the latest Tasmota release when the plugin starts, and can upgrade a device for you.

**This is a beta.** I tested switching and the energy readings on two Athom plugs. The lights, sensors, buttons, shutters and boards with more than one relay pass the plugin's own tests but have not yet been tried on real hardware, so reports from anyone who has one are very welcome on the [issues page](https://github.com/Highsteads/TasmotaBridge/issues).

## What it works with

Any device running Tasmota that is connected to the same MQTT broker as the plugin. The plugin picks the Indigo device type from what the device reports:

| In Indigo | Your device |
|---|---|
| **Tasmota Relay** | A plug, switch or relay, such as a Sonoff Basic |
| **Tasmota Energy Plug** | A plug or relay that measures power, such as an Athom plug or a Sonoff POW |
| **Tasmota Light** | A dimmer, bulb or LED strip, white or colour |
| **Tasmota Sensor** | A device with sensors only, such as a temperature probe |
| **Tasmota Button** | A device with buttons only, such as a wall switch with no relay |
| **Tasmota Shutter** | A blind, curtain or roller shutter controller |

## Installing

1. Go to the [Releases page](https://github.com/Highsteads/TasmotaBridge/releases/latest) and download `TasmotaBridge.indigoPlugin.zip`
2. Unzip the downloaded file — you will get `TasmotaBridge.indigoPlugin`
3. Double-click `TasmotaBridge.indigoPlugin` — Indigo will install it automatically

## Setting it up

1. Open **Plugins → Tasmota Bridge → Configure**, fill in **Broker Host** with your broker's network address — the four numbers, such as `192.168.1.20` — and the **Username** and **Password** if your broker has them, and click **Save**.
2. On each Tasmota device's own web page, choose **Configuration → Configure MQTT**, point it at the same broker, give it a **Topic** no other device uses, and click **Save**.
3. When the device restarts, it appears in Indigo's **Tasmota** folder within a few seconds.

The [full guide](https://highsteads.github.io/TasmotaBridge/) goes through each step, explains every setting, and covers what to do if something does not work.

## What's new

**v0.8.0** — Button presses, **Request Status Update**, the colour mode of a light and every **Log Level** choice now work, a change to any broker setting reconnects straight away, and each kind of ESP32 chip gets its own firmware. A setting that never did anything has gone.

**v0.7.9** — The list of which device types are relays is written once inside the plugin, with a check that it agrees with the device definitions. The example addresses in the device settings help are now made-up values. Nothing about how the plugin behaves has changed.

Every version is listed in the [version history](https://highsteads.github.io/TasmotaBridge/changelog.html).

## Authors & licence

Vibed into existence by **CliveS**, who knew what he wanted, argued until he got it, and tested it on a real house. Typed at inhuman speed by **Claude** (Anthropic), who mostly did as it was told.

© 2026 CliveS · [MIT licence](LICENSE) — copy it, fork it, bend it, break it, fix it, ship it. If it breaks, you get to keep both pieces.
