---
title: Home
nav_order: 1
---

# Tasmota Bridge for Indigo

This plugin brings devices that run [Tasmota](https://tasmota.github.io/docs/) into [Indigo](https://www.indigodomo.com) as ordinary Indigo devices. Tasmota is free firmware — the software inside a device — that many people put on Wi-Fi plugs, switches, bulbs and sensors in place of the maker's own, so the device works on the home network with no cloud account.

Tasmota devices pass their messages through a program on your network called an **MQTT broker**, which is a post office for messages: each device sends its readings to the broker, and anything that wants them, Indigo included, collects them from there. The plugin talks to the broker and never to the internet, apart from one check for new Tasmota firmware each time it starts.

**This is a beta.** I tested switching and the energy readings on two Athom plugs. The lights, sensors, buttons, shutters and boards with more than one relay pass the plugin's own tests but have not yet been tried on real hardware, so a report from anyone who has one is very welcome.

## What it does for you

- **Finds your Tasmota devices by itself.** Each Tasmota device announces what it is to the broker, and the plugin creates the matching Indigo device in a folder called **Tasmota**, with no typing on your part.
- **Switches plugs and relays** from Indigo, a control page, a schedule or a trigger, the same as any other Indigo device, and shows the change as soon as the device reports it, however it was switched.
- **Reads energy-monitoring plugs** — the power being drawn now, the running total, today's and yesterday's use, the voltage and more.
- **Dims lights and sets their colour**, and moves blinds and shutters to a position.
- **Records every reading from a sensor**, such as a temperature probe, even ones the plugin has never been told about.
- **Tells you when a device goes offline** and can run a trigger when it does, or when it comes back.
- **Checks each device's firmware** against the latest Tasmota release when the plugin starts, and can upgrade a device for you.

## Where to go next

| If you want to... | Read |
|---|---|
| Install the plugin and see your first device | [Getting started](getting-started.md) |
| Know what each device shows in Indigo | [Your devices](devices.md) |
| Understand what the plugin is doing behind the scenes | [How it works](how-it-works.md) |
| Switch things from triggers, schedules and action groups | [Actions and triggers](actions-and-triggers.md) |
| Know what every setting does | [Settings](settings.md) |
| Know what each item in the Plugins menu does | [The plugin menu](plugin-menu.md) |
| Keep your devices' firmware up to date | [Firmware updates](firmware.md) |
| Sort out a problem | [When something goes wrong](troubleshooting.md) |
| See what changed in each version | [Version history](changelog.md) |

## Download

The latest version is always on the [Releases page](https://github.com/Highsteads/TasmotaBridge/releases/latest).
