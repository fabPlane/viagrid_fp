# YKUSH-style switchable USB hub on Viagrid: feasibility

Target: something functionally like the [Yepkit YKUSH](https://www.yepkit.com/products/ykush),
a USB 2.0 hub with 3 downstream ports. Each port's power can be switched on and off from the host.

## TL;DR

- **Viable on a Viagrid 9055 Standard blank (2 layers, 90 x 55 mm), with some care.** A
  USB 2.0 High-Speed hub is routinely built on 2 layers, and Viagrid only gives you 2.
- **We could not confirm the YKUSH layer count.** Yepkit has not published the PCB files. The
  [estatz/YKUSH](https://github.com/estatz/YKUSH) repo says it has a `/Hardware` folder, but it
  only contains a README. [Yepkit/ykush](https://github.com/Yepkit/ykush) is only the host tool
  `ykushcmd`. The yepkit.com datasheets were not reachable from this environment. A USB 2.0 hub
  of this size is usually 2-layer. The USB 3 version (YKUSH 3) is almost certainly 4 or more.
  To check the real board, look at the edge or hold it up to a light.
- We would **re-design, not clone**. The design would follow the same architecture with parts
  chosen to fit the Viagrid grid.

## What Viagrid gives you

Taken from the `opulo-inc/viagrid` 9055 KiCad template:

| Property | Value |
|---|---|
| Layers | 2 (F.Cu / B.Cu), 1.6 mm FR4 |
| Usable blank | 90 x 55 mm, 4 mounting holes, fits a Hammond 1591XXB enclosure |
| Vias | 180, at **2.00 mm pitch**, but only in a ring around the edge plus four small clusters and four "+" crosses. The middle of the board has none (see `pcb/LAYOUT.md`) |
| Via | **0.2 mm drill**, 1.0 mm pad in the template |
| New vias | **None.** You can only change layers where one of those vias already exists |
| Through-hole | Not provided. You drill and mill any THT holes yourself, and they are **not plated** |

## YKUSH architecture (from public info and the `ykushcmd` source)

1. **USB 2.0 hub IC**: 1 upstream port and 3 or 4 downstream ports, running at HS/FS/LS.
2. **Control MCU**: a Microchip PIC. `ykushcmd` uses VID `0x04D8` (Microchip) and PID `0xF2F7`
   (legacy `0x0042`). The MCU sits on one hub port as a HID device, so no driver is needed.
3. **Per-port VBUS load switch**: 3 current-limited switches driven by MCU GPIOs.
4. **Power input**: USB bus power, or an external 5 V supply for the downstream devices.

## Design risks on Viagrid, and how to handle them

### 1. USB 2.0 HS differential pairs (90 ohm) on 1.6 mm 2-layer: manageable

- A 1.6 mm board makes plain microstrip over a ground plane far too wide for 90 ohm
  differential. Use **coplanar waveguide with ground (CPWG) on the top layer**. A starting
  point is about 0.3 mm traces, a 0.15 mm gap within the pair and 0.2 mm to the side ground
  pour. Tune it in the KiCad calculator.
- Keep D+/D- **entirely on F.Cu**, with no layer changes. Keep every run short (under 25 mm).
  Put the hub IC close to the connectors.
- Tie unused grid vias to GND. They then act as ground stitching for the CPWG.
- Grid spacing: 2 mm pitch minus a 1 mm via pad leaves 1 mm between pads. That is just
  enough for a narrow pair, so plan to route pairs **between grid rows**.
- Your process must hold about 0.15 mm (6 mil) isolation reliably. The Viagrid docs claim this
  for chemical etch (3 mil) and UV laser. CNC milling will struggle.

### 2. Fine-pitch ICs vs the 2 mm grid: the biggest layout constraint

- Grid vias are plated barrels that go through the board. Any grid via under a part must land
  **inside one pad of the right net**, or in an empty or GND area under the body. It can never
  land between two pads.
- With laser or etch you can trim the top ring well below the template's 1 mm, down to about
  0.4 mm. Model this by shrinking the via size in KiCad.
- **QFN hubs** (USB2513B/USB2514B, QFN-36, 0.5 mm pitch, 6 x 6 mm) are awkward. The pad ring
  is about 0.25 mm wide on 0.5 mm pitch, so a barrel cannot safely sit on it. The part must be
  placed so that no grid point falls on the pad ring. You also need 2x2 grid vias under the
  exposed pad for GND. It is doable, but requires careful offset and rotation.
- **SSOP hubs** are easier, for example FE1.1s or GL850G (SSOP-28 3.9 mm body, 0.635 mm pitch, 4-port USB 2.0
  HS). The pads are wider, so a via-in-pad on the pin that needs it is tolerable. They have no
  exposed pad and are easy to hand-solder. **This is the recommended choice for a first spin.**
- Load switches (SOT-23-5, for example AP2553/TPS2051-class) and a USB MCU in SOIC/TSSOP-14 (for
  example PIC16F1455, which needs no crystal) are easy.

### 3. Connectors: needs a drilling step

- USB-A receptacles use THT signal pins and/or large shell tabs. Viagrid has no plated THT,
  so you need to **drill or mill non-plated holes** and solder on one side only. Use
  **SMD-signal USB-A** parts and solder the shell tabs well, because they carry the plugging
  force.
- Upstream: an SMD USB-C (16-pin, USB 2.0 only) or micro-B. For a first build, a mid-mount
  micro-B or a USB-C "2.0 only" 16-pin part is fine.
- Size: 3 x USB-A at about 15-16 mm pitch is about 48 mm along the 90 mm edge, so it fits.
- The external 5 V input can be a 2-pin screw terminal or an SMD barrel jack.

### 4. Power: fine

- VBUS traces are about 1.5 mm wide on top and bottom for about 1.5 A total. No issue.
- Put a bulk cap (at least 120 uF across the downstream VBUS rail, per USB spec) and a
  per-port 10 uF cap.

## Simpler alternative: no MCU

Some hub ICs support **per-port power switching (PPPS)**, for example USB2514B with the PRTPWR
pins driving load switches. The host can then switch ports with **[uhubctl](https://github.com/mvp/uhubctl)**,
so there is no MCU and no firmware. This option is **not `ykushcmd`-compatible**. If you need
drop-in compatibility with YKUSH scripts, keep the MCU. Note that the PPPS route pushes you
toward the QFN USB2514B, not the SSOP parts.

## Suggested plan

1. Pick a path. Either **(A)** YKUSH-compatible (hub + PIC16F1455 + 3 load switches, and firmware
   that answers the YKUSH HID protocol), or **(B)** PPPS hub + uhubctl.
2. Start from the Viagrid 9055 KiCad template. Place the connectors first, then the hub IC
   close to them, with D+/D- on F.Cu only.
3. Set DRC to your process: about 0.15 mm clearance and a via pad of about 0.45 mm.
4. Build a bare-board etch test of just the hub IC footprint and one USB pair before the
   full board.

## Verdict

**Feasible on a 2-layer Viagrid 9055.** The difficult parts are placing the fine-pitch hub IC
on the fixed grid and drilling the USB-A shell holes. The number of layers is not a problem.
Use an SSOP hub IC for the first attempt.
