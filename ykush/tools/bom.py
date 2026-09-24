"""BOM with sourcing columns (Shopee/Lazada, AliExpress, DigiKey, JLCPCB/LCSC).

Sourcing research date: 2026-09-24. Marketplace data comes from search-result
listings (the stores themselves were not reachable from the build machine), so
treat prices/stock as "check before ordering". JLC Basic/Extended status is from
the daily scrape of JLC's Basic/Preferred list (github.com/CDFER/jlcpcb-parts-database).

Legend for the marketplace columns (Shopee/Lazada = Thailand sites):
  YES     = matching listing seen
  LIKELY  = commodity part, no exact listing seen
  NO      = not found
"""
import csv
import os
from collections import OrderedDict

# key: (value, footprint-substring) -> sourcing
# Marketplace column = Shopee Thailand (shopee.co.th) / Lazada Thailand (lazada.co.th).
KIT = 'YES - Shopee TH (0603 kit, 33 values x 20)'
SRC = [
    # value, fp match, part/MPN, shopee/lazada TH, aliexpress, digikey, lcsc, jlc_type, notes
    ('FE1.1s', 'SSOP-28', 'Terminus FE1.1S-BSOP28 (USB 2.0 HS 4-port hub)',
     'YES - Shopee TH (5 pcs)', 'YES',
     'NO (alt: Microchip USB2514B-AEZC-TR, QFN-36)', 'C9359', 'Extended',
     'Buy genuine Rev B (FE1.1S-BSOP28). Cross-border seller: 1-2 weeks.'),
    ('12MHz', 'Crystal', 'YXC X322512MSB4SI 12 MHz 3225 4-pad',
     'NO (only HC-49 seen)', 'YES', 'Abracon ABM8-12.000MHZ-B2-T (535-9826-1-ND)', 'C9002', 'Basic',
     'Passive crystal, not an oscillator. FE1.1s has internal load caps.'),
    ('CH552G', 'SOIC-16', 'WCH CH552G (SOP-16 MCU, USB device)',
     'YES - Shopee TH (variant in WCH multi-chip listing)', 'YES',
     'NO (alt: PIC16F1455-I/SL; needs different firmware)', 'C111292', 'Extended',
     'Blank chips boot into the USB bootloader.'),
    ('SY6280AAC', 'SOT-23-5', 'Silergy SY6280AAC load switch',
     'NO (MT9700 is on Shopee TH; verify pinout before substituting)', 'YES',
     'NO (alt: TI TPS2051BDBVR, different pinout)', 'C55136', 'Extended',
     'Order from AliExpress/LCSC. Not SY6280AAAC (C207620).'),
    ('USBLC6-2SC6', 'SOT-23-6', 'ST USBLC6-2SC6 USB ESD array',
     'YES - Shopee TH, Lazada TH', 'YES', '497-5235-1-ND', 'C7519', 'Extended', ''),
    ('USB-C 16P', 'USB_C', 'HRO TYPE-C-31-M-12 (USB 2.0 16-pin)',
     'YES - Shopee TH (TYPE-C-31-M-12), Lazada TH (16P)', 'YES',
     'NO (alt: GCT USB4105-GF-A, 2073-USB4105-GF-ACT-ND)', 'C165948', 'Extended',
     'Shell pegs need drilled holes on a Viagrid.'),
    ('USB-A port', 'USB_A', 'TE 292303-7 USB-A receptacle, right angle, SMT signal pins',
     'NO (TH has generic THT 4-pin 90deg; different footprint)', 'LIKELY',
     'TE 292303-7', '(search LCSC)', 'Extended',
     'SMT signal pads keep the Viagrid build simple; only the 2 shell tabs need holes.'),
    ('EXT 5V', 'TerminalBlock', 'Screw terminal 2P 5.08 mm (KF301-2P)',
     'YES - Shopee TH, Lazada TH, Cybertice, MyArduino', 'YES', 'Phoenix 1935161 (277-1667-ND)', 'C474881',
     'Extended', 'THT: drill 2 holes, solder from the bottom.'),
    ('SS34', 'D_SMA', 'SS34 Schottky 3 A 40 V, SMA',
     'YES - Shopee TH (ships from Thailand)', 'YES', 'Vishay SSA34-E3/61T', 'C8678', 'Basic', ''),
    ('2A hold', 'Fuse', 'PTC resettable fuse 1812, 2 A hold',
     'YES - Shopee TH (PPTC kit incl. 1812)', 'YES', 'Littelfuse 1812L200/12DR', 'C315901', 'Extended', ''),
    ('22uF', 'C_1206', 'MLCC 22 uF 25 V X5R 1206',
     'LIKELY', 'YES', 'Samsung CL31A226KAHNNNE', 'C12891', 'Basic',
     'Per-port bulk. USB 2.0 asks for 120 uF per port; SY6280 soft-start limits inrush instead.'),
    ('100nF', 'C_0603', 'MLCC 100 nF 50 V X7R 0603', 'YES - Shopee TH (0603 kit)', 'YES',
     'Yageo CC0603KRX7R9BB104', 'C14663', 'Basic', ''),
    ('10uF', 'C_0805', 'MLCC 10 uF 25 V X5R 0805', 'YES - Lazada TH (0805 kit)', 'YES',
     'Samsung CL21A106KAYNNNC', 'C15850', 'Basic', ''),
    ('220uF', 'CP_Elec', 'Alu electrolytic 220 uF 10 V SMD 6.3x7.7 mm',
     'YES - Shopee TH (220u/16V 6.3x7.7), Lazada TH', 'YES', 'Panasonic EEE-FK1A221P (verify)',
     '(pick on LCSC)', 'Extended', 'Bulk on +5V_PORT.'),
    ('0R', 'R_0603', 'Resistor 0 R 0603 (jumper over USB-C D- trace)', KIT, 'YES', 'generic',
     'C21189', 'Basic', 'Board jumper: USB-C D+ pads are interleaved with D-.'),
    ('5.1k', 'R_0603', 'Resistor 5.1 k 1% 0603', KIT, 'YES', 'generic', 'C23186', 'Basic', 'USB-C CC'),
    ('10k', 'R_0603', 'Resistor 10 k 1% 0603', KIT, 'YES', 'generic', 'C25804', 'Basic',
     'ISET: 10k = ~0.68 A limit; 6.8k (C23212) = ~1 A.'),
    ('1k', 'R_0603', 'Resistor 1 k 1% 0603', KIT, 'YES', 'generic', 'C21190', 'Basic', ''),
    ('2.7k 1%', 'R_0603', 'Resistor 2.7 k 1% 0603 (FE1.1s REXT)', KIT, 'YES', 'generic',
     'C13167', 'Basic', 'Must be 1%.'),
    ('100k', 'R_0603', 'Resistor 100 k 1% 0603', KIT, 'YES', 'generic', 'C25803', 'Basic', ''),
    ('56k', 'R_0603', 'Resistor 56 k 1% 0603', KIT, 'YES', 'generic', 'C23206', 'Basic',
     'VBUSM divider top (also drives XRSTJ/BUSJ).'),
    ('LED_green', 'LED_0805', 'LED green 0805', 'YES - Shopee TH, Lazada TH (0805 colour kits)', 'YES',
     'Lite-On LTST-C171GKT', 'C2297', 'Basic', ''),
    ('BOOT', 'TS-1187A', 'Tactile switch 5.1x5.1 mm SMD (XKB TS-1187A-B-A-B)',
     'NO (only 3x4 / 4.5x4.5 / 6x6 seen)', 'YES',
     'C&K PTS810 SJM 250 SMTR LFS', 'C318884', 'Basic', 'Hold while plugging in = CH552 bootloader.'),
]

EXTRAS = [
    # things that are not on the schematic but needed to build it
    dict(refs='-', qty=1, part='Viagrid 9055 Standard blank (90x55 mm, 2-layer, ENIG)',
         shopee='NO', ali='NO', digikey='NO', lcsc='-', jlc='-',
         notes='Opulo (opulo.io), or have JLCPCB/PCBWay make it from the open-source Viagrid files.'),
    dict(refs='-', qty=1, part='Enclosure Hammond 1591XXB (optional)',
         shopee='NO (generic ABS boxes only)', ali='LIKELY (clones)', digikey='HM1038-ND (1591XXBBK)',
         lcsc='-', jlc='-', notes='TME Thailand lists Hammond (ships from abroad).'),
]


def lookup(value, fp):
    for row in SRC:
        if row[0] == value and row[1] in fp:
            return row
    raise KeyError(f'no sourcing entry for {value} / {fp}')


def _refkey(r):
    import re
    m = re.match(r'([A-Z#]+)(\d+)', r)
    return (m.group(1), int(m.group(2))) if m else (r, 0)


def write(parts, outdir):
    lines = OrderedDict()
    for p in parts:
        if p['ref'].startswith('#'):
            continue
        row = lookup(p['value'], p['footprint'])
        key = (row[0], row[1], p['dnp'])
        lines.setdefault(key, dict(row=row, refs=[], footprint=p['footprint'], dnp=p['dnp']))
        lines[key]['refs'].append(p['ref'])
    order = ['U', 'Y', 'J', 'SW', 'F', 'D', 'C', 'R']

    def cat(ln):
        r = min(ln['refs'], key=_refkey)
        pre = _refkey(r)[0]
        return (ln['dnp'], order.index(pre) if pre in order else 99, _refkey(r))
    out = []
    for i, ln in enumerate(sorted(lines.values(), key=cat), 1):
        v, _, part, sl, ali, dk, lcsc, jlc, notes = ln['row']
        refs = sorted(ln['refs'], key=_refkey)
        out.append(dict(line=i, refs=' '.join(refs), qty=len(refs), part=part,
                        footprint=ln['footprint'].split(':')[-1],
                        shopee=sl, ali=ali, digikey=dk, lcsc=lcsc, jlc=jlc,
                        notes=('DNP. ' if ln['dnp'] else '') + notes))
    for e in EXTRAS:
        out.append(dict(line=len(out) + 1, footprint='-', **e))

    cols = ['line', 'refs', 'qty', 'part', 'footprint', 'shopee', 'ali', 'digikey', 'lcsc', 'jlc', 'notes']
    heads = ['#', 'Refs', 'Qty', 'Part', 'Footprint', 'Shopee / Lazada (Thailand)', 'AliExpress', 'DigiKey',
             'JLCPCB (LCSC #)', 'JLC type', 'Notes']
    with open(os.path.join(outdir, 'bom.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(heads)
        for r in out:
            w.writerow([r[c] for c in cols])

    def yes(s):
        return s.startswith('YES')
    n = len(out)
    sl_yes = sum(yes(r['shopee']) for r in out)
    sl_likely = sum(r['shopee'].startswith('LIKELY') for r in out)
    jlc_basic = sum(r['jlc'] == 'Basic' for r in out)
    jlc_ext = sum(r['jlc'] == 'Extended' for r in out)
    with open(os.path.join(outdir, 'bom.md'), 'w') as f:
        f.write('# YKUSH-VG bill of materials\n\n')
        f.write('Generated by `tools/make_schematic.py` + `tools/bom.py`. Sourcing checked 2026-09-24 '
                'from search listings; confirm price and stock before ordering.\n\n')
        f.write(f'- **{n} BOM lines**, {sum(r["qty"] for r in out)} parts in total.\n')
        f.write(f'- **Shopee/Lazada Thailand:** {sl_yes} lines seen listed, {sl_likely} likely (commodity, '
                f'no exact listing seen), {n - sl_yes - sl_likely} not found in Thailand '
                '(AliExpress/LCSC instead). Many IC listings are cross-border sellers: allow 1-2 weeks.\n')
        f.write(f'- **JLCPCB:** {jlc_basic} lines are Basic parts, {jlc_ext} are Extended '
                '(about $3 setup fee each for assembly).\n')
        f.write('- **DigiKey:** does not carry the Chinese ICs (FE1.1s, CH552G, SY6280AAC); '
                'alternatives are listed but change the circuit.\n\n')
        f.write('| ' + ' | '.join(heads) + ' |\n')
        f.write('|' + '---|' * len(heads) + '\n')
        for r in out:
            f.write('| ' + ' | '.join(str(r[c]).replace('|', '/') for c in cols) + ' |\n')
    return out
