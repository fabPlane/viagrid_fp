"""Placement for YKUSH-VG on the Viagrid 9055 blank.

Coordinates are board-relative mm (origin = top-left corner of the 90x55 blank, y down),
rotation in degrees (KiCad convention). Constraints that drove this layout are in
../pcb/LAYOUT.md.
"""

BW, BH = 89.9, 54.9

# USB-A sockets on the bottom edge. These x positions are the only ones where the
# socket's 4 signal pads clear the lower Viagrid clusters (see LAYOUT.md).
PORT_X = (16.4, 45.0, 73.2)
PORT_Y = BH - 7.58          # TE 292303-7 front face flush with the board edge

PLACE = {
    # ---- connectors
    'J1': (47.84, 4.10, 180),            # USB-C, 0.45 mm in from the top edge
    'J2': (PORT_X[0], PORT_Y, 0),
    'J3': (PORT_X[1], PORT_Y, 0),
    'J4': (PORT_X[2], PORT_Y, 0),
    'J5': (84.70, 21.45, 270),           # screw terminal, overhangs right edge 0.55 mm

    # ---- upstream
    'JP1': (48.125, 10.50, 0),           # 0R jumper: USB-C D- (A7 -> B7) over the A6 D+ trace
    'R1': (52.60, 10.40, 0),             # CC1 5.1k
    'R2': (43.20, 10.30, 0),             # CC2 5.1k
    'C1': (57.40, 10.60, 90),            # VBUS_UP 10u

    # ---- hub (pins 1-14 face down, 15-28 face up)
    'U1': (47.00, 22.00, 90),
    'Y1': (39.90, 24.00, 90),            # crystal, fed through the gap under the hub
    'C3': (44.60, 12.90, 90),            # VDD5 10u, on the VBUS feed to pin 20
    'C4': (45.70, 16.60, 90),            # VD33_O 10u
    'C5': (52.80, 27.40, 270),           # VD33 100n, below pin 13
    'C6': (50.90, 27.40, 270),           # VD18_O 10u, below pin 12
    'C7': (42.90, 16.40, 90),            # VD18 100n, above pin 28
    'R5': (54.80, 17.20, 0),             # VBUSM divider top 56k
    'R6': (54.80, 19.00, 0),             # VBUSM divider bottom 100k
    'C8': (54.80, 20.80, 0),             # VBUSM 100n
    'R4': (54.50, 27.40, 270),           # REXT 2.7k, below pin 14

    # ---- MCU U2 (top-left). Its USB link is Full-Speed, so it may use Viagrid vias freely;
    # USB, VCC and V33 pins face up toward the top corridor.
    'U2': (35.40, 16.40, 90),
    'C9': (32.20, 10.20, 90),            # VCC 10u, inline between its via and VCC
    'C10': (30.20, 10.40, 90),           # V33 100n
    'SW1': (20.00, 11.20, 0),            # BOOT
    'R7': (25.40, 13.60, 0),             # BOOT -> UDP 10k

    # ---- power path
    'F1': (78.20, 13.20, 90),
    'D1': (74.00, 18.60, 0),             # EXT -> +5V_PORT
    'D2': (62.00, 11.50, 0),             # VBUS_UP -> +5V_PORT
    'C2': (71.00, 11.50, 0),             # +5V_PORT bulk 220u
    # indicator LEDs along the front edge, in the gaps between the USB-A sockets
    'R3': (55.45, 42.60, 0), 'D3': (55.45, 45.40, 0),     # power
}

# ---- per-port groups: SY6280 load switch, ISET, EN pull-down, Cin, 22u bulk, 10u out, ESD, LED
PORTS = {
    # port 1 (J2): group left of the socket
    'P1': dict(sw=('U3', 12.00, 32.00, 180), riset=('R9', 12.00, 29.00, 0), ren=('R10', 8.60, 28.60, 90),
               cin=('C11', 8.60, 32.40, 90), cbulk=('C12', 11.60, 37.60, 0), cout=('C13', 12.00, 35.00, 0),
               esd=('U4', 16.40, 36.60, 270), rled=('R11', 27.60, 42.60, 0), led=('D5', 27.60, 45.40, 0)),
    # port 2 (J3): group left of the socket (its VBUS pin is the left one)
    'P2': dict(sw=('U5', 40.60, 32.80, 180), riset=('R12', 36.60, 30.80, 90), ren=('R13', 40.60, 29.60, 0),
               cin=('C14', 44.00, 30.60, 90), cbulk=('C15', 36.60, 35.40, 90), cout=('C16', 40.60, 36.00, 0),
               esd=('U6', 45.00, 36.60, 270), rled=('R14', 33.80, 42.60, 0), led=('D6', 33.80, 45.40, 0)),
    # port 3 (J4): group right of the socket (the lower-right Viagrid cluster is on its left)
    'P3': dict(sw=('U7', 77.60, 32.00, 0), riset=('R15', 77.60, 29.00, 0), ren=('R16', 76.00, 26.40, 0),
               cin=('C17', 81.20, 32.40, 90), cbulk=('C18', 78.00, 37.60, 0), cout=('C19', 77.60, 35.00, 0),
               esd=('U8', 73.20, 36.60, 270), rled=('R17', 62.75, 42.60, 0), led=('D7', 62.75, 45.40, 0)),
}
for grp in PORTS.values():
    for ref, x, y, rot in grp.values():
        PLACE[ref] = (x, y, rot)
PLACE['R8'] = (59.10, 42.60, 0)        # status LED next to the power LED
PLACE['D4'] = (59.10, 45.40, 0)
