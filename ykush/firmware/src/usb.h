/* Minimal full-speed USB HID device for the CH552: one vendor-defined HID interface with
 * 64-byte interrupt IN (0x81) and OUT (0x01) reports, which is what ykushcmd looks for. */
#ifndef USB_H
#define USB_H

#include <stdint.h>

#ifndef USB_VID
#define USB_VID 0x04D8      /* the IDs YKUSH boards use, so ykushcmd finds this one */
#endif
#ifndef USB_PID
#define USB_PID 0xF2F7
#endif

extern volatile uint8_t usb_configured;
extern volatile uint8_t usb_rx_ready;           /* a report is waiting in usb_rx */
extern __xdata uint8_t usb_rx[64];

void usb_init(void);
/* queue a 64-byte reply on the interrupt IN endpoint and accept the next request */
void usb_reply(const uint8_t *report);
void usb_isr(void) __interrupt(INT_NO_USB);

#endif
