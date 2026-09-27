---
title: Your devices
nav_order: 3
---

# Your devices

The plugin looks at what each Tasmota device says it has, and picks the Indigo device type to match. You do not choose the type yourself. It checks in this order and takes the first that fits:

1. The device drives a shutter or blind — **Tasmota Shutter**.
2. The device has a light — **Tasmota Light**.
3. The device has one or more relays — **Tasmota Energy Plug** if it also measures power, otherwise **Tasmota Relay**.
4. The device has buttons and nothing above — **Tasmota Button**.
5. Anything else — **Tasmota Sensor**.

Each device is named with the name Tasmota gives it, or its host name if it has none, and its line in Indigo's device list shows its network address and model.

## Readings every device type shows

Most of the device types carry the same set of readings about the device itself. The table lists them with the names Indigo shows under the device's states.

| State | What it means |
|---|---|
| `availability` | **Online** or **Offline** — whether the device is connected to the broker. It turns to Offline when the device says it has gone, or when the plugin has heard nothing from it for 10 minutes. |
| `rssi` | How strong the device's Wi-Fi signal is, as Tasmota gives it, from 0 to 100. Higher is better. |
| `signal` | The same Wi-Fi signal in the units radio people use, dBm, such as -60. Nearer to zero is better. |
| `uptime` | How long the device has been running since it last started. |
| `lastSeen` | The time of the device's last regular report. |
| `restartReason` | Why the device last started, such as a power cut or a software restart. |
| `firmwareStatus` | **up-to-date**, **update available:** followed by the newest version, or **unknown**. The [Firmware updates](firmware.md) page explains it. |

Tasmota sends these every five minutes unless you have changed its **TelePeriod** setting.

## Tasmota Relay

For a plug, switch or relay board that switches something on and off, such as a Sonoff Basic.

You control it with Indigo's usual **Turn On**, **Turn Off** and **Toggle**, from the device list, a control page, a schedule, a trigger or an action group. Indigo shows the change as soon as the device reports it, whether Indigo, the device's own button or anything else switched it.

It carries all the readings in the table above.

## Tasmota Energy Plug

For a plug or relay that also measures the power going through it, such as an Athom plug or a Sonoff POW. It switches exactly like a Tasmota Relay, and Indigo shows its power and energy alongside on and off.

| State | What it means |
|---|---|
| `curEnergyLevel` | The power being drawn right now, in watts. |
| `accumEnergyTotal` | The total energy used since the device started counting, in kWh. |
| `energyToday` | The energy used so far today, in kWh. |
| `energyYesterday` | The energy used yesterday, in kWh. |
| `voltage` | The mains voltage. |
| `current` | The current being drawn, in amps. |
| `apparentPower` | Apparent power, in VA. |
| `reactivePower` | Reactive power, in VAR. |
| `powerFactor` | The power factor, from 0 to 1. |

It also carries all the readings in the first table.

## Boards with more than one relay

A board with several relays, such as a Sonoff 4CH, becomes one Indigo device per relay, each switched on its own. They are named with the device's name followed by **- Ch 1**, **- Ch 2** and so on.

The first relay's device is a Tasmota Energy Plug if the board measures power, because Tasmota measures power for the whole board rather than for each relay. The others are always Tasmota Relays.

When the board goes offline, every one of its Indigo devices shows Offline together.

## Tasmota Light

For a bulb, LED strip or dimmer. You switch it and set its brightness with Indigo's usual controls. To set a colour or a shade of white, use the **Set HSB Color** and **Set Colour Temperature** actions on the [Actions and triggers](actions-and-triggers.md) page.

The device's **Light Subtype** setting shows which kind of light Tasmota reported: 1 for a plain dimmer, 2 for adjustable white, 3 for colour, 4 for colour with white, and 5 for colour with both warm and cool white.

| State | What it means |
|---|---|
| `colorTemp` | The shade of white, in mireds — 153 is the coolest, bluest white and 500 the warmest. |
| `hsbColor` | The last colour the light reported. |
| `availability`, `rssi`, `firmwareStatus`, `restartReason` | As in the first table. |

## Tasmota Sensor

For a device with no relay or light, only sensors — a temperature probe, or a sensor for temperature, humidity and air pressure.

You do not need to tell the plugin what sensors are attached. Every reading the device sends becomes a state on the Indigo device, named after the sensor and the reading, so a BME280 sensor gives `bme280Temperature`, `bme280Humidity` and `bme280Pressure`. A new reading appears the first time the device sends it. The device's **Sensors** setting lists the sensors it found when it created the device.

A plug or switch with a sensor attached gets the same extra states on its own device.

It also carries `availability`, `rssi`, `lastSeen`, `firmwareStatus` and `restartReason`.

## Tasmota Button

For a device that only has buttons, such as a wall switch set up with no relay. The plugin records each press, and the **Tasmota Button Pressed** trigger lets you act on it.

| State | What it means |
|---|---|
| `lastButton` | Which button was pressed last, from 1 to 8. |
| `lastAction` | What kind of press it was, as Tasmota reports it, such as a single press, a double press or a long hold. |
| `pressCount` | How many presses the plugin has counted. It goes up by one on every press, so a trigger can tell two identical presses apart. |
| `availability`, `rssi`, `firmwareStatus`, `restartReason` | As in the first table. |

## Tasmota Shutter

For a blind, curtain or roller shutter. Indigo treats it like a dimmer, where 0% is fully closed and 100% fully open.

- **Turn On** opens it fully and **Turn Off** closes it fully.
- The brightness slider moves it to that position.
- The **Open Shutter**, **Close Shutter** and **Stop Shutter** actions do what they say.

| State | What it means |
|---|---|
| `direction` | **opening**, **closing** or **stopped**. |
| `availability`, `firmwareStatus`, `restartReason` | As in the first table. |
