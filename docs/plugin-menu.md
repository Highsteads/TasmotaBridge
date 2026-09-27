---
title: The plugin menu
nav_order: 7
---

# The plugin menu

These are under **Plugins → Tasmota Bridge**.

| Menu item | What it does |
|---|---|
| **Discover Tasmota Devices** | Asks the broker to hand over every device's description again, so the plugin looks at each device afresh and creates any Indigo device that is missing. Use it if a device you expect has not appeared. |
| **List Seen Devices** | Writes one line to the Event Log for each Tasmota device the plugin has heard from since it started, with its MAC address, name, model, firmware version and sensors. |
| **Dump Discovery Cache to Log** | Writes everything each device has said about itself to the Event Log, in full. It is long, and mainly useful to include when you report a problem with a device. |
| **Upgrade Tasmota Firmware...** | Opens a box listing each Tasmota device with its firmware status beside it. Pick one and click **Upgrade**, and the plugin upgrades it to the latest official Tasmota firmware. A board with several relays is listed once. The [Firmware updates](firmware.md) page explains what happens. |
| **Open Tasmota Device Web UI...** | Opens a box listing each Tasmota device. Pick one and click **Open**, and its own web page opens in the web browser on the Mac that runs Indigo. |
| **Toggle Timestamps in Log (on/off)** | Every line the plugin writes to the log starts with the time to the thousandth of a second, which helps when lining events up. This turns that on or off. It stays as you leave it. |
| **Show Plugin Info** | Writes the plugin's version, details of your Mac and Indigo, the broker it uses, whether it is connected, and how many devices it has found, to the log. It is useful to include if you ask for help on the Indigo forum. |
