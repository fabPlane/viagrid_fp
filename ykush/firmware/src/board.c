#include <stdint.h>
#include "ch554.h"
#include "board.h"
#include "ykush.h"

static uint8_t port_state;      /* bit n-1 = port n on */

void board_port_set(uint8_t port, uint8_t on)
{
    uint8_t mask = (uint8_t)(1 << (port - 1));
    if (on)
        port_state |= mask;
    else
        port_state &= (uint8_t)~mask;
    switch (port) {
    case 1: PIN_EN1 = on ? 1 : 0; break;
    case 2: PIN_EN2 = on ? 1 : 0; break;
    case 3: PIN_EN3 = on ? 1 : 0; break;
    default: break;
    }
}

uint8_t board_port_get(uint8_t port)
{
    return (port_state >> (port - 1)) & 1;
}

/* Timer0 in mode 1 counts Fsys/12 = 2 MHz at 24 MHz: 2000 ticks per millisecond. */
void delay_ms(uint16_t ms)
{
    while (ms--) {
        TR0 = 0;
        TH0 = (uint8_t)((65536 - 2000) >> 8);
        TL0 = (uint8_t)((65536 - 2000) & 0xFF);
        TF0 = 0;
        TR0 = 1;
        while (!TF0)
            ;
    }
    TR0 = 0;
}

void board_init(void)
{
    /* system clock 24 MHz from the internal oscillator (needs VCC = 5 V, which we have) */
    SAFE_MOD = 0x55;
    SAFE_MOD = 0xAA;
    CLOCK_CFG = CLOCK_CFG & ~MASK_SYS_CK_SEL | 0x06;
    SAFE_MOD = 0x00;

    /* EN1 = P1.4; EN2/EN3/LED = P3.3/P3.4/P3.2: push-pull outputs, all low (ports off) */
    PIN_EN1 = 0;
    PIN_EN2 = 0;
    PIN_EN3 = 0;
    PIN_LED = 0;
    P1_MOD_OC &= (uint8_t)~(1 << 4);
    P1_DIR_PU |= (uint8_t)(1 << 4);
    P3_MOD_OC &= (uint8_t)~((1 << 2) | (1 << 3) | (1 << 4));
    P3_DIR_PU |= (uint8_t)((1 << 2) | (1 << 3) | (1 << 4));
    port_state = 0;

    /* Timer0: 16-bit mode, clocked at Fsys/12 (T2MOD bT0_CLK = 0) */
    TMOD = TMOD & 0xF0 | 0x01;
    T2MOD &= (uint8_t)~bT0_CLK;

    delay_ms(5);        /* let the clock settle after the switch */
}

void board_enter_bootloader(void)
{
    EA = 0;
    USB_CTRL = 0;       /* detach so the host re-enumerates the bootloader */
    UDEV_CTRL = 0;
    delay_ms(100);
    __asm
        ljmp 0x3800
    __endasm;
}
