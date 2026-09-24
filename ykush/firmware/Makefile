# YKUSH-VG firmware (CH552G), built with SDCC.
#   make          -> build/ykush_vg.hex and .bin
#   make test     -> check the USB descriptors in the built image + unit-test the protocol (gcc)
#   make e2e      -> build Yepkit's real ykushcmd against this protocol code and drive it
#   make flash    -> flash over USB with wchisp (hold BOOT while plugging in, or `host/ykvg.py boot`)

TARGET   = ykush_vg
FREQ_SYS = 24000000
CC       = sdcc
BUILD    = build
SRCS     = main.c usb.c board.c ykush.c
# xdata 0x0000-0x00BF holds the USB DMA buffers (placed with __at in usb.c), so SDCC
# allocates its own xdata from 0x0100.
CFLAGS   = -mmcs51 --model-small --xram-size 0x0300 --xram-loc 0x0100 --code-size 0x3800 \
           -Iinclude -Isrc -DFREQ_SYS=$(FREQ_SYS) $(EXTRA_FLAGS)
RELS     = $(addprefix $(BUILD)/,$(SRCS:.c=.rel))

all: $(BUILD)/$(TARGET).hex $(BUILD)/$(TARGET).bin

$(BUILD)/%.rel: src/%.c src/*.h | $(BUILD)
	$(CC) -c $(CFLAGS) -o $@ $<

$(BUILD)/$(TARGET).ihx: $(RELS)
	$(CC) $(CFLAGS) -o $@ $(RELS)

$(BUILD)/$(TARGET).hex: $(BUILD)/$(TARGET).ihx
	packihx $< > $@

$(BUILD)/$(TARGET).bin: $(BUILD)/$(TARGET).ihx
	objcopy -I ihex -O binary $< $@
	@echo "code size: $$(stat -c %s $@) bytes of 14336"

$(BUILD):
	mkdir -p $@

test: $(BUILD)/$(TARGET).ihx
	python3 test/check_descriptors.py
	gcc -Wall -Wextra -O1 -Isrc -o $(BUILD)/test_ykush test/test_ykush.c src/ykush.c && $(BUILD)/test_ykush

flash: $(BUILD)/$(TARGET).bin
	wchisp flash $<

clean:
	rm -rf $(BUILD)

e2e:
	sh test/ykushcmd_e2e.sh

.PHONY: all test e2e flash clean
