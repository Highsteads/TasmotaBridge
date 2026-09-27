---
title: Settings
nav_order: 6
---

# Settings

## The plugin's settings

Open these with **Plugins → Tasmota Bridge → Configure**. They apply to every Tasmota device.

### MQTT Broker Settings

| Setting | What it does |
|---|---|
| **Broker Host** | The network address of your MQTT broker, such as `192.168.1.20`, or its name on your network. The plugin cannot start talking to your devices without it, and says so in the Event Log. |
| **Broker Port** | The broker's port number, 1883 to start with. A broker that uses TLS usually listens on 8883. |
| **Username** | The user name your broker asks for, if it asks for one. |
| **Password** | The password to go with it. |
| **Use TLS** | Tick this if your broker only accepts encrypted connections, which is known as TLS. Most brokers on a home network do not use it, and nor does Tasmota to start with. |

If you change **Broker Host** and click Save, the plugin reconnects to the new broker straight away, picking up the other broker settings as it does. A change to **Broker Port**, **Username**, **Password** or **Use TLS** on its own takes effect the next time the plugin starts, so after saving choose **Plugins → Tasmota Bridge → Reload**.

### Device Discovery

| Setting | What it does |
|---|---|
| **Auto-create Indigo devices on discovery** | Ticked, the plugin creates an Indigo device for each Tasmota device it finds. Unticked, it still finds them and lists them with **List Seen Devices**, but you create the Indigo devices yourself. It is ticked to start with. |
| **Force-enable Tasmota discovery on each device** | This setting has no effect in this version. Leave it unticked. |

### Logging

| Setting | What it does |
|---|---|
| **Log Level** | **Debug (verbose)** adds a line to the Event Log for much of what the plugin does, which is only useful when chasing a problem. The other three choices give the normal log, which has the plugin's messages, warnings and errors. A change here takes effect the next time the plugin starts. |
| **Log raw MQTT payloads (debug)** | Writes every message the plugin receives from the broker into the Event Log. It only shows anything while **Log Level** is **Debug**, and it adds a great many lines, so leave it off unless you are asked for it. |

### Keeping the broker details in one file

If you run several of my plugins that use the same broker, you can keep the broker's details in one shared file instead of typing them into each plugin. The file is called `IndigoSecrets.py` and lives in `/Library/Application Support/Perceptive Automation/`. A blank copy, `IndigoSecrets_example.py`, comes inside the plugin — copy it to that folder, rename it `IndigoSecrets.py`, and fill in these lines with your own details:

```python
MQTT_BROKER   = "192.168.1.20"
MQTT_PORT     = 1883
MQTT_USERNAME = "your-user"
MQTT_PASSWORD = "your-password"
```

When the plugin starts, a broker address, user name or password in the file is used, whatever the Configure box says. The port comes from the Configure box whenever one is set there. Leave `MQTT_BROKER` as `""` if you would rather use the Configure box. The file holds settings for my other plugins too, and this plugin reads only the four lines above.

## Each device's settings

Open these by double-clicking a Tasmota device in Indigo. The plugin fills them all in when it creates the device, so there is usually nothing to change. If you untick **Auto-create Indigo devices on discovery** and add a device yourself, these are the boxes to fill in, and **List Seen Devices** in the plugin menu gives you each device's MAC address.

| Setting | Device types | What it does |
|---|---|---|
| **MAC Address** | All | The device's MAC address, twelve letters and numbers with no colons, such as `AABBCC000001`. The second and later relays on a board have **-2**, **-3** and so on added. |
| **MQTT Topic** | All | The **Topic** set on the device's **Configure MQTT** page. The plugin matches every message to its device by this name, so it must be the same in both places. |
| **Relay Channel** | Relay, Energy Plug | Which relay on the board this device switches, from 1 to 8. A single-relay device uses 1. |
| **Shutter Index** | Shutter | Which shutter on the device this is, from 1 to 4. A device with one shutter uses 1. |
| **IP Address** | Relay, Energy Plug, Light, Shutter | The device's network address, used to open its web page and to upgrade its firmware. The plugin keeps it up to date from what the device reports. |
| **Model** | All | The model Tasmota reports. You cannot change it here. |
| **Firmware** | Relay, Energy Plug | The Tasmota version the device reports. You cannot change it here. |
| **Light Subtype** | Light | The kind of light Tasmota reports: 1 for a plain dimmer, 2 for adjustable white, 3 for colour, 4 for colour with white, and 5 for colour with both warm and cool white. You cannot change it here. |
| **Sensors** | Sensor | The sensors the device reported when the plugin created it. You cannot change it here. |

If you change **MQTT Topic** on the Tasmota device, change it here to match.
