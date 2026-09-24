#include "ykush.h"

uint8_t ykush_handle(const uint8_t *req, uint8_t *resp)
{
    uint8_t cmd = req[0];
    uint8_t op = cmd >> 4;
    uint8_t arg = cmd & 0x0F;
    uint8_t i;

    for (i = 0; i < YK_REPORT_SIZE; i++)
        resp[i] = 0;

    if (cmd == 0xB0) {
        resp[0] = 0x01;
        resp[1] = cmd;
        return YK_ACT_BOOTLOADER;
    }

    switch (op) {
    case 0x0:                       /* port off */
    case 0x1:                       /* port on  */
        if (arg >= 1 && arg <= YK_NUM_PORTS) {
            board_port_set(arg, op);
        } else if (arg == 0x0A) {
            for (i = 1; i <= YK_NUM_PORTS; i++)
                board_port_set(i, op);
        } else {
            return YK_ACT_NONE;     /* resp[0] = 0: rejected */
        }
        resp[0] = 0x01;
        resp[1] = cmd;
        break;
    case 0x2:                       /* status */
        if (arg >= 1 && arg <= YK_NUM_PORTS) {
            resp[0] = 0x01;
            resp[1] = (uint8_t)((board_port_get(arg) ? 0x10 : 0x00) | arg);
        } else if (arg == 0x0A) {
            resp[0] = 0x01;
            for (i = 1; i <= YK_NUM_PORTS; i++)
                if (board_port_get(i))
                    resp[1] |= (uint8_t)(1 << (i - 1));
        }
        break;
    default:
        break;
    }
    return YK_ACT_NONE;
}
