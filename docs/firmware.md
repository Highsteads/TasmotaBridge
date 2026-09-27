---
title: Firmware updates
nav_order: 8
---

# Firmware updates

## Checking for new firmware

Each time the plugin starts, it asks GitHub, where Tasmota is published, for the number of the latest Tasmota release. About 15 seconds after starting, it compares the firmware of each Tasmota device in Indigo with that release and sets the device's `firmwareStatus` state to one of:

| Firmware status | What it means |
|---|---|
| **up-to-date** | The device runs the latest release, or a later one. |
| **update available:** followed by a version | A newer release is out, and the version shown is the one it would get. |
| **unknown** | The plugin could not read the device's firmware version. |

If any device is behind, the Event Log lists each one with the version it runs and the version it could have. If all are current, the log has one line saying so. The list ends by pointing you to **Upgrade Tasmota Firmware...**, which does the upgrade for you, as below.

The check runs once each time the plugin starts. If Indigo has no Tasmota devices a minute after the plugin starts, it skips the check until the next start.

## Upgrading a device

Choose **Plugins → Tasmota Bridge → Upgrade Tasmota Firmware...**, pick the device and click **Upgrade**. There is also an **Upgrade Firmware (one-click)** action for use in an action group.

The plugin then:

1. Asks the device over your network which chip it is built on. Tasmota runs on two families of chip, the older ESP8266 and the ESP32, and the ESP32 comes in several kinds — the original, and newer ones such as the ESP32-C3 and ESP32-S3. Each needs its own firmware. The plugin remembers the answer, so it only asks once.
2. Tells the device to fetch the matching official release from Tasmota's own download site and install it.

The device restarts, installs the new firmware, and is back on the broker within a minute or so. Its **Firmware** setting shows the new version once it announces itself again, and its firmware status catches up the next time the plugin starts.

The plugin knows the right firmware for the ESP8266, the original ESP32 (with its single-core version), and the ESP32-S2, S3, C2, C3 and C6. If the device does not answer the question about its chip, or has a chip the plugin does not know, the plugin does not upgrade it, and says so in the Event Log. You can still upgrade it from its own page, using the **Open Firmware Upgrade Page** action.
