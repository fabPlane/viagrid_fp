/* USB device stack for the CH552 (full speed, one HID interface).
 * Written for YKUSH-VG; the register usage follows the WCH CH552 datasheet. */
#include <stdint.h>
#include "ch554.h"
#include "ch554_usb.h"
#include "usb.h"

#define EP0_SIZE 64

/* DMA buffers must sit at even xdata addresses. EP1 uses OUT (64) + IN (64). */
__xdata __at (0x0000) uint8_t ep0_buf[EP0_SIZE];
__xdata __at (0x0040) uint8_t ep1_buf[128];
#define EP1_OUT  (ep1_buf)
#define EP1_IN   (ep1_buf + 64)
#define SETUP    ((PXUSB_SETUP_REQ)ep0_buf)

volatile uint8_t usb_configured;
volatile uint8_t usb_rx_ready;
__xdata uint8_t usb_rx[64];
static __xdata uint8_t last_reply[64];          /* also served on HID GET_REPORT */

/* ------------------------------------------------------------------ descriptors */
__code const uint8_t dev_desc[] = {
    18, USB_DESCR_TYP_DEVICE,
    0x00, 0x02,                 /* USB 2.0 */
    0x00, 0x00, 0x00,           /* class per interface */
    EP0_SIZE,
    USB_VID & 0xFF, USB_VID >> 8,
    USB_PID & 0xFF, USB_PID >> 8,
    0x00, 0x01,                 /* bcdDevice 1.00 */
    1, 2, 3,                    /* manufacturer, product, serial strings */
    1                           /* configurations */
};

__code const uint8_t report_desc[] = {
    0x06, 0x00, 0xFF,           /* usage page: vendor defined */
    0x09, 0x01,                 /* usage 1 */
    0xA1, 0x01,                 /* collection (application) */
    0x15, 0x00,                 /*   logical minimum 0 */
    0x26, 0xFF, 0x00,           /*   logical maximum 255 */
    0x75, 0x08,                 /*   report size 8 bits */
    0x95, 0x40,                 /*   report count 64 */
    0x09, 0x01, 0x81, 0x02,     /*   input (data, var, abs) */
    0x95, 0x40,
    0x09, 0x01, 0x91, 0x02,     /*   output (data, var, abs) */
    0xC0                        /* end collection */
};

#define CFG_LEN (9 + 9 + 9 + 7 + 7)
__code const uint8_t cfg_desc[CFG_LEN] = {
    9, USB_DESCR_TYP_CONFIG, CFG_LEN, 0, 1, 1, 0,
    0x80,                       /* bus powered */
    50,                         /* 100 mA */
    /* interface 0: HID, 2 endpoints */
    9, USB_DESCR_TYP_INTERF, 0, 0, 2, 0x03, 0x00, 0x00, 0,
    /* HID descriptor */
    9, USB_DESCR_TYP_HID, 0x11, 0x01, 0x00, 1, USB_DESCR_TYP_REPORT,
    sizeof(report_desc) & 0xFF, sizeof(report_desc) >> 8,
    /* endpoint 0x81 interrupt IN, 64 bytes, 1 ms */
    7, USB_DESCR_TYP_ENDP, 0x81, 0x03, 64, 0, 1,
    /* endpoint 0x01 interrupt OUT, 64 bytes, 1 ms */
    7, USB_DESCR_TYP_ENDP, 0x01, 0x03, 64, 0, 1,
};

static __code const uint8_t lang_desc[] = { 4, USB_DESCR_TYP_STRING, 0x09, 0x04 };
static __code const uint8_t manuf_desc[] = {
    22, USB_DESCR_TYP_STRING,
    'v', 0, 'i', 0, 'a', 0, 'g', 0, 'r', 0, 'i', 0, 'd', 0, '_', 0, 'f', 0, 'p', 0 };
static __code const uint8_t prod_desc[] = {
    18, USB_DESCR_TYP_STRING,
    'Y', 0, 'K', 0, 'U', 0, 'S', 0, 'H', 0, '-', 0, 'V', 0, 'G', 0 };
/* serial = "VG" + 8 hex digits of the chip's unique ID, built at start-up */
static __xdata uint8_t serial_desc[2 + 2 * 10];

static void build_serial(void)
{
    static __code const char hex[] = "0123456789ABCDEF";
    uint32_t id = *(__code uint16_t *)ROM_CHIP_ID_LO | ((uint32_t)*(__code uint16_t *)ROM_CHIP_ID_HI << 16);
    uint8_t i;
    serial_desc[0] = sizeof(serial_desc);
    serial_desc[1] = USB_DESCR_TYP_STRING;
    serial_desc[2] = 'V';
    serial_desc[4] = 'G';
    for (i = 0; i < 8; i++) {
        serial_desc[6 + 2 * i] = hex[(id >> (28 - 4 * i)) & 0x0F];
        serial_desc[7 + 2 * i] = 0;
    }
    serial_desc[3] = serial_desc[5] = 0;
}

/* ------------------------------------------------------------------ control transfers */
static uint8_t setup_req, setup_type;
static uint16_t setup_len;
static uint8_t new_addr;
static const uint8_t *desc_ptr;         /* generic pointer: code or xdata */

static uint8_t load_chunk(void)
{
    uint8_t n = setup_len > EP0_SIZE ? EP0_SIZE : (uint8_t)setup_len, i;
    for (i = 0; i < n; i++)
        ep0_buf[i] = desc_ptr[i];
    setup_len -= n;
    desc_ptr += n;
    return n;
}

#define STALL 0xFF

static uint8_t handle_setup(void)
{
    uint16_t dlen = 0;

    setup_len = ((uint16_t)SETUP->wLengthH << 8) | SETUP->wLengthL;
    setup_req = SETUP->bRequest;
    setup_type = SETUP->bRequestType;

    if ((setup_type & USB_REQ_TYP_MASK) == USB_REQ_TYP_CLASS) {
        switch (setup_req) {
        case HID_GET_REPORT:
            desc_ptr = last_reply;
            if (setup_len > 64) setup_len = 64;
            return load_chunk();
        case HID_SET_REPORT:            /* data arrives in the OUT stage */
        case HID_SET_IDLE:
        case HID_SET_PROTOCOL:
            return 0;
        case HID_GET_IDLE:
            ep0_buf[0] = 0;
            return 1;
        case HID_GET_PROTOCOL:
            ep0_buf[0] = 1;
            return 1;
        default:
            return STALL;
        }
    }
    if ((setup_type & USB_REQ_TYP_MASK) != USB_REQ_TYP_STANDARD)
        return STALL;

    switch (setup_req) {
    case USB_GET_DESCRIPTOR:
        switch (SETUP->wValueH) {
        case USB_DESCR_TYP_DEVICE: desc_ptr = dev_desc; dlen = sizeof(dev_desc); break;
        case USB_DESCR_TYP_CONFIG: desc_ptr = cfg_desc; dlen = sizeof(cfg_desc); break;
        case USB_DESCR_TYP_HID:    desc_ptr = cfg_desc + 18; dlen = 9; break;
        case USB_DESCR_TYP_REPORT: desc_ptr = report_desc; dlen = sizeof(report_desc); break;
        case USB_DESCR_TYP_STRING:
            switch (SETUP->wValueL) {
            case 0: desc_ptr = lang_desc; dlen = sizeof(lang_desc); break;
            case 1: desc_ptr = manuf_desc; dlen = sizeof(manuf_desc); break;
            case 2: desc_ptr = prod_desc; dlen = sizeof(prod_desc); break;
            case 3: desc_ptr = serial_desc; dlen = sizeof(serial_desc); break;
            default: return STALL;
            }
            break;
        default:
            return STALL;
        }
        if (setup_len > dlen)
            setup_len = dlen;
        return load_chunk();
    case USB_SET_ADDRESS:
        new_addr = SETUP->wValueL;
        return 0;
    case USB_GET_CONFIGURATION:
        ep0_buf[0] = usb_configured;
        return setup_len ? 1 : 0;
    case USB_SET_CONFIGURATION:
        usb_configured = SETUP->wValueL;
        return 0;
    case USB_GET_INTERFACE:
        ep0_buf[0] = 0;
        return setup_len ? 1 : 0;
    case USB_SET_INTERFACE:
        return 0;
    case USB_GET_STATUS:
        ep0_buf[0] = 0;
        ep0_buf[1] = 0;
        return setup_len >= 2 ? 2 : (uint8_t)setup_len;
    case USB_CLEAR_FEATURE:
        if ((setup_type & USB_REQ_RECIP_MASK) == USB_REQ_RECIP_ENDP) {
            if (SETUP->wIndexL == 0x81)
                UEP1_CTRL = UEP1_CTRL & ~(bUEP_T_TOG | MASK_UEP_T_RES) | UEP_T_RES_NAK;
            else if (SETUP->wIndexL == 0x01)
                UEP1_CTRL = UEP1_CTRL & ~(bUEP_R_TOG | MASK_UEP_R_RES) | UEP_R_RES_ACK;
            else
                return STALL;
            return 0;
        }
        return STALL;
    default:
        return STALL;
    }
}

void usb_isr(void) __interrupt(INT_NO_USB)
{
    uint8_t len, i;

    if (UIF_TRANSFER) {
        switch (USB_INT_ST & (MASK_UIS_TOKEN | MASK_UIS_ENDP)) {
        case UIS_TOKEN_OUT | 1:                 /* request report from the host */
            if (U_TOG_OK) {
                len = USB_RX_LEN;
                for (i = 0; i < 64; i++)
                    usb_rx[i] = i < len ? EP1_OUT[i] : 0;
                usb_rx_ready = 1;
                /* NAK further requests until the main loop has answered this one */
                UEP1_CTRL = UEP1_CTRL & ~MASK_UEP_R_RES | UEP_R_RES_NAK;
            }
            break;
        case UIS_TOKEN_IN | 1:                  /* reply collected by the host */
            UEP1_T_LEN = 0;
            UEP1_CTRL = UEP1_CTRL & ~MASK_UEP_T_RES | UEP_T_RES_NAK;
            break;
        case UIS_TOKEN_SETUP | 0:
            len = USB_RX_LEN == sizeof(USB_SETUP_REQ) ? handle_setup() : STALL;
            if (len == STALL) {
                setup_req = 0xFF;
                UEP0_CTRL = bUEP_R_TOG | bUEP_T_TOG | UEP_R_RES_STALL | UEP_T_RES_STALL;
            } else {
                UEP0_T_LEN = len;               /* data stage (DATA1) or zero-length status */
                UEP0_CTRL = bUEP_R_TOG | bUEP_T_TOG | UEP_R_RES_ACK | UEP_T_RES_ACK;
            }
            break;
        case UIS_TOKEN_IN | 0:
            if ((setup_type & USB_REQ_TYP_MASK) == USB_REQ_TYP_STANDARD && setup_req == USB_GET_DESCRIPTOR) {
                UEP0_T_LEN = load_chunk();
                UEP0_CTRL ^= bUEP_T_TOG;
            } else if ((setup_type & USB_REQ_TYP_MASK) == USB_REQ_TYP_STANDARD && setup_req == USB_SET_ADDRESS) {
                USB_DEV_AD = USB_DEV_AD & bUDA_GP_BIT | new_addr;
                UEP0_CTRL = UEP_R_RES_ACK | UEP_T_RES_NAK;
            } else {
                UEP0_T_LEN = 0;
                UEP0_CTRL = UEP_R_RES_ACK | UEP_T_RES_NAK;
            }
            break;
        case UIS_TOKEN_OUT | 0:
            if ((setup_type & USB_REQ_TYP_MASK) == USB_REQ_TYP_CLASS && setup_req == HID_SET_REPORT) {
                if (U_TOG_OK) {
                    len = USB_RX_LEN;
                    for (i = 0; i < 64; i++)
                        usb_rx[i] = i < len ? ep0_buf[i] : 0;
                    usb_rx_ready = 1;
                    UEP0_T_LEN = 0;             /* zero-length status IN */
                    UEP0_CTRL = UEP0_CTRL & ~MASK_UEP_T_RES | UEP_T_RES_ACK;
                }
            } else {
                UEP0_T_LEN = 0;                 /* status stage of an IN transfer */
                UEP0_CTRL = UEP_R_RES_ACK | UEP_T_RES_NAK;
            }
            break;
        default:
            break;
        }
        UIF_TRANSFER = 0;
    }
    if (UIF_BUS_RST) {
        UEP0_CTRL = UEP_R_RES_ACK | UEP_T_RES_NAK;
        UEP1_CTRL = bUEP_AUTO_TOG | UEP_T_RES_NAK | UEP_R_RES_ACK;
        USB_DEV_AD = 0x00;
        usb_configured = 0;
        usb_rx_ready = 0;
        UIF_SUSPEND = 0;
        UIF_TRANSFER = 0;
        UIF_BUS_RST = 0;
    }
    if (UIF_SUSPEND) {
        /* stay awake: the port switches must keep their state while the host sleeps */
        UIF_SUSPEND = 0;
    }
}

void usb_reply(const uint8_t *report)
{
    uint8_t i;
    for (i = 0; i < 64; i++) {
        EP1_IN[i] = report[i];
        last_reply[i] = report[i];
    }
    IE_USB = 0;
    usb_rx_ready = 0;
    UEP1_T_LEN = 64;
    UEP1_CTRL = UEP1_CTRL & ~(MASK_UEP_T_RES | MASK_UEP_R_RES) | UEP_T_RES_ACK | UEP_R_RES_ACK;
    IE_USB = 1;
}

void usb_init(void)
{
    build_serial();
    usb_configured = 0;
    usb_rx_ready = 0;

    USB_CTRL = 0x00;
    USB_CTRL = bUC_DEV_PU_EN | bUC_INT_BUSY | bUC_DMA_EN;   /* device, internal D+ pull-up */
    USB_DEV_AD = 0x00;
    UDEV_CTRL = bUD_PD_DIS;                                 /* full speed, no pull-downs */
    UDEV_CTRL |= bUD_PORT_EN;

    UEP0_DMA = (uint16_t)ep0_buf;
    UEP1_DMA = (uint16_t)ep1_buf;
    UEP4_1_MOD = bUEP1_RX_EN | bUEP1_TX_EN;                 /* EP1: 64 B OUT + 64 B IN */
    UEP0_CTRL = UEP_R_RES_ACK | UEP_T_RES_NAK;
    UEP1_CTRL = bUEP_AUTO_TOG | UEP_T_RES_NAK | UEP_R_RES_ACK;
    UEP0_T_LEN = 0;
    UEP1_T_LEN = 0;

    USB_INT_EN = bUIE_SUSPEND | bUIE_TRANSFER | bUIE_BUS_RST;
    USB_INT_FG = 0x1F;
    IE_USB = 1;
}
