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
# WIP: CH552G / SY6280AAC pin numbers below are PLACEHOLDERS pending datasheet check.
CH552G = custom_ic(
    'ykush_vg:CH552G',
    pins_left=[('10', 'P3.6/UDP', 'bidirectional'),
               ('11', 'P3.7/UDM', 'bidirectional'),
               ('6', 'RST/P5.7', 'input'),
               ('16', 'VCC', 'power_in'),
               ('15', 'V33', 'passive'),
               ('14', 'GND', 'power_in')],
    pins_right=[('1', 'P3.2', 'bidirectional'),
                ('2', 'P1.4', 'bidirectional'),
                ('3', 'P1.5', 'bidirectional'),
                ('4', 'P1.6', 'bidirectional'),
                ('5', 'P1.7', 'bidirectional'),
                ('7', 'P3.1/TXD', 'bidirectional'),
                ('8', 'P3.0/RXD', 'bidirectional'),
                ('9', 'P1.1', 'bidirectional'),
                ('12', 'P3.3', 'bidirectional'),
                ('13', 'P3.4', 'bidirectional')],
    footprint='Package_SO:SOIC-16_3.9x9.9mm_P1.27mm', value='CH552G',
    desc='WCH CH552G 8051 MCU with USB device, SOP-16')

SY6280 = custom_ic(
    'ykush_vg:SY6280AAC',
    pins_left=[('5', 'IN', 'power_in'), ('4', 'EN', 'input'), ('3', 'ISET', 'passive')],
    pins_right=[('1', 'OUT', 'power_out'), ('2', 'GND', 'power_in')],
    footprint='Package_TO_SOT_SMD:SOT-23-5', value='SY6280AAC',
    desc='Silergy SY6280AAC current-limited load switch, SOT-23-5')
