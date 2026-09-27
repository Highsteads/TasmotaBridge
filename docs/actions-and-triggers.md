---
title: Actions and triggers
nav_order: 5
---

# Actions and triggers

## Switching, dimming and moving

Relays, energy plugs and lights answer Indigo's standard **Turn On**, **Turn Off** and **Toggle**, wherever you use them — a control page, a schedule, a trigger or an action group. Lights also answer **Set Brightness**, **Brighten By** and **Dim By**.

A shutter answers **Turn On** by opening fully, **Turn Off** by closing fully, and **Set Brightness**, **Brighten By** and **Dim By** by moving to that position, where 0% is closed and 100% open.

## The plugin's own actions

Add an action, choose **Tasmota Bridge** and then the action from the list of action types, and pick the device.

| Action | For | What it does |
|---|---|---|
| **Send Raw Tasmota Command** | Any device | Sends the device any Tasmota command you type, such as `Power TOGGLE`, `Dimmer 50` or `Backlog Power ON; Delay 100; Dimmer 75`. The first word is the command and the rest is its value. Tasmota's own [list of commands](https://tasmota.github.io/docs/Commands/) says what each one does. |
| **Set HSB Color** | Lights | Sets the colour by **Hue** (0 to 360, the position round the colour wheel), **Saturation** (0 to 100, how strong the colour is) and **Brightness** (0 to 100). |
| **Set Colour Temperature** | Lights | Sets the shade of white in **Mireds**, from 153 for the coolest, bluest white to 500 for the warmest. It starts at 300. |
| **Open Shutter** | Shutters | Opens the shutter fully. |
| **Close Shutter** | Shutters | Closes the shutter fully. |
| **Stop Shutter** | Shutters | Stops the shutter where it is. |
| **Request Status Update** | Any device | Asks the device to send its full status to the broker. This version of the plugin does not read that reply, so to bring a device's readings up to date straight away, use **Send Raw Tasmota Command** with `TelePeriod` instead, which makes the device send its regular report now. |
| **Open Tasmota Web UI** | Any device | Opens the device's own web page in the web browser **on the Mac that runs Indigo**, not on the screen you are using if that is somewhere else. |
| **Open Firmware Upgrade Page** | Any device | Opens the device's firmware upgrade page, in the same way. |
| **Upgrade Firmware (one-click)** | Any device | Upgrades the device to the latest official Tasmota firmware, as the [Firmware updates](firmware.md) page explains. The device restarts and is away for a minute or so. |
| **Reboot Device** | Any device | Restarts the device. It is back on the broker within a few seconds. |

The two web page actions and the firmware upgrade need the device's network address, which the plugin fills in by itself when it finds the device.

## Triggers

Create a new trigger and set its type to **Tasmota Bridge**, then choose one of these.

| Trigger | When it runs |
|---|---|
| **Tasmota Device Came Online** | A Tasmota device that has an Indigo device connects to the broker. |
| **Tasmota Device Went Offline** | A Tasmota device that has an Indigo device drops off the broker, or the plugin has heard nothing from it for 10 minutes. |
| **New Tasmota Device Discovered** | The plugin hears from a Tasmota device that does not yet have an Indigo device. |
| **Tasmota Button Pressed** | A button is pressed on a Tasmota device that has an Indigo device. |

**Came Online** and **Went Offline** have one box, **MAC Address**. Leave it empty to react to any Tasmota device, or type in one device's MAC address to react to that one only. The MAC address is on the device's own web page under **Information**, and in its Indigo device settings. You can type it with or without the colons.

The broker keeps each device's last online or offline announcement, and hands them all to the plugin when it starts, so these two triggers also run for each device when the plugin starts or reconnects.

**Tasmota Button Pressed** has three boxes, and a press has to match every one you fill in:

- **MAC Address** — empty for any device, or one device's MAC address.
- **Button Number** — empty for any button, or a number from 1 to 8.
- **Action** — **Any action**, or one kind of press: **Single press**, **Double press**, **Triple press**, **Quadruple press**, **Quintuple press**, **Long hold** or **Released**.

It also runs for a button on a plug or switch, not only on a Tasmota Button device.
