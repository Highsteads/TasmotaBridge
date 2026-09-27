---
title: Getting started
nav_order: 2
---

# Getting started

## What you need

- Indigo 2025.2 or later.
- An **MQTT broker** running somewhere on your home network — Mosquitto is the usual one, and it can run on the Mac that runs Indigo. You need its **network address** (the four numbers separated by dots, such as `192.168.1.20`), its port number, which is 1883 unless someone has changed it, and the user name and password if it asks for one.
- One or more Tasmota devices already joined to your Wi-Fi.

A brand-new Tasmota device that has never been set up puts out its own Wi-Fi network instead of joining yours. Join that network with your phone or laptop, open `http://192.168.4.1`, and give it your Wi-Fi details there. The plugin cannot see a device until it is on your network and talking to the broker.

## 1. Install the plugin

1. Go to the [Releases page](https://github.com/Highsteads/TasmotaBridge/releases/latest) and download `TasmotaBridge.indigoPlugin.zip`
2. Unzip the downloaded file — you will get `TasmotaBridge.indigoPlugin`
3. Double-click `TasmotaBridge.indigoPlugin` — Indigo will install it automatically

Indigo asks whether to enable the plugin. Say yes. The first time it starts, Indigo fetches the one extra piece of software the plugin needs, paho-mqtt, which it uses to talk to the broker.

## 2. Tell the plugin where the broker is

Open **Plugins → Tasmota Bridge → Configure**.

Fill in **Broker Host** with the broker's network address, check **Broker Port**, and fill in **Username** and **Password** if your broker has them. Leave everything else as it is to start with, and click **Save**. Every setting is explained on the [Settings](settings.md) page, including how to keep the broker details in a shared file instead.

## 3. Point each Tasmota device at the same broker

On each Tasmota device, open its own web page by typing its network address into a browser, then:

1. Choose **Configuration → Configure MQTT**.
2. Set **Host** to the broker's network address, and **Port**, **User** and **Password** to match the broker.
3. Give it a **Topic** — any short name that no other device uses, such as `kitchen_plug`. The device sends its messages under this name.
4. Leave **Full Topic** as it is.
5. Click **Save**. The device restarts.

## 4. Check it works

When the device comes back, it announces itself to the broker, and within a few seconds the Indigo Event Log has a line saying the plugin has discovered it, then another saying it has created the Indigo device. The new device appears in a device folder called **Tasmota**, named with the name the device gave itself, and its line in the device list shows its network address and model.

Switch it from Indigo, and then with its own button if it has one. Indigo should show each change.

The device is now yours to rename or move to another folder, and the plugin leaves the name and folder as you set them.

If nothing appears, the [When something goes wrong](troubleshooting.md) page goes through the usual causes.
