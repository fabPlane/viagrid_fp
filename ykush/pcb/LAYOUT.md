# YKUSH-VG layout notes (Viagrid 9055 Standard)

The PCB is built by a script, not drawn by hand:

```sh
cd tools
export PYTHONPATH=/opt/kicad10/lib/python3/dist-packages
python3 sweep.py        # routes 4 parameter sets in parallel (~25 min), keeps the best
python3 finish.py       # retries anything left unrouted, re-stitches GND
python3 drc.py          # KiCad DRC + schematic parity summary
python3 export_fab.py   # ../fab: laser DXFs, Gerbers, holes to drill, previews
```

## Result

KiCad 10.0.6 DRC with schematic parity:

- **Errors:** 0 (no clearance, short, crossing or hole problems).
- **Unconnected items:** 0.
- **Schematic mismatches:** 0.

Two kinds of warning remain, and both are expected:
- **~18 "via_dangling".** These are Viagrid vias that a track passes over and claims. The
  plated barrel is in the blank whether we use it or not, so it belongs to that net.
- **1 "starved_thermal".** A GND pad has fewer pour spokes than KiCad's default. It is also
  tied to ground by a routed track.

You drill **14 holes** yourself (`fab/holes_to_drill.csv`):
- USB-C: 2 pegs and 4 shell slots
- USB-A: 6 shell tabs
- screw terminal: 2 pins

Every other connection is SMD or a Viagrid via. Solder the through-hole parts from B.Cu,
because holes you drill are not plated.

## How the router works (router.py)

- **Grid A\*, two layers, 0.1 mm cells.** The C core is `astar.c`. Direction changes are
  limited to 45°/90°. A path may change layer **only at a Viagrid via**.
- **Negotiated congestion (PathFinder).** Other nets' copper is a cost, not a wall. Cells that
  stay contested get more expensive every round. Anything still in conflict at the end is
  rerouted strictly.
- **GND is routed as a net.** Every SMD GND pad goes to the nearest Viagrid via, which is tied
  to the B.Cu plane. A few pins that would otherwise get walled in are tied early
  (`GND_TIES`). The pours then fill around the routing.
- **Pads joined inside the ESD chip are routed as one target.** The flow-through ESD's pin pairs
  1-6 and 3-4 are written into the footprint as KiCad jumper pad groups, so DRC agrees.

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
2. **The USB-C data pads need a jumper.** USB-C interleaves them as B6(D+) A7(D-) A6(D+)
   B7(D-), and no via sits beside them. JP1 (0 R) carries D- from A7 over the A6 trace to B7,
   and the two D+ pads join just below it. The pair then leaves with D+ on the left and D- on
   the right, matching hub pins 16/15.
   - **VBUS pads:** both drop straight onto the top-row vias behind them (x 45.95 / 49.95).
   - **VBUS spine on B.Cu:** it runs along the edge and brings VBUS out at x 41.95, feeding the
     MCU and hub pin 20, and at x 53.95, feeding C1, D2 and the VBUSM divider.
   - **CC1/CC2:** with VBUS off the top layer there, they run freely under the pads.
   - **No upstream ESD.** Its VBUS/GND pins sit between the data pins and cannot be reached
     without blocking the pair. The three port-side USBLC6s remain.
3. **The USB-A sockets are at x = 16.4 / 45.0 / 73.2.** These are the only positions where each
   socket's four signal pads clear the lower clusters. The sockets are TE 292303-7: SMT signal
   pins, with only the two shell tabs needing holes.
4. **Hub port order along the SSOP matches the board.** Port 4 goes to the CH552G, port 3 to J2,
   port 2 to J3 and port 1 to J4. A USB pair can never swap D+/D-, so any other order forces a
   crossing that needs a via.
5. **The gap under the FE1.1s carries +1V8 (pin 28 → 12), +3V3 (21 → 13), VBUSM and the
   crystal.** These nets link the two pin rows, and routing them around the outside would cross
   the USB pairs. The decoupling for pins 12-13 and the REXT resistor sit directly below those
   pins.
   The port ESDs (USBLC6-2SC6) are rotated 270° so that their D-/D+ pin columns line up with
   the socket's D- (left) and D+ (right) pins, and the pair runs straight through them.
6. **The CH552G's link is Full-Speed (12 Mbit/s).** It is the only USB link allowed to hop to
   B.Cu through Viagrid vias. The four 480 Mbit/s pairs stay on F.Cu.
7. **Port 3's support parts sit right of its socket.** The lower-right cluster is on its left.
8. **The indicator LEDs sit along the front edge,** in the gaps between the USB-A sockets.

## Schematic simplifications made for the layout

- **Debug header dropped.** The CH552G is flashed over USB: hold BOOT while plugging in.
- **Upstream ESD dropped** (see item 2 above).
- **Hub activity LED dropped.** FE1.1s DRV/LED pins are outputs and are left open.
- **FE1.1s XRSTJ and BUSJ are tied to the VBUSM divider** (56k/100k, about 3.2 V) instead of
  having separate pull-ups. All three pins are adjacent.
- **Per-port bulk is 22 µF ceramic, not 220 µF electrolytic.** There is one 220 µF on
  `+5V_PORT`, and the SY6280 soft-start limits inrush.
