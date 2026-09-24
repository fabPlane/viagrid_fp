"""Generate the YKUSH-VG schematic (KiCad 7 format) plus a BOM/netlist summary.

Run:  python3 make_schematic.py      (writes ../kicad/ykush_vg.kicad_sch)
Then: kicad-cli sch erc ../kicad/ykush_vg.kicad_sch
"""
import csv
import os

from schgen import Sheet, custom_ic

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'kicad')

R0603 = 'Resistor_SMD:R_0603_1608Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
CAP_EL = 'Capacitor_SMD:CP_Elec_6.3x7.7'
LED0603 = 'LED_SMD:LED_0603_1608Metric'

sh = Sheet('ykush_vg', 'YKUSH-VG: 3-port switchable USB 2.0 hub on Viagrid 9055')

# ---------------------------------------------------------------- custom symbols
# CH552G pinout: WCH CH552 datasheet v1E, SOP16 column (cross-checked vs wagiminator
# CH552-MacroPad-plus schematic).
CH552G = custom_ic(
    'ykush_vg:CH552G',
    pins_left=[('12', 'P3.6/UDP', 'bidirectional'),
               ('13', 'P3.7/UDM', 'bidirectional'),
               ('6', 'RST', 'input'),
               ('15', 'VCC', 'power_in'),
               ('16', 'V33', 'passive'),
               ('14', 'GND', 'power_in')],
    pins_right=[('1', 'P3.2/INT0', 'bidirectional'),
                ('2', 'P1.4', 'bidirectional'),
                ('3', 'P1.5', 'bidirectional'),
                ('4', 'P1.6', 'bidirectional'),
                ('5', 'P1.7', 'bidirectional'),
                ('7', 'P3.1/TXD', 'bidirectional'),
                ('8', 'P3.0/RXD', 'bidirectional'),
                ('9', 'P1.1', 'bidirectional'),
                ('10', 'P3.3', 'bidirectional'),
                ('11', 'P3.4', 'bidirectional')],
    footprint='Package_SO:SOIC-16_3.9x9.9mm_P1.27mm', value='CH552G',
    desc='WCH CH552G 8051 MCU with USB device, SOP-16')

# SY6280AAC pinout: Silergy AN_SY6280 datasheet (cross-checked vs OLIMEX netlist).
# No FLG pin. EN active high, must not float. I_LIM = 6800 / R_SET.
SY6280 = custom_ic(
    'ykush_vg:SY6280AAC',
    pins_left=[('5', 'IN', 'power_in'), ('4', 'EN', 'input'), ('3', 'ISET', 'passive')],
    pins_right=[('1', 'OUT', 'power_out'), ('2', 'GND', 'power_in')],
    footprint='Package_TO_SOT_SMD:SOT-23-5', value='SY6280AAC',
    desc='Silergy SY6280AAC current-limited load switch, SOT-23-5')

sh.lib('ykush_vg:CH552G', CH552G)
sh.lib('ykush_vg:SY6280AAC', SY6280)

# ---------------------------------------------------------------- helpers
_n = {'U': 3}  # U1-U3 are placed by hand below


def ref(prefix):
    _n[prefix] = _n.get(prefix, 0) + 1
    return f'{prefix}{_n[prefix]}'


def R(value, a, b, at, **kw):
    sh.add(ref('R'), 'Device:R', value, at, {'1': a, '2': b}, R0603, **kw)


def C(value, a, b, at, fp=None, **kw):
    lib = 'Device:C_Polarized' if fp == CAP_EL else 'Device:C'
    fp = fp or (C0805 if value in ('10uF',) else C0603)
    sh.add(ref('C'), lib, value, at, {'1': a, '2': b}, fp, **kw)


def LED(net_a, net_k, at, value='LED_green'):
    sh.add(ref('D'), 'Device:LED', value, at, {'2': net_a, '1': net_k}, LED0603)


def column(x, y0, dy=20.32):
    """Yield successive positions going down a column."""
    y = y0
    while True:
        yield (x, y)
        y += dy


# ================================================================= UPSTREAM
sh.text('UPSTREAM USB-C (device/UFP) + ESD', (20, 20))
sh.add('J1', 'Connector:USB_C_Receptacle_USB2.0_16P', 'USB-C 16P', (40, 60),
       {'A1': 'GND', 'A4': 'VBUS_UP', 'A5': 'CC1', 'A6': 'UP_DP', 'A7': 'UP_DM',
        'B5': 'CC2', 'S1': 'GND', 'A9': 'VBUS_UP', 'A12': 'GND', 'B1': 'GND', 'B4': 'VBUS_UP',
        'B6': 'UP_DP', 'B7': 'UP_DM', 'B9': 'VBUS_UP', 'B12': 'GND'},
       'Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12', nc=('A8', 'B8'))
col = column(95, 40)
R('5.1k', 'CC1', 'GND', next(col))
R('5.1k', 'CC2', 'GND', next(col))
C('10uF', 'VBUS_UP', 'GND', next(col))
sh.add('U2', 'Power_Protection:USBLC6-2SC6', 'USBLC6-2SC6', (60, 110),
       {'1': 'UP_DP', '6': 'UP_DP', '3': 'UP_DM', '4': 'UP_DM', '5': 'VBUS_UP', '2': 'GND'},
       'Package_TO_SOT_SMD:SOT-23-6')
sh.flag('VBUS_UP', (125, 40))
sh.flag('GND', (140, 40))

# ================================================================= POWER PATH
sh.text('POWER: downstream rail +5V_PORT = VBUS_UP or EXT_5V (diode-OR)', (20, 140))
sh.add('J5', 'Connector:Screw_Terminal_01x02', 'EXT 5V', (40, 165),
       {'1': 'EXT_5V_IN', '2': 'GND'}, 'TerminalBlock:TerminalBlock_bornier-2_P5.08mm')
sh.add('F1', 'Device:Polyfuse', '2A hold', (70, 165), {'1': 'EXT_5V_IN', '2': 'EXT_5V'},
       'Fuse:Fuse_1812_4532Metric')
sh.add(ref('D'), 'Device:D_Schottky', 'SS34', (100, 160), {'2': 'EXT_5V', '1': '+5V_PORT'}, 'Diode_SMD:D_SMA')
sh.add(ref('D'), 'Device:D_Schottky', 'SS34', (100, 180), {'2': 'VBUS_UP', '1': '+5V_PORT'}, 'Diode_SMD:D_SMA')
C('150uF', '+5V_PORT', 'GND', (130, 165), fp=CAP_EL)
R('1k', '+5V_PORT', 'LED_PWR', (150, 160))
LED('LED_PWR', 'GND', (150, 180))
sh.flag('EXT_5V_IN', (70, 185))
sh.flag('+5V_PORT', (130, 185))

# ================================================================= HUB
sh.text('HUB: Terminus FE1.1s (SSOP-28, 0.635mm). No crystal load caps (internal).', (190, 20))
sh.add('U1', 'Interface_USB:FE1.1s', 'FE1.1s', (240, 75),
       {'1': 'GND', '2': 'XOUT', '3': 'XIN',
        '4': 'MCU_DM', '5': 'MCU_DP',   # port 4 -> CH552 (control HID device)
        '6': 'P3_DM', '7': 'P3_DP', '8': 'P2_DM', '9': 'P2_DP', '10': 'P1_DM', '11': 'P1_DP',
        '12': '+1V8', '13': '+3V3', '14': 'REXT', '15': 'UP_DM', '16': 'UP_DP',
        '17': 'HUB_RSTJ', '18': 'VBUSM', '19': 'BUSJ', '20': 'VBUS_UP', '21': '+3V3',
        '22': 'HUB_DRV', '26': '+3V3', '28': '+1V8'},
       'Package_SO:SSOP-28_3.9x9.9mm_P0.635mm', nc=('23', '24', '25', '27'))
sh.add('Y1', 'Device:Crystal_GND24', '12MHz', (240, 125),
       {'1': 'XIN', '3': 'XOUT', '2': 'GND', '4': 'GND'}, 'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm')
col = column(300, 35)
C('10uF', 'VBUS_UP', 'GND', next(col))    # VDD5
C('10uF', '+3V3', 'GND', next(col))       # VD33_O
C('100nF', '+3V3', 'GND', next(col))      # VD33
C('10uF', '+1V8', 'GND', next(col))       # VD18_O
C('100nF', '+1V8', 'GND', next(col))      # VD18
R('2.7k 1%', 'REXT', 'GND', next(col))
col = column(330, 35)
R('100k', '+3V3', 'HUB_RSTJ', next(col))
C('100nF', 'HUB_RSTJ', 'GND', next(col))
R('47k', 'VBUS_UP', 'VBUSM', next(col))
R('100k', 'VBUSM', 'GND', next(col))
C('100nF', 'VBUSM', 'GND', next(col))
R('100k', '+3V3', 'BUSJ', next(col))      # self-powered
R('330', 'HUB_DRV', 'LED_HUB', next(col))
LED('LED_HUB', 'GND', next(col))

# ================================================================= MCU
sh.text('CONTROL: WCH CH552G on hub port 4, always powered from VBUS_UP.', (190, 205))
sh.text('Boot: hold SW1 while plugging in, or jump to bootloader from firmware.', (190, 211), 1.4)
sh.add('U3', 'ykush_vg:CH552G', 'CH552G', (250, 250),
       {'12': 'MCU_DP', '13': 'MCU_DM', '6': 'MCU_RST', '15': 'VBUS_UP', '16': 'V33_MCU', '14': 'GND',
        '1': 'LED_STAT', '2': 'MCU_P14', '3': 'MCU_P15', '4': 'MCU_P16', '5': 'MCU_P17',
        '7': 'MCU_TXD', '9': 'EN1', '10': 'EN2', '11': 'EN3'},
       nc=('8',))
col = column(310, 230)
C('100nF', 'VBUS_UP', 'GND', next(col))
C('10uF', 'VBUS_UP', 'GND', next(col))
C('100nF', 'V33_MCU', 'GND', next(col))
sh.add('SW1', 'Switch:SW_Push', 'BOOT', next(col), {'1': 'V33_MCU', '2': 'BOOT_R'},
       'Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A')
R('10k', 'BOOT_R', 'MCU_DP', next(col))
col = column(340, 230)
R('1k', 'LED_STAT', 'LED_STAT_A', next(col))
LED('LED_STAT_A', 'GND', next(col))
sh.add('J6', 'Connector_Generic:Conn_01x08', 'PROG/DEBUG', (250, 300),
       {'1': 'VBUS_UP', '2': 'GND', '3': 'MCU_RST', '4': 'MCU_P14', '5': 'MCU_P15',
        '6': 'MCU_P16', '7': 'MCU_P17', '8': 'MCU_TXD'},
       'Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical')

# ================================================================= PORTS
sh.text('DOWNSTREAM PORTS: SY6280AAC per port, I_LIM = 6800/R_SET (10k -> ~0.68 A)', (390, 20))
for i in (1, 2, 3):
    y = 30 + (i - 1) * 85
    vb = f'VBUS_P{i}'
    sh.add(ref('U'), 'ykush_vg:SY6280AAC', 'SY6280AAC', (420, y + 25),
           {'5': '+5V_PORT', '4': f'EN{i}', '3': f'ISET{i}', '1': vb, '2': 'GND'})
    R('10k', f'ISET{i}', 'GND', (400, y + 50))
    R('100k', f'EN{i}', 'GND', (415, y + 50))    # keep port off while MCU boots
    C('10uF', '+5V_PORT', 'GND', (430, y + 50))
    C('150uF', vb, 'GND', (460, y + 50), fp=CAP_EL)
    C('10uF', vb, 'GND', (475, y + 50))
    R('1k', vb, f'LED_P{i}', (490, y + 50))
    LED(f'LED_P{i}', 'GND', (505, y + 50))
    sh.add(f'J{i + 1}', 'Connector:USB_A', f'USB-A port {i}', (540, y + 20),
           {'1': vb, '2': f'P{i}_DM', '3': f'P{i}_DP', '4': 'GND', '5': 'GND'},
           'Connector_USB:USB_A_Molex_67643_Horizontal')
    sh.add(ref('U'), 'Power_Protection:USBLC6-2SC6', 'USBLC6-2SC6', (480, y + 15),
           {'1': f'P{i}_DP', '6': f'P{i}_DP', '3': f'P{i}_DM', '4': f'P{i}_DM', '5': vb, '2': 'GND'},
           'Package_TO_SOT_SMD:SOT-23-6')

os.makedirs(OUT, exist_ok=True)
sh.write(os.path.join(OUT, 'ykush_vg.kicad_sch'))
with open(os.path.join(OUT, 'nets.txt'), 'w') as f:
    for net, nodes in sorted(sh.nets().items()):
        f.write(f'{net}: {" ".join(sorted(nodes))}\n')
print('parts', len([p for p in sh.parts if not p['ref'].startswith('#')]))
