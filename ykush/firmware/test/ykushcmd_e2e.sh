#!/bin/sh
# End-to-end: build Yepkit's real ykushcmd with its USB layer replaced by test/mock_usbhid.cpp,
# which feeds the YKUSH-VG protocol handler, then drive it like a user would.
set -e
HERE=$(cd "$(dirname "$0")/.." && pwd)
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
git clone -q --depth 1 https://github.com/Yepkit/ykush "$W/ykush"
cd "$W/ykush"
cp "$HERE/test/mock_usbhid.cpp" src/usbhid/usbhid.cpp
INC="-Isrc -Isrc/ykush -Isrc/ykushxs -Isrc/ykush2 -Isrc/ykush3 -Isrc/help -Isrc/utils -Isrc/usbhid -Ilibusb"
gcc -c -I"$HERE/src" "$HERE/src/ykush.c" -o ykush_fw.o
g++ -D_LINUX_ -D_LIBUSB_ $INC -o ykushcmd src/yktrl.cpp src/commandParser.cpp src/ykushxs/ykushxs.cpp \
    src/ykush/ykush.cpp src/ykush2/ykush2.cpp src/ykush3/ykush3.cpp src/yk_usb_device.cpp \
    src/help/ykush_help.cpp src/utils/command_parser.cpp src/utils/string2val.cpp src/usbhid/usbhid.cpp \
    ykush_fw.o
export YKVG_STATE="$W/state"
fail=0
expect() {  # expect <description> <pattern> <ykushcmd args...>
    d=$1; p=$2; shift 2
    out=$(./ykushcmd "$@" 2>&1 || true)
    if printf '%s' "$out" | grep -q "$p"; then echo "ok   $d"; else echo "FAIL $d: got: $out"; fail=1; fi
}
expect "list boards"            "serial number: VG12345678"   -l
./ykushcmd -u 2 >/dev/null
expect "status port 2 ON"       "port 2 is ON"                -g 2
expect "status port 1 still off" "port 1 is OFF"              -g 1
./ykushcmd -u a >/dev/null
expect "port 3 ON after all-on" "port 3 is ON"                -g 3
./ykushcmd -d 3 >/dev/null
expect "port 3 off"             "port 3 is OFF"               -g 3
expect "port 1 unaffected"      "port 1 is ON"                -g 1
./ykushcmd -d a >/dev/null
expect "all off"                "port 1 is OFF"               -g 1
expect "select by serial"       "port 2 is OFF"               -s VG12345678 -g 2
exit $fail
