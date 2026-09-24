/* Host-side tests of the YKUSH protocol handler, checked the way ykushcmd reads replies
 * (ykushcmd/src/ykush/ykush.cpp: resp[0] == 0x01 is success, status is resp[1]). */
#include <stdio.h>
#include <string.h>
#include "ykush.h"

static unsigned char ports[YK_NUM_PORTS + 1];
void board_port_set(uint8_t port, uint8_t on) { ports[port] = on; }
uint8_t board_port_get(uint8_t port) { return ports[port]; }

static int fails;
#define CHECK(c, msg) do { if (!(c)) { printf("FAIL: %s\n", msg); fails++; } } while (0)

static uint8_t req[64], resp[64];

static uint8_t send(uint8_t cmd)
{
    memset(req, 0, sizeof req);
    req[0] = cmd;
    memset(resp, 0xEE, sizeof resp);
    return ykush_handle(req, resp);
}

/* what `ykushcmd -g N` prints */
static int status_on(char port)
{
    send((uint8_t)(0x20 | (port - '0')));
    return resp[0] == 0x01 ? (resp[1] >> 4) : -1;
}

int main(void)
{
    int p;
    char name[64];

    /* ykushcmd -u N / -d N for each port */
    for (p = 1; p <= 3; p++) {
        send((uint8_t)(0x10 | p));
        snprintf(name, sizeof name, "up %d acknowledged", p);
        CHECK(resp[0] == 0x01, name);
        CHECK(ports[p] == 1, "port switched on");
        CHECK(status_on((char)('0' + p)) == 1, "status reports on");
        send((uint8_t)(0x20 | p));
        CHECK((resp[1] & 0x0F) == p, "status echoes the port number");

        send((uint8_t)p);
        snprintf(name, sizeof name, "down %d acknowledged", p);
        CHECK(resp[0] == 0x01, name);
        CHECK(ports[p] == 0, "port switched off");
        CHECK(status_on((char)('0' + p)) == 0, "status reports off");
    }

    /* ykushcmd -u a / -d a */
    send(0x1A);
    CHECK(resp[0] == 0x01 && ports[1] && ports[2] && ports[3], "all on");
    send(0x2A);
    CHECK(resp[0] == 0x01 && resp[1] == 0x07, "all-status bitmask");
    send(0x0A);
    CHECK(resp[0] == 0x01 && !ports[1] && !ports[2] && !ports[3], "all off");

    /* port 2 only must not touch 1 and 3 */
    send(0x12);
    CHECK(!ports[1] && ports[2] && !ports[3], "only port 2 on");

    /* invalid requests are rejected and change nothing */
    send(0x14);
    CHECK(resp[0] == 0x00 && !ports[1] && ports[2] && !ports[3], "port 4 rejected");
    send(0x00);
    CHECK(resp[0] == 0x00, "cmd 0x00 rejected");
    send(0x24);
    CHECK(resp[0] == 0x00, "status of port 4 rejected");
    send(0x55);
    CHECK(resp[0] == 0x00, "unknown command rejected");

    /* reply is always a full, zero-padded report */
    send(0x11);
    for (p = 2; p < 64; p++)
        CHECK(resp[p] == 0, "reply zero padded");

    /* bootloader request */
    CHECK(send(0xB0) == YK_ACT_BOOTLOADER && resp[0] == 0x01, "bootloader command");
    CHECK(send(0x11) == YK_ACT_NONE, "normal commands do not reboot");

    if (fails) {
        printf("%d check(s) failed\n", fails);
        return 1;
    }
    printf("all YKUSH protocol checks passed\n");
    return 0;
}
