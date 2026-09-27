---
title: How it works
nav_order: 4
---

# How it works

You do not need to know any of this to use the plugin. It is here for anyone who likes to know what is going on.

## The broker in the middle

Indigo never talks to a Tasmota device directly for day-to-day work. Each device keeps a connection open to your MQTT broker and sends it messages, and the plugin keeps one connection open to the same broker and listens.

Each device's messages carry the **Topic** you gave it, so the plugin knows which device each one comes from. To switch a device, the plugin sends a command to the broker under that device's topic, and the broker passes it on.

If the connection to the broker drops, the plugin reconnects by itself and says so in the Event Log. A command sent while it is disconnected is not delivered, and the log says so.

## Finding devices

When a Tasmota device connects to the broker, it leaves two notes there describing itself: one saying what it has — relays, a light, buttons, a shutter — with its name, model, network address and firmware version, and one with its sensor readings. The broker keeps both notes, so the plugin reads them whenever it connects, even for a device that connected hours earlier.

The plugin waits until it has both notes before it decides what the device is, because the second note is the one that shows whether a plug measures power. It then creates the Indigo device in a folder called **Tasmota**, making the folder the first time. It only ever sets the folder when it creates a device, so once you move a device to a room folder it stays there.

Each time the device connects again, the plugin updates its model, firmware version and network address from the new note, so the plugin always has the address it needs to open the device's web page or upgrade its firmware.

## Knowing which device is which

Every network device has a **MAC address**, a number it was made with that never changes, a bit like a serial number. The plugin stores it as the Indigo device's address, so it never creates a second Indigo device for the same Tasmota device. The second and later relays on a board share the board's MAC address with **-2**, **-3** and so on added to the end.

## Keeping Indigo up to date

A device sends a message the moment one of its relays switches, whatever switched it, so Indigo shows the change straight away. After a brightness or colour command, a light reports its new setting back, and Indigo shows that too.

Every five minutes, unless you have changed its **TelePeriod** setting, the device also sends a report with its Wi-Fi signal, how long it has been running, and its sensor and energy readings.

## Sensors the plugin has never heard of

Tasmota supports a great many sensors, and new ones appear all the time. Rather than knowing about each one, the plugin takes every reading in a device's report and makes a state for it, named after the sensor and the reading. It sets up any new state before writing to it, so even the first reading is kept, and it remembers each state it has made so they are still there after Indigo restarts.

## Noticing a device has gone

A device tells the broker in advance what to announce if it drops off the network — Tasmota sets this up by itself. When that announcement arrives, every Indigo device belonging to that Tasmota device shows **Offline**.

As a backstop, the plugin checks every 30 seconds for any device it has not heard from in 10 minutes, and marks it Offline too. Both can run the **Tasmota Device Went Offline** trigger.

## Firmware

Once each time the plugin starts, it asks GitHub for the latest Tasmota release and compares every device's firmware against it. The [Firmware updates](firmware.md) page covers this, and how the plugin upgrades a device.
