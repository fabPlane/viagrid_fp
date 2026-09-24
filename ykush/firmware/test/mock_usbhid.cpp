// Stand-in for ykushcmd's src/usbhid/usbhid.cpp (Linux/libusb build): instead of USB,
// every HID report goes to the YKUSH-VG firmware's protocol handler (src/ykush.c).
// Port state lives in a file so it survives between ykushcmd invocations.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "usbhid.h"

// from the firmware's src/ykush.h (not included: ykushcmd has its own ykush.h)
#define YK_REPORT_SIZE 64
#define YK_NUM_PORTS 3
extern "C" uint8_t ykush_handle(const uint8_t *req, uint8_t *resp);

static const char *state_file() { const char *p = getenv("YKVG_STATE"); return p ? p : "/tmp/ykvg_state"; }
static unsigned char st[YK_NUM_PORTS + 1];
static void load() { FILE *f = fopen(state_file(), "rb"); if (f) { fread(st, 1, sizeof st, f); fclose(f); } }
static void save() { FILE *f = fopen(state_file(), "wb"); if (f) { fwrite(st, 1, sizeof st, f); fclose(f); } }
extern "C" void board_port_set(uint8_t port, uint8_t on) { st[port] = on; }
extern "C" uint8_t board_port_get(uint8_t port) { return st[port]; }

static unsigned char resp[YK_REPORT_SIZE];

UsbHid::UsbHid() {}

struct hid_device_info *UsbHid::enumerate(unsigned int vid, unsigned int pid)
{
    if (vid != 0x04D8 || pid != 0xF2F7)
        return NULL;
    struct hid_device_info *d = (struct hid_device_info *)calloc(1, sizeof *d);
    d->serial_number_ascii = strdup("VG12345678");
    return d;
}

void UsbHid::free_enumeration(struct hid_device_info *d)
{
    free(d->serial_number_ascii);
    free(d);
}

int UsbHid::open(unsigned int vid, unsigned int pid, char *serial)
{
    if (vid != 0x04D8 || pid != 0xF2F7)
        return -1;
    if (serial && strcmp(serial, "VG12345678") != 0)
        return -1;
    load();
    return 0;
}

void UsbHid::close(void) { save(); }

int UsbHid::write(unsigned char *data, size_t length)
{
    unsigned char req[YK_REPORT_SIZE] = {0};
    memcpy(req, data, length < sizeof req ? length : sizeof req);
    ykush_handle(req, resp);
    return (int)length;
}

int UsbHid::read(unsigned char *data, int length)
{
    memcpy(data, resp, length < YK_REPORT_SIZE ? length : YK_REPORT_SIZE);
    return length;
}
