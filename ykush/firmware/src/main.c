/* YKUSH-VG firmware for the CH552G on the Viagrid 3-port switchable hub.
 *
 * Speaks the YKUSH HID protocol (see ykush.h) with the YKUSH USB IDs, so Yepkit's
 * ykushcmd works unchanged:  ykushcmd -d 2   (port 2 off)   ykushcmd -u a   (all on)
 */
#include <stdint.h>
#include "ch554.h"
#include "usb.h"         /* must be visible here: declares the USB interrupt vector */
#include "board.h"
#include "ykush.h"

static __xdata uint8_t reply[YK_REPORT_SIZE];

void main(void)
{
    uint8_t i, act, blink = 0;

    board_init();
    usb_init();
    EA = 1;

#if PORTS_ON_AT_BOOT
    /* staggered so three devices do not hit the supply at once */
    for (i = 1; i <= YK_NUM_PORTS; i++) {
        delay_ms(PORT_STAGGER_MS);
        board_port_set(i, 1);
    }
#endif

    for (;;) {
        if (usb_rx_ready) {
            act = ykush_handle(usb_rx, reply);
            usb_reply(reply);
            blink = 30;
            if (act == YK_ACT_BOOTLOADER) {
                delay_ms(50);           /* give the host time to read the reply */
                board_enter_bootloader();
            }
        }
        /* LED: on while configured by the host, a short blink on every command */
        if (blink) {
            PIN_LED = 0;
            delay_ms(1);
            blink--;
        } else {
            PIN_LED = usb_configured ? 1 : 0;
        }
    }
}
