# YKUSH-VG: 3-port switchable USB 2.0 hub on a Viagrid 9055 blank

A board that works like the [Yepkit YKUSH](https://www.yepkit.com/products/ykush), laid out for a
2-layer [Viagrid](https://github.com/opulo-inc/viagrid) 9055 blank.

- **Hub:** Terminus FE1.1s (SSOP-28). Upstream port is USB-C. Ports 1-3 go to the USB-A sockets,
  and port 4 goes to the control MCU.
- **Control:** WCH CH552G. The host sees it as a HID device. The plan is for its firmware to speak
  the YKUSH protocol, so `ykushcmd` works unchanged.
- **Port power:** one SY6280AAC current-limited switch per port. The CH552G drives each EN pin,
  and each EN has a 100k pull-down so the port stays off during boot.
- **Power:** from upstream VBUS, or from an external 5 V screw terminal. The two sources are
  diode-ORed onto `+5V_PORT`.

| File | What |
|---|---|
| `FEASIBILITY.md` | Why this is doable on Viagrid, and the risks |
| `kicad/ykush_vg.kicad_pro` / `.kicad_sch` | KiCad 10 project and schematic (generated) |
| `kicad/ykush_vg.kicad_sym`, `kicad/sym-lib-table` | Project symbol library (CH552G, SY6280AAC) |
| `kicad/ykush_vg_schematic.pdf` | PDF of the schematic |
| `kicad/bom.md`, `kicad/bom.csv` | BOM with Shopee/Lazada, AliExpress, DigiKey and JLCPCB columns |
| `kicad/nets.txt` | Netlist the generator intended |
| `tools/make_schematic.py` | **Source of truth.** Edit this, then regenerate |
| `tools/check_netlist.py` | Exports the netlist with kicad-cli and diffs it against `nets.txt` |

```sh
cd tools && python3 make_schematic.py && python3 check_netlist.py
kicad-cli sch erc --severity-all ../kicad/ykush_vg.kicad_sch
```

Needs KiCad 10. The generator reads the KiCad 10 symbol libraries and then runs
`kicad-cli sch upgrade`, so the saved file is in KiCad's native format.

## Status
- [x] Schematic. Pinouts checked against the FE1.1s, CH552 and SY6280 datasheets, and against
  open-source boards.
- [x] BOM and sourcing
- [x] ERC in KiCad 10.0.6: 0 violations (all severities)
- [ ] PCB layout on the Viagrid 9055 grid
- [ ] CH552 firmware (YKUSH HID protocol)
