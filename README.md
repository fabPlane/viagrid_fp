# viagrid_fp
Viagrid example projects

This repository contains **10 introductory [Viagrid](https://viagrid.io) circuit board designs** covering fundamental PCB concepts. Each board is stored as a JSON file in the `boards/` directory and can be opened directly in Viagrid.

---

## Boards

| # | File | Description |
|---|------|-------------|
| 01 | [LED Blinker](boards/01_led_blinker.json) | 555-timer astable oscillator driving a red LED. Introduces RC timing, decoupling caps, and output current limiting. |
| 02 | [Push-Button LED](boards/02_push_button_led.json) | Tactile switch → current-limiting resistor → LED. The simplest possible complete circuit; includes a 100 nF debounce cap. |
| 03 | [3.3 V Buck Regulator](boards/03_buck_regulator_3v3.json) | XL4005 step-down switcher (5–40 V in → 3.3 V / 2 A out). Covers feedback dividers, flyback diode, and output capacitor sizing. |
| 04 | [Arduino Nano Breakout](boards/04_arduino_nano_breakout.json) | Clean breakout board exposing all Nano I/O pins on 0.1″ headers with barrel-jack power, decoupling caps, and M3 mounting holes. |
| 05 | [USB-C PD Sink](boards/05_usb_c_pd_sink.json) | CH224K PD negotiation IC requests 9 V or 12 V from a USB-C charger. Demonstrates CC resistors, TVS protection, and DIP-switch voltage selection. |
| 06 | [H-Bridge Motor Driver](boards/06_h_bridge_motor_driver.json) | L298N dual H-bridge for bidirectional DC motor or stepper control. Covers PWM inputs, flyback diodes, and isolated motor/logic power domains. |
| 07 | [Temp & Humidity Sensor Node](boards/07_temp_humidity_sensor_node.json) | ESP8266 (Wemos D1 Mini) + DHT22 with TP4056 LiPo charger and 3.3 V LDO. Teaches sensor pull-ups, battery management, and low-power Wi-Fi. |
| 08 | [RS-485 Isolated Transceiver](boards/08_rs485_isolated_transceiver.json) | MAX485 with PC817 opto-isolation for Modbus RTU. Shows bus termination, fail-safe bias resistors, and isolated power planes. |
| 09 | [Raspberry Pi HAT – GPIO & RTC](boards/09_rpi_hat_gpio_rtc.json) | MCP23017 I²C GPIO expander + DS3231 RTC + AT24C32 EEPROM on a standard RPi HAT form factor. Covers I²C addressing, battery backup, and HAT compliance. |
| 10 | [Class-D Audio Amplifier](boards/10_class_d_audio_amplifier.json) | PAM8403 stereo 3 W×2 amplifier with log-pot volume control, input coupling caps, and ferrite-bead EMI filters on speaker outputs. |

---

## How to use

1. Open [viagrid.io](https://viagrid.io) in your browser.
2. Create a new board or select *Import*.
3. Upload the desired `.json` file from the `boards/` directory.
4. The schematic, net list, and component placements will load automatically.
