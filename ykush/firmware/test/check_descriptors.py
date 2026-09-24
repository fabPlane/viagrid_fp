"""Validate the USB descriptors inside the built firmware image (build/ykush_vg.ihx),
the way a host parses them at enumeration. No hardware needed.

    python3 test/check_descriptors.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, '..', 'build')


def load_ihx(path):
    mem = {}
    for line in open(path):
        if not line.startswith(':'):
            continue
        n, addr, typ = int(line[1:3], 16), int(line[3:7], 16), int(line[7:9], 16)
        if typ == 0:
            for i in range(n):
                mem[addr + i] = int(line[9 + 2 * i:11 + 2 * i], 16)
    return mem


def symbols(path):
    syms = {}
    for line in open(path):
        m = re.match(r'\s*C:\s+([0-9A-F]+)\s+(_\w+)', line)
        if m:
            syms[m.group(2)] = int(m.group(1), 16)
    return syms


def main():
    mem = load_ihx(os.path.join(BUILD, 'ykush_vg.ihx'))
    syms = symbols(os.path.join(BUILD, 'ykush_vg.map'))
    rd = lambda a, n: bytes(mem[a + i] for i in range(n))
    errors = []

    def check(cond, msg):
        if not cond:
            errors.append(msg)

    dev = rd(syms['_dev_desc'], 18)
    check(dev[0] == 18 and dev[1] == 1, 'device descriptor header')
    check(dev[2:4] == b'\x00\x02', 'bcdUSB 2.00')
    check(dev[7] == 64, 'EP0 max packet 64')
    vid, pid = dev[8] | dev[9] << 8, dev[10] | dev[11] << 8
    check((vid, pid) == (0x04D8, 0xF2F7), f'YKUSH VID/PID, got {vid:04X}:{pid:04X}')
    check(dev[14:17] == b'\x01\x02\x03', 'string indexes 1/2/3')
    check(dev[17] == 1, 'one configuration')

    cfg_addr = syms['_cfg_desc']
    head = rd(cfg_addr, 9)
    total = head[2] | head[3] << 8
    cfg = rd(cfg_addr, total)
    check(head[1] == 2 and head[4] == 1, 'config descriptor, 1 interface')
    # walk the sub-descriptors: lengths must add up exactly
    pos, kinds = 0, []
    while pos < total:
        ln, typ = cfg[pos], cfg[pos + 1]
        check(ln >= 2, f'descriptor length at {pos}')
        kinds.append((typ, cfg[pos:pos + ln]))
        pos += ln
    check(pos == total, 'wTotalLength matches the descriptors')
    types = [k for k, _ in kinds]
    check(types == [2, 4, 0x21, 5, 5], f'config layout config/interface/HID/EP/EP, got {types}')
    intf = kinds[1][1]
    check(intf[5] == 0x03 and intf[4] == 2, 'HID interface with 2 endpoints')
    hid = kinds[2][1]
    rlen = hid[7] | hid[8] << 8
    eps = {e[2]: e for _, e in kinds[3:]}
    for addr in (0x81, 0x01):
        e = eps.get(addr)
        check(e is not None and e[3] == 3 and (e[4] | e[5] << 8) == 64, f'endpoint {addr:02X}: interrupt, 64 bytes')

    rep = rd(syms['_report_desc'], rlen)
    check(rep[-1] == 0xC0, 'report descriptor ends with END_COLLECTION (length in HID descriptor is right)')
    # every Input/Output main item must describe 64 x 8-bit fields
    size = count = None
    i = 0
    ins = outs = 0
    while i < len(rep):
        b = rep[i]
        n = [0, 1, 2, 4][b & 3]
        val = int.from_bytes(rep[i + 1:i + 1 + n], 'little')
        tag = b & 0xFC
        if tag == 0x74:
            size = val
        elif tag == 0x94:
            count = val
        elif tag in (0x80, 0x90):
            check(size == 8 and count == 64, 'reports are 64 bytes')
            ins += tag == 0x80
            outs += tag == 0x90
        i += 1 + n
    check(ins == 1 and outs == 1, 'one input and one output report')

    if errors:
        for e in errors:
            print('FAIL:', e)
        sys.exit(1)
    print(f'USB descriptors OK: {vid:04X}:{pid:04X}, config {total} bytes, '
          f'HID report descriptor {rlen} bytes, EP 0x81/0x01 interrupt 64 B')


if __name__ == '__main__':
    main()
