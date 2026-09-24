/* YKUSH-VG board pins (see ../../kicad/ykush_vg.kicad_sch).
 * EN pins drive the SY6280AAC enables (active high, 100k pull-down on the board). */
#ifndef BOARD_H
#define BOARD_H

#include <stdint.h>
#include "ch554.h"

SBIT(PIN_EN1, 0x90, 4);     /* P1.4 -> port 1 (J2, left)   */
SBIT(PIN_EN2, 0xB0, 3);     /* P3.3 -> port 2 (J3, middle) */
SBIT(PIN_EN3, 0xB0, 4);     /* P3.4 -> port 3 (J4, right)  */
SBIT(PIN_LED, 0xB0, 2);     /* P3.2 -> status LED, active high */

#ifndef PORTS_ON_AT_BOOT
#define PORTS_ON_AT_BOOT 1  /* like a YKUSH: ports power up on, one after another */
#endif
#define PORT_STAGGER_MS  100

void board_init(void);
void delay_ms(uint16_t ms);
void board_enter_bootloader(void);

#endif
