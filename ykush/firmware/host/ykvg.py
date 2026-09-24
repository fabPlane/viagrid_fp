#!/usr/bin/env python3
"""Talk to a YKUSH-VG board (or any YKUSH) over HID. Needs `pip install hidapi`.

    ykvg.py list                 boards and their serial numbers
    ykvg.py up 1|2|3|a           switch a port (or all) on
    ykvg.py down 1|2|3|a         switch a port (or all) off
    ykvg.py status               state of every port
    ykvg.py boot                 YKUSH-VG only: reboot the CH552 into its USB bootloader
    add  -s SERIAL  to pick one board when several are connected

Yepkit's own `ykushcmd` works too (same protocol and USB IDs); this is a small alternative
that also knows the YKUSH-VG extras.
"""
import argparse
import sys

try:
    import hid
except ImportError:
    sys.exit('needs hidapi: pip install hidapi')

VID, PID = 0x04D8, 0xF2F7


def open_board(serial=None):
    dev = hid.device()
    dev.open(VID, PID, serial)
    return dev


def xfer(dev, cmd):
    dev.write([0x00, cmd] + [0] * 63)            # report ID 0 + 64-byte report
    resp = dev.read(64, 2000)
    if not resp or resp[0] != 0x01:
        raise RuntimeError(f'board rejected command 0x{cmd:02X}: {resp[:2] if resp else "no reply"}')
    return resp


def port_arg(p):
    return 0x0A if p == 'a' else int(p)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('-s', '--serial')
    ap.add_argument('action', choices=['list', 'up', 'down', 'status', 'boot'])
    ap.add_argument('port', nargs='?', choices=['1', '2', '3', 'a'])
    a = ap.parse_args()

    if a.action == 'list':
        boards = hid.enumerate(VID, PID)
        for b in boards:
            print(f"{b['serial_number']}  {b['product_string']}  ({b['path'].decode(errors='replace')})")
        if not boards:
            print('no YKUSH boards found')
        return

    dev = open_board(a.serial)
    try:
        if a.action in ('up', 'down'):
            if not a.port:
                ap.error('which port? 1, 2, 3 or a')
            xfer(dev, (0x10 if a.action == 'up' else 0x00) | port_arg(a.port))
        elif a.action == 'status':
            for p in (1, 2, 3):
                r = xfer(dev, 0x20 | p)
                print(f'port {p}: {"ON" if r[1] >> 4 else "off"}')
        elif a.action == 'boot':
            xfer(dev, 0xB0)
            print('rebooting into the CH552 bootloader; flash with: wchisp flash build/ykush_vg.hex')
    finally:
        dev.close()


if __name__ == '__main__':
    main()
