---
title: When something goes wrong
nav_order: 9
---

# When something goes wrong

Each section starts with what you see, then what it means and what to do.

## The log says "No MQTT broker configured"

The plugin does not know where your broker is. Fill in **Broker Host** in **Plugins → Tasmota Bridge → Configure**, or `MQTT_BROKER` in your `IndigoSecrets.py` file, as the [Settings](settings.md) page explains.

## The log says "MQTT connect failed"

The plugin reached the broker, but the broker refused it. The usual cause is a wrong **Username** or **Password**. Check them against the broker's own settings and click **Save**. The plugin reconnects straight away.

## The log says "MQTT disconnected (will auto-reconnect)"

The connection to the broker dropped — the broker restarted, say, or the network blinked. The plugin reconnects by itself and writes "MQTT connected" when it has. Anything you switched while it was disconnected was not sent, and the log says so for each one, so switch it again.

## A Tasmota device has not appeared in Indigo

- Choose **Plugins → Tasmota Bridge → Show Plugin Info** and check the log says **MQTT Connected: yes**.
- Choose **List Seen Devices**. If the device is listed, the plugin has heard from it — check **Auto-create Indigo devices on discovery** is ticked in **Configure**, then choose **Discover Tasmota Devices**.
- If it is not listed, the device is not reaching the broker. Open the device's own web page, choose **Configuration → Configure MQTT**, and check **Host**, **Port**, **User** and **Password** match your broker.
- Restart the device, with its power or with **Restart** on its own web page. It announces itself to the broker each time it starts.

## A device has its own Wi-Fi network instead of joining yours

It has not been set up yet. Join its network with your phone or laptop, open `http://192.168.4.1`, and give it your Wi-Fi details. Once it is on your network, point it at your broker as the [Getting started](getting-started.md) page describes.

## A device shows "Offline"

The device has dropped off the broker, or the plugin has heard nothing from it for 10 minutes.

- Check it has power, and that it shows on your router's list of connected devices.
- Open its own web page. If that works, check its **Configure MQTT** page as above.

When it connects again, it shows **Online** by itself.

## A board with several relays has only one device in Indigo

The plugin makes one Indigo device for each relay the device says it has. Choose **Dump Discovery Cache to Log** and find the device's entry. If it shows only one relay, the device itself is set up as a single relay, which is changed in Tasmota's **Configure Module** or **Configure Template** page, not in Indigo.

## A device's readings are out of date

Tasmota sends its regular report every five minutes unless you have changed its **TelePeriod** setting. To bring a device up to date straight away, use the **Request Status Update** action.

## The log says a state is "not defined"

The device has sent a reading the plugin had not seen before. For a sensor reading the plugin adds the state by itself, and the message stops. If it carries on for the same state, [raise an issue on GitHub](https://github.com/Highsteads/TasmotaBridge/issues) with the output of **Dump Discovery Cache to Log**.

## A web page opens on the wrong screen

**Open Tasmota Web UI**, **Open Firmware Upgrade Page** and **Open Tasmota Device Web UI...** open the page in the web browser on the Mac that runs Indigo. If you are using Indigo from another computer or an iPad, type the device's network address into your own browser instead. The device's **IP Address** setting shows it.

## The log says "no IP recorded"

The plugin does not know the device's network address, so it cannot open its web page or upgrade it. Restart the device, or choose **Discover Tasmota Devices**, and the plugin picks the address up from what the device reports.

## A firmware upgrade says "could not tell which Tasmota firmware this chip needs"

The device did not answer when the plugin asked which chip it uses, or it has a chip the plugin does not know the firmware for. If a line just before it names the chip, the plugin does not know that one. Otherwise check the device's web page opens and try again. Either way, you can upgrade it from its own page with the **Open Firmware Upgrade Page** action.

## A button press does nothing in Indigo

The button has not been set to report its presses. Send it `SetOption73 1` with the **Send Raw Tasmota Command** action, as the [Actions and triggers](actions-and-triggers.md) page explains.

## Still stuck?

Choose **Plugins → Tasmota Bridge → Show Plugin Info**, copy the lines it writes to the Event Log, and post them on the [Indigo forum](https://forums.indigodomo.com) with a description of what you see. You can also [raise an issue on GitHub](https://github.com/Highsteads/TasmotaBridge/issues) — for a problem with one device, include its model, its firmware version and the output of **Dump Discovery Cache to Log**.
