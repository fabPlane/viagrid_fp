# YKUSH-VG firmware (CH552G)

This firmware runs on the CH552G that sits on port 4 of the hub. It switches the three
SY6280 port power switches, and it speaks **the YKUSH HID protocol with the YKUSH USB IDs**,
so Yepkit's `ykushcmd` works unchanged:

```sh
ykushcmd -l          # list boards (serial = "VG" + the CH552's unique chip ID)
ykushcmd -d 2        # port 2 off
ykushcmd -u a        # all ports on
ykushcmd -g 3        # is port 3 on?
```

`host/ykvg.py` (Python, `pip install hidapi`) does the same, and it can also reboot the board
into the bootloader for reflashing.

## Behaviour

- **At power-up the ports come on one after another, 100 ms apart**, like a YKUSH. Build with
  `make EXTRA_FLAGS=-DPORTS_ON_AT_BOOT=0` to have them start off.
- **Status LED (P3.2):** on while the host has configured the board. It blinks on every command.
- **The ports keep their state while the host suspends the USB bus.**

| Request byte | Meaning | Reply |
|---|---|---|
| `0x11` `0x12` `0x13` / `0x1A` | port 1/2/3 on / all on | `[0x01, cmd]` |
| `0x01` `0x02` `0x03` / `0x0A` | port 1/2/3 off / all off | `[0x01, cmd]` |
| `0x21` `0x22` `0x23` | status of port N | `[0x01, (on<<4) \| N]` |
| `0x2A` | *(YKUSH-VG)* all ports | `[0x01, bitmask]` |
| `0xB0` | *(YKUSH-VG)* reboot into the CH552 USB bootloader | `[0x01, 0xB0]` |
| anything else | rejected | `[0x00]` |

Requests and replies are 64-byte reports on interrupt endpoints OUT 0x01 and IN 0x81.
HID SET_REPORT and GET_REPORT on endpoint 0 work too.

## Build and test

```sh
sudo apt install sdcc
make            # build/ykush_vg.hex + .bin (about 2.5 KB of the 14 KB available)
make test       # checks the USB descriptors in the built image, then unit-tests the protocol
make e2e        # builds Yepkit's real ykushcmd against the protocol code and drives it
```

## Flash

1. **First time:** hold **BOOT (SW1)** while plugging the board into USB. A blank CH552 also
   starts in its bootloader.
2. **Later:** run `host/ykvg.py boot` and the firmware jumps to the bootloader itself.
3. Flash with [wchisp](https://github.com/ch32-rs/wchisp):
   ```sh
   wchisp flash build/ykush_vg.hex          # or: make flash
   ```

On Linux, install `host/99-ykush-vg.rules` so this works without root.

## Pin map (matches `../kicad/ykush_vg.kicad_sch`)

| CH552G | Function |
|---|---|
| P3.6 / P3.7 | USB D+ / D- (hub port 4, full speed) |
| P1.4 | EN port 1 (J2, left) |
| P3.3 | EN port 2 (J3, middle) |
| P3.4 | EN port 3 (J4, right) |
| P3.2 | status LED |

## Status and caveats

- **Tested so far:**
  - the protocol logic, with unit tests;
  - interoperability with the real `ykushcmd` code, with the USB layer stubbed out;
  - the USB descriptors, parsed from the built image.

  **The USB stack has not yet run on real hardware.** Bring-up on the first board is the next
  step.
- **USB IDs:** `04D8:F2F7` is Microchip's VID with Yepkit's product ID. It is used here only so
  that `ykushcmd` works unchanged, for personal and lab use. Build your own IDs with
  `make EXTRA_FLAGS='-DUSB_VID=0x.... -DUSB_PID=0x....'`; `host/ykvg.py` takes the same.
- **Licensing:** `include/ch554.h` and `include/ch554_usb.h` are WCH's register headers (via
  [ch554_sdcc](https://github.com/Blinkinlabs/ch554_sdcc)). The rest was written for this
  project.
