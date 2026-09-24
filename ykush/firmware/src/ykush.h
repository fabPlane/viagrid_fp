/* YKUSH command protocol (as spoken by Yepkit's ykushcmd, PID 0xF2F7 boards).
 *
 * Every request and reply is a 64-byte HID report without report ID.
 *   0x11..0x13  port N on          reply [0x01, cmd]
 *   0x1A        all ports on       reply [0x01, cmd]
 *   0x01..0x03  port N off         reply [0x01, cmd]
 *   0x0A        all ports off      reply [0x01, cmd]
 *   0x21..0x23  port N status      reply [0x01, (on << 4) | N]
 * YKUSH-VG extensions (ignored by ykushcmd):
 *   0x2A        all ports status   reply [0x01, bit0..2 = port 1..3 on]
 *   0xB0        reboot into the CH552 USB bootloader, for reflashing without the button
 * Anything else                    reply [0x00]
 * This file is plain C with no hardware access so it can be unit-tested on the host.
 */
#ifndef YKUSH_H
#define YKUSH_H

#include <stdint.h>

#define YK_REPORT_SIZE 64
#define YK_NUM_PORTS   3

#define YK_ACT_NONE        0
#define YK_ACT_BOOTLOADER  1

/* provided by the board layer: port is 1..YK_NUM_PORTS */
void board_port_set(uint8_t port, uint8_t on);
uint8_t board_port_get(uint8_t port);

/* Fill resp (YK_REPORT_SIZE bytes) for request req; returns a YK_ACT_* follow-up action. */
uint8_t ykush_handle(const uint8_t *req, uint8_t *resp);

#endif
