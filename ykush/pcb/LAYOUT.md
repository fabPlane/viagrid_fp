# YKUSH-VG layout notes (Viagrid 9055 Standard)

The PCB is built by a script, not drawn by hand:

```sh
cd tools
PYTHONPATH=/opt/kicad10/lib/python3/dist-packages python3 build_pcb.py   # ~15 min
python3 render.py            # PNG preview
kicad-cli pcb drc ../kicad/ykush_vg.kicad_pcb
```

- `placement.py` places the parts.
- `router.py` routes the board.
- `build_pcb.py` puts them together: it builds the outline and Viagrid vias, loads footprints from the schematic netlist, then places, routes and pours.

## What the blank gives you

`viagrid_9055.json` holds the via positions, extracted from the official template. The 9055
Standard is **not a full via grid**:

| Where | Vias |
|---|---|
| Top and bottom rows (y = 6.95 and 47.95 mm) | 36 each, 2 mm pitch, x 9.95–79.95 |
| Left and right columns (x = 6.95 and 82.95 mm) | 15 each, y 13.45–41.45 |
| Four 3x5 clusters (+2 end vias each) | 17 each: upper/lower at y 15.45–19.45 and 35.45–39.45 |
| Four "+" crosses | 5 each, around (25.95, 27.45) and (63.95, 27.45) |
| Mounting holes | 4 plated, 3.5 mm drill |

Coordinates are board-relative (origin at the top-left of the 90 x 55 mm blank).

A track can change layer **only at one of these vias**. The middle of the board, where the hub
sits, has none.

## Rules the layout follows

- **Grid via copper is trimmed to 0.6 mm**, compared with 1.0 mm on the blank. The laser or
  etch removes the rest. Clearance is 0.15 mm and signal tracks are 0.25 mm.
- **Unused vias stay on GND** and stitch the two ground pours together.
- **Through-hole parts are soldered from B.Cu only.** Holes you drill in a Viagrid are not
  plated. This applies to the screw terminal and to the USB shell tabs and pegs. The router only
  connects to THT pads on B.Cu.
- **B.Cu costs 2x per mm** in the router, so it stays mostly a ground plane.

## Decisions forced by the via map

1. **Upstream USB-C (J1) sits on the top edge, 0.45 mm in.** Its pads then clear the top via row
   by 0.165 mm. The shell pegs land on GND vias, which is harmless.
2. **The USB-C D+ pads cannot be joined without a via, so JP1 (0 R) does it.** USB-C interleaves
   the pads as B6(D+) A7(D-) A6(D+) B7(D-), and no via sits beside them. JP1 carries D+ from A6
   over the A7 trace.
3. **The USB-A sockets are at x = 16.4 / 45.0 / 73.2.** These are the only positions where each
   socket's four signal pads clear the lower clusters. The sockets are TE 292303-7: SMT signal
   pins, with only the two shell tabs needing holes.
4. **Hub port order along the SSOP matches the board.** Port 4 goes to the CH552G, port 3 to J2,
   port 2 to J3 and port 1 to J4. A USB pair can never swap D+/D-, so any other order forces a
   crossing that needs a via.
5. **The gap under the FE1.1s carries +1V8 (pin 28 → 12), +3V3 (21 → 13), VBUSM, REXT and the
   crystal.** These nets link the two pin rows. Routing them around the outside would cross the
   USB pairs.
6. **The CH552G's link is Full-Speed (12 Mbit/s).** It is the only USB link allowed to hop to
   B.Cu through Viagrid vias. The four 480 Mbit/s pairs stay on F.Cu.
7. **Port 3's support parts sit right of its socket.** The lower-right cluster is on its left.
8. **The indicator LEDs sit along the front edge,** in the gaps between the USB-A sockets.

## Schematic simplifications made for the layout

- **Debug header dropped.** The CH552G is flashed over USB: hold BOOT while plugging in.
- **Hub activity LED dropped.** FE1.1s DRV/LED pins are outputs and are left open.
- **FE1.1s XRSTJ and BUSJ are tied to the VBUSM divider** (56k/100k, about 3.2 V) instead of
  having separate pull-ups. All three pins are adjacent.
- **Per-port bulk is 22 µF ceramic, not 220 µF electrolytic.** There is one 220 µF on
  `+5V_PORT`, and the SY6280 soft-start limits inrush.
