"""
Input Injection Module for Pling Server Linux.
Translates Quest touch gestures and VR keyboard inputs into native Linux
input events using /dev/uinput.
"""

import os
import sys
import time
import fcntl
import struct
import logging
from typing import Optional
from pling.protocol import (
    TOUCH_ACTION_TAP,
    TOUCH_ACTION_LONG_PRESS,
    TOUCH_ACTION_SCROLL,
    TOUCH_ACTION_DRAG_START,
    TOUCH_ACTION_DRAG_MOVE,
    TOUCH_ACTION_DRAG_END,
    TOUCH_ACTION_MOVE,
    KEYBOARD_KIND_TEXT,
    KEYBOARD_KIND_KEYCODE,
)

logger = logging.getLogger("PlingInput")

# Linux input event constants
EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02
EV_ABS = 0x03

SYN_REPORT = 0x00

BTN_LEFT = 0x110
BTN_RIGHT = 0x111
BTN_MIDDLE = 0x112
BTN_TOUCH = 0x14A

REL_X = 0x00
REL_Y = 0x01
REL_WHEEL = 0x08
REL_HWHEEL = 0x06

ABS_X = 0x00
ABS_Y = 0x01

# Common Linux Keycodes
KEY_ESC = 1
KEY_1 = 2
KEY_2 = 3
KEY_3 = 4
KEY_4 = 5
KEY_5 = 6
KEY_6 = 7
KEY_7 = 8
KEY_8 = 9
KEY_9 = 10
KEY_0 = 11
KEY_MINUS = 12
KEY_EQUAL = 13
KEY_BACKSPACE = 14
KEY_TAB = 15
KEY_Q = 16
KEY_W = 17
KEY_E = 18
KEY_R = 19
KEY_T = 20
KEY_Y = 21
KEY_U = 22
KEY_I = 23
KEY_O = 24
KEY_P = 25
KEY_LEFTBRACE = 26
KEY_RIGHTBRACE = 27
KEY_ENTER = 28
KEY_LEFTCTRL = 29
KEY_A = 30
KEY_S = 31
KEY_D = 32
KEY_F = 33
KEY_G = 34
KEY_H = 35
KEY_J = 36
KEY_K = 37
KEY_L = 38
KEY_SEMICOLON = 39
KEY_APOSTROPHE = 40
KEY_GRAVE = 41
KEY_LEFTSHIFT = 42
KEY_BACKSLASH = 43
KEY_Z = 44
KEY_X = 45
KEY_C = 46
KEY_V = 47
KEY_B = 48
KEY_N = 49
KEY_M = 50
KEY_COMMA = 51
KEY_DOT = 52
KEY_SLASH = 53
KEY_RIGHTSHIFT = 54
KEY_LEFTALT = 56
KEY_SPACE = 57
KEY_CAPSLOCK = 58
KEY_UP = 103
KEY_LEFT = 105
KEY_RIGHT = 106
KEY_DOWN = 108

# Mapping macOS virtual keycodes (sent by Quest VR keyboard) to Linux Keycodes
MAC_TO_LINUX_KEYCODES = {
    0x33: KEY_BACKSPACE,  # 51
    0x24: KEY_ENTER,      # 36
    0x30: KEY_TAB,        # 48
    0x31: KEY_SPACE,      # 49
    0x35: KEY_ESC,        # 53
    0x7B: KEY_LEFT,       # 123
    0x7C: KEY_RIGHT,      # 124
    0x7D: KEY_DOWN,       # 125
    0x7E: KEY_UP,         # 126
}

# ASCII Character to Linux Keycode + Shift flag
CHAR_TO_KEY = {
    'a': (KEY_A, False), 'b': (KEY_B, False), 'c': (KEY_C, False), 'd': (KEY_D, False),
    'e': (KEY_E, False), 'f': (KEY_F, False), 'g': (KEY_G, False), 'h': (KEY_H, False),
    'i': (KEY_I, False), 'j': (KEY_J, False), 'k': (KEY_K, False), 'l': (KEY_L, False),
    'm': (KEY_M, False), 'n': (KEY_N, False), 'o': (KEY_O, False), 'p': (KEY_P, False),
    'q': (KEY_Q, False), 'r': (KEY_R, False), 's': (KEY_S, False), 't': (KEY_T, False),
    'u': (KEY_U, False), 'v': (KEY_V, False), 'w': (KEY_W, False), 'x': (KEY_X, False),
    'y': (KEY_Y, False), 'z': (KEY_Z, False),
    'A': (KEY_A, True), 'B': (KEY_B, True), 'C': (KEY_C, True), 'D': (KEY_D, True),
    'E': (KEY_E, True), 'F': (KEY_F, True), 'G': (KEY_G, True), 'H': (KEY_H, True),
    'I': (KEY_I, True), 'J': (KEY_J, True), 'K': (KEY_K, True), 'L': (KEY_L, True),
    'M': (KEY_M, True), 'N': (KEY_N, True), 'O': (KEY_O, True), 'P': (KEY_P, True),
    'Q': (KEY_Q, True), 'R': (KEY_R, True), 'S': (KEY_S, True), 'T': (KEY_T, True),
    'U': (KEY_U, True), 'V': (KEY_V, True), 'W': (KEY_W, True), 'X': (KEY_X, True),
    'Y': (KEY_Y, True), 'Z': (KEY_Z, True),
    '1': (KEY_1, False), '2': (KEY_2, False), '3': (KEY_3, False), '4': (KEY_4, False),
    '5': (KEY_5, False), '6': (KEY_6, False), '7': (KEY_7, False), '8': (KEY_8, False),
    '9': (KEY_9, False), '0': (KEY_0, False),
    '!': (KEY_1, True), '@': (KEY_2, True), '#': (KEY_3, True), '$': (KEY_4, True),
    '%': (KEY_5, True), '^': (KEY_6, True), '&': (KEY_7, True), '*': (KEY_8, True),
    '(': (KEY_9, True), ')': (KEY_0, True),
    ' ': (KEY_SPACE, False), '\t': (KEY_TAB, False), '\n': (KEY_ENTER, False),
    '-': (KEY_MINUS, False), '_': (KEY_MINUS, True),
    '=': (KEY_EQUAL, False), '+': (KEY_EQUAL, True),
    '[': (KEY_LEFTBRACE, False), '{': (KEY_LEFTBRACE, True),
    ']': (KEY_RIGHTBRACE, False), '}': (KEY_RIGHTBRACE, True),
    ';': (KEY_SEMICOLON, False), ':': (KEY_SEMICOLON, True),
    "'": (KEY_APOSTROPHE, False), '"': (KEY_APOSTROPHE, True),
    '`': (KEY_GRAVE, False), '~': (KEY_GRAVE, True),
    '\\': (KEY_BACKSLASH, False), '|': (KEY_BACKSLASH, True),
    ',': (KEY_COMMA, False), '<': (KEY_COMMA, True),
    '.': (KEY_DOT, False), '>': (KEY_DOT, True),
    '/': (KEY_SLASH, False), '?': (KEY_SLASH, True),
}

# Linux Uinput ioctl numbers
UI_SET_EVBIT   = 0x40045564
UI_SET_KEYBIT  = 0x40045565
UI_SET_RELBIT  = 0x40045566
UI_SET_ABSBIT  = 0x40045567
UI_DEV_CREATE  = 0x5501
UI_DEV_DESTROY = 0x5502

# Coordinates range for absolute touchscreen/pointer (0..32767)
ABS_MAX_COORD = 32767

class InputInjector:
    """
    Creates and controls a virtual input device via /dev/uinput.
    """
    def __init__(self, screen_width: int = 1920, screen_height: int = 1080):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._fd: Optional[int] = None
        self._available = False
        self._init_uinput()

    @property
    def is_available(self) -> bool:
        return self._available

    def _init_uinput(self) -> None:
        if not sys.platform.startswith("linux"):
            logger.warning("Non-Linux platform: /dev/uinput simulation mode.")
            return

        if not os.path.exists("/dev/uinput"):
            logger.warning("/dev/uinput device not found. Ensure 'uinput' kernel module is loaded.")
            return

        try:
            self._fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        except PermissionError:
            logger.error("Permission denied opening /dev/uinput. Run as root or install 99-pling-uinput.rules.")
            return
        except Exception as e:
            logger.error(f"Failed to open /dev/uinput: {e}")
            return

        try:
            # Enable Event Types
            fcntl.ioctl(self._fd, UI_SET_EVBIT, EV_SYN)
            fcntl.ioctl(self._fd, UI_SET_EVBIT, EV_KEY)
            fcntl.ioctl(self._fd, UI_SET_EVBIT, EV_REL)
            fcntl.ioctl(self._fd, UI_SET_EVBIT, EV_ABS)

            # Enable Mouse / Touch Buttons
            for btn in (BTN_LEFT, BTN_RIGHT, BTN_MIDDLE, BTN_TOUCH):
                fcntl.ioctl(self._fd, UI_SET_KEYBIT, btn)

            # Enable Scroll Wheels
            for rel in (REL_X, REL_Y, REL_WHEEL, REL_HWHEEL):
                fcntl.ioctl(self._fd, UI_SET_RELBIT, rel)

            # Enable Absolute Coordinates
            for abs_code in (ABS_X, ABS_Y):
                fcntl.ioctl(self._fd, UI_SET_ABSBIT, abs_code)

            # Enable All Keyboard Keys
            for keycode in range(1, 256):
                fcntl.ioctl(self._fd, UI_SET_KEYBIT, keycode)

            # Setup legacy uinput_user_dev struct
            # name (80B) + id (bustype 2B, vendor 2B, product 2B, version 2B) + ff_effects_max (4B)
            # + absmax (64*4B) + absmin (64*4B) + absfuzz (64*4B) + absflat (64*4B)
            name = b"Pling Virtual Quest Controller\x00"
            name = name.ljust(80, b"\x00")
            id_data = struct.pack("<HHHH", 0x03, 0x1234, 0x5678, 1) # USB bustype
            ff_max = struct.pack("<I", 0)

            absmax = [0] * 64
            absmin = [0] * 64
            absfuzz = [0] * 64
            absflat = [0] * 64

            absmax[ABS_X] = ABS_MAX_COORD
            absmax[ABS_Y] = ABS_MAX_COORD

            absmax_bytes = struct.pack(f"<{len(absmax)}i", *absmax)
            absmin_bytes = struct.pack(f"<{len(absmin)}i", *absmin)
            absfuzz_bytes = struct.pack(f"<{len(absfuzz)}i", *absfuzz)
            absflat_bytes = struct.pack(f"<{len(absflat)}i", *absflat)

            uinput_dev = name + id_data + ff_max + absmax_bytes + absmin_bytes + absfuzz_bytes + absflat_bytes
            os.write(self._fd, uinput_dev)

            # Create device
            fcntl.ioctl(self._fd, UI_DEV_CREATE)
            self._available = True
            logger.info("Successfully registered /dev/uinput virtual controller.")

        except Exception as e:
            logger.error(f"Error configuring /dev/uinput: {e}")
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None

    def _write_event(self, ev_type: int, code: int, value: int) -> None:
        if not self._available or self._fd is None:
            return
        # struct input_event: timeval (16 bytes on 64-bit), type (2 bytes), code (2 bytes), value (4 bytes)
        # Note: on 64-bit Linux timeval is two 64-bit longs (16 bytes). We can pass 0 for timestamp.
        now = time.time()
        tv_sec = int(now)
        tv_usec = int((now - tv_sec) * 1_000_000)
        ev_data = struct.pack("<qqHHi", tv_sec, tv_usec, ev_type, code, value)
        try:
            os.write(self._fd, ev_data)
        except Exception as e:
            logger.debug(f"Failed to write input event: {e}")

    def _syn(self) -> None:
        self._write_event(EV_SYN, SYN_REPORT, 0)

    def handle_touch(self, action: int, nx: float, ny: float) -> None:
        """
        Translates normalized (0.0 to 1.0) coordinates and actions into Linux events.
        """
        abs_x = max(0, min(ABS_MAX_COORD, int(nx * ABS_MAX_COORD)))
        abs_y = max(0, min(ABS_MAX_COORD, int(ny * ABS_MAX_COORD)))

        if action == TOUCH_ACTION_TAP:
            # Move -> Left Down -> Left Up
            self._write_event(EV_ABS, ABS_X, abs_x)
            self._write_event(EV_ABS, ABS_Y, abs_y)
            self._write_event(EV_KEY, BTN_TOUCH, 1)
            self._write_event(EV_KEY, BTN_LEFT, 1)
            self._syn()
            time.sleep(0.01)
            self._write_event(EV_KEY, BTN_TOUCH, 0)
            self._write_event(EV_KEY, BTN_LEFT, 0)
            self._syn()

        elif action == TOUCH_ACTION_LONG_PRESS:
            # Move -> Right Down -> Right Up
            self._write_event(EV_ABS, ABS_X, abs_x)
            self._write_event(EV_ABS, ABS_Y, abs_y)
            self._write_event(EV_KEY, BTN_RIGHT, 1)
            self._syn()
            time.sleep(0.01)
            self._write_event(EV_KEY, BTN_RIGHT, 0)
            self._syn()

        elif action == TOUCH_ACTION_SCROLL:
            # nx, ny are normalized deltas. Scale to fluid wheel clicks.
            scroll_y = int(ny * -10.0) # standard wheel direction
            scroll_x = int(nx * 10.0)
            if scroll_y != 0:
                self._write_event(EV_REL, REL_WHEEL, scroll_y)
            if scroll_x != 0:
                self._write_event(EV_REL, REL_HWHEEL, scroll_x)
            self._syn()

        elif action == TOUCH_ACTION_DRAG_START:
            self._write_event(EV_ABS, ABS_X, abs_x)
            self._write_event(EV_ABS, ABS_Y, abs_y)
            self._write_event(EV_KEY, BTN_LEFT, 1)
            self._write_event(EV_KEY, BTN_TOUCH, 1)
            self._syn()

        elif action == TOUCH_ACTION_DRAG_MOVE:
            self._write_event(EV_ABS, ABS_X, abs_x)
            self._write_event(EV_ABS, ABS_Y, abs_y)
            self._syn()

        elif action == TOUCH_ACTION_DRAG_END:
            self._write_event(EV_ABS, ABS_X, abs_x)
            self._write_event(EV_ABS, ABS_Y, abs_y)
            self._write_event(EV_KEY, BTN_LEFT, 0)
            self._write_event(EV_KEY, BTN_TOUCH, 0)
            self._syn()

        elif action == TOUCH_ACTION_MOVE:
            self._write_event(EV_ABS, ABS_X, abs_x)
            self._write_event(EV_ABS, ABS_Y, abs_y)
            self._syn()

    def handle_keyboard(self, kind: int, data: bytes) -> None:
        """
        Translates VR keyboard input to Linux keystrokes.
        """
        if kind == KEYBOARD_KIND_TEXT:
            try:
                text = data.decode("utf-8")
                for ch in text:
                    self.type_char(ch)
            except Exception as e:
                logger.error(f"Error decoding keyboard text: {e}")

        elif kind == KEYBOARD_KIND_KEYCODE:
            if len(data) > 0:
                mac_code = data[0]
                linux_code = MAC_TO_LINUX_KEYCODES.get(mac_code)
                if linux_code is not None:
                    self.press_key(linux_code)
                else:
                    logger.debug(f"Unmapped macOS keycode: {hex(mac_code)}")

    def press_key(self, keycode: int) -> None:
        self._write_event(EV_KEY, keycode, 1)
        self._syn()
        time.sleep(0.005)
        self._write_event(EV_KEY, keycode, 0)
        self._syn()

    def type_char(self, ch: str) -> None:
        mapping = CHAR_TO_KEY.get(ch)
        if not mapping:
            logger.debug(f"No direct mapping for character: {ch!r}")
            return
        code, need_shift = mapping
        if need_shift:
            self._write_event(EV_KEY, KEY_LEFTSHIFT, 1)
            self._syn()

        self._write_event(EV_KEY, code, 1)
        self._syn()
        time.sleep(0.002)
        self._write_event(EV_KEY, code, 0)
        self._syn()

        if need_shift:
            self._write_event(EV_KEY, KEY_LEFTSHIFT, 0)
            self._syn()

    def close(self) -> None:
        if self._fd is not None:
            try:
                fcntl.ioctl(self._fd, UI_DEV_DESTROY)
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None
            self._available = False
