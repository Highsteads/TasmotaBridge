---
title: Version history
nav_order: 10
---

# Version history

The newest version is at the top.

## 0.7.9 — 21 September 2026

The list of which device types are relays was written out in three places in the plugin, and now it is written once, with a check that it agrees with the device definitions. The example addresses in the device settings help are now made-up values. Nothing about how the plugin behaves has changed.

## 0.7.8 — 11 September 2026

The plugin carries a note of where its code lives on GitHub in the same form as other Indigo plugins. Nothing else changed.

## 0.7.7 — 8 August 2026

- The **About** item in the Plugins menu opens this project's page. It went nowhere before.
- The plugin comes with `IndigoSecrets_example.py`, the blank copy of the shared settings file that the [Settings](settings.md) page tells you to copy.

## 0.7.6 — 10 June 2026

A tidy-up of the plugin's code with no change to how it behaves.

## 0.7.5 — 5 June 2026

- **Send Status Request** on a sensor or button device no longer logs an error.
- A **Broker Port** that is not a number no longer stops the plugin from starting, and the colour actions cope with an empty box.

## 0.7.4 — 25 May 2026

A device only restarts its connection when you change a setting that decides which messages belong to it — its topic, relay channel or shutter index — and not when the plugin updates its model, firmware or network address.

## 0.7.3 — 23 May 2026

Every log line starts with the time to the thousandth of a second, with a menu item to turn that off.

## 0.7.2 — 20 May 2026

Lights and shutters answer Indigo's brightness controls. Before, the brightness slider did nothing on a light. A shutter also answers **Turn On** and **Turn Off** by opening and closing fully.

## 0.7.1 — 19 May 2026

The first public beta.

- Every Indigo device belonging to a board with several relays goes offline and comes back together.
- A sensor device's MAC address no longer has a stray **-0** on the end.
- The first reading from a new sensor is kept. Before, it was lost and only the second one appeared.

## 0.7.0 — 19 May 2026

- Boards with several relays become one Indigo device per relay.
- Sensor devices record every reading the device sends, whatever the sensor.
- A new **Tasmota Button** device type and **Tasmota Button Pressed** trigger.
- A new **Reboot Device** action, and a `restartReason` state on every device.

## 0.6.0 to 0.6.2 — 19 May 2026

- **Upgrade Tasmota Firmware...** in the Plugins menu, and an **Upgrade Firmware (one-click)** action, upgrade a device to the latest official firmware.
- **Open Tasmota Device Web UI...** opens a device's own web page straight away, without asking which page.
- The upgrade no longer asks you to tick a box to confirm.

## 0.5.0 and 0.5.1 — 19 May 2026

Each device has a `firmwareStatus` state, filled in when the plugin starts, and the Event Log has a short list of devices with a newer firmware available. The **Check Firmware Updates** menu item went, because the check now runs by itself.

## 0.4 — 19 May 2026

The plugin checks each device's firmware against the latest Tasmota release when it starts.

## 0.3.0 — 19 May 2026

The **Scan Network for Tasmota Devices** menu item went. The plugin can only use devices that talk to the broker, and those announce themselves, so the scan found nothing it could use.

## 0.2.0 to 0.2.3 — 19 May 2026

- New devices go in a folder called **Tasmota**.
- Each device's line in the device list shows its network address and model.
- A **Scan Network for Tasmota Devices** menu item, removed again in 0.3.0.

## 0.1.0 — 19 May 2026

The first version: devices found through the broker, energy-monitoring plugs with their readings, switching on and off, online and offline tracking, the plugin's own actions and triggers, and the broker details read from `IndigoSecrets.py`.
