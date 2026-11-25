# An MCP server on standard input and output that takes pictures of the
# screen and sends mouse and keyboard input. Linux with an X11 display only;
# it needs nothing beyond Python's standard library and the system's own X
# libraries (libX11 and libXtst; libXrandr, when present, tells the displays
# apart).
#
# The tools are described in tools.json beside this file, which the macOS and
# Windows versions read as well, so all three offer the same tools.
#
# Run with --this-desktop, the server finds the X display of the desktop of
# the account it runs as by itself, instead of reading DISPLAY, and names its
# tools with a desktop_ prefix.
import base64
import contextlib
import ctypes
import json
import os
import re
import struct
import sys
import time
import zlib
from array import array
from operator import itemgetter

VERSION = "0.3.3"
# The longest edge of a picture handed back, in pixels.
LONGEST = 1568
HERE = os.path.dirname(os.path.abspath(__file__))

ARGS = sys.argv[1:]
THIS_DESKTOP = "--this-desktop" in ARGS
# For testing only: use this display, still found among the account's own.
CHOSEN = ARGS[ARGS.index("--display") + 1] if "--display" in ARGS[:-1] else None
PREFIX = "desktop_" if THIS_DESKTOP else ""
SUBJECT = "the Linux desktop this tool runs on" if THIS_DESKTOP else "the user's computer"
SERVER = "linux-desktop" if THIS_DESKTOP else "desktop-control"

ref, uint, ulong, c_int, c_long = ctypes.c_void_p, ctypes.c_uint, ctypes.c_ulong, ctypes.c_int, ctypes.c_long
LIBRARIES = ("The X11 libraries libX11.so.6 and libXtst.so.6 are not installed. Install them (for example the "
             "libx11-6 and libxtst6 packages), then try again.")
try:
    x11, xtst = ctypes.CDLL("libX11.so.6"), ctypes.CDLL("libXtst.so.6")
except OSError:
    x11 = xtst = None
try:
    xrandr = ctypes.CDLL("libXrandr.so.2") if x11 else None
except OSError:
    xrandr = None


class Image(ctypes.Structure):
    # The start of Xlib's XImage; the rest is not read here.
    _fields_ = [("width", c_int), ("height", c_int), ("xoffset", c_int), ("format", c_int), ("data", ref),
                ("byte_order", c_int), ("bitmap_unit", c_int), ("bitmap_bit_order", c_int), ("bitmap_pad", c_int),
                ("depth", c_int), ("bytes_per_line", c_int), ("bits_per_pixel", c_int),
                ("red_mask", ulong), ("green_mask", ulong), ("blue_mask", ulong)]


class KeyboardState(ctypes.Structure):
    _fields_ = [("group", ctypes.c_ubyte), ("locked_group", ctypes.c_ubyte), ("base_group", ctypes.c_ushort),
                ("latched_group", ctypes.c_ushort)] + [(name, ctypes.c_ubyte) for name in (
                    "mods", "base_mods", "latched_mods", "locked_mods", "compat_state", "grab_mods",
                    "compat_grab_mods", "lookup_mods", "compat_lookup_mods")] + [("ptr_buttons", ctypes.c_ushort)]


class ErrorEvent(ctypes.Structure):
    _fields_ = [("type", c_int), ("display", ref), ("resourceid", ulong), ("serial", ulong),
                ("error_code", ctypes.c_ubyte), ("request_code", ctypes.c_ubyte), ("minor_code", ctypes.c_ubyte)]


class WindowAttributes(ctypes.Structure):
    _fields_ = [("x", c_int), ("y", c_int), ("width", c_int), ("height", c_int), ("border_width", c_int),
                ("depth", c_int), ("visual", ref), ("root", ulong), ("class_", c_int), ("bit_gravity", c_int),
                ("win_gravity", c_int), ("backing_store", c_int), ("backing_planes", ulong),
                ("backing_pixel", ulong), ("save_under", c_int), ("colormap", ulong), ("map_installed", c_int),
                ("map_state", c_int), ("all_event_masks", c_long), ("your_event_mask", c_long),
                ("do_not_propagate_mask", c_long), ("override_redirect", c_int), ("screen", ref)]


class Monitor(ctypes.Structure):
    _fields_ = [("name", ulong), ("primary", c_int), ("automatic", c_int), ("noutput", c_int), ("x", c_int),
                ("y", c_int), ("width", c_int), ("height", c_int), ("mwidth", c_int), ("mheight", c_int),
                ("outputs", ref)]


def declare(library, name, result, *arguments):
    function = getattr(library, name)
    function.restype, function.argtypes = result, list(arguments)
    return function


if x11:
    keycode, number_out, ulong_out = ctypes.c_ubyte, ctypes.POINTER(c_int), ctypes.POINTER(ulong)
    open_display = declare(x11, "XOpenDisplay", ref, ctypes.c_char_p)
    close_display = declare(x11, "XCloseDisplay", c_int, ref)
    default_screen = declare(x11, "XDefaultScreen", c_int, ref)
    display_wide = declare(x11, "XDisplayWidth", c_int, ref, c_int)
    display_high = declare(x11, "XDisplayHeight", c_int, ref, c_int)
    root_window = declare(x11, "XRootWindow", ulong, ref, c_int)
    get_image = declare(x11, "XGetImage", ctypes.POINTER(Image), ref, ulong, c_int, c_int, uint, uint, ulong, c_int)
    destroy_image = declare(x11, "XDestroyImage", c_int, ctypes.POINTER(Image))
    sync = declare(x11, "XSync", c_int, ref, c_int)
    flush = declare(x11, "XFlush", c_int, ref)
    free = declare(x11, "XFree", c_int, ref)
    keycodes = declare(x11, "XDisplayKeycodes", c_int, ref, number_out, number_out)
    get_mapping = declare(x11, "XGetKeyboardMapping", ctypes.POINTER(ulong), ref, keycode, c_int, number_out)
    change_mapping = declare(x11, "XChangeKeyboardMapping", c_int, ref, c_int, c_int, ctypes.POINTER(ulong), c_int)
    keysym_code = declare(x11, "XKeysymToKeycode", keycode, ref, ulong)
    keyboard_state = declare(x11, "XkbGetState", c_int, ref, uint, ctypes.POINTER(KeyboardState))
    lock_modifiers = declare(x11, "XkbLockModifiers", c_int, ref, uint, uint, uint)
    intern_atom = declare(x11, "XInternAtom", ulong, ref, ctypes.c_char_p, c_int)
    get_property = declare(x11, "XGetWindowProperty", c_int, ref, ulong, ulong, c_long, c_long, c_int, ulong,
                           ulong_out, number_out, ulong_out, ulong_out, ctypes.POINTER(ctypes.c_void_p))
    query_tree = declare(x11, "XQueryTree", c_int, ref, ulong, ulong_out, ulong_out,
                         ctypes.POINTER(ctypes.POINTER(ulong)), ctypes.POINTER(uint))
    window_attributes = declare(x11, "XGetWindowAttributes", c_int, ref, ulong, ctypes.POINTER(WindowAttributes))
    translate = declare(x11, "XTranslateCoordinates", c_int, ref, ulong, ulong, c_int, c_int, number_out,
                        number_out, ulong_out)
    input_focus = declare(x11, "XGetInputFocus", c_int, ref, ulong_out, number_out)
    query_pointer = declare(x11, "XQueryPointer", c_int, ref, ulong, ulong_out, ulong_out, number_out, number_out,
                            number_out, number_out, ctypes.POINTER(uint))
    on_error = ctypes.CFUNCTYPE(c_int, ref, ctypes.POINTER(ErrorEvent))
    set_error_handler = declare(x11, "XSetErrorHandler", ref, on_error)
    has_test = declare(xtst, "XTestQueryExtension", c_int, ref, number_out, number_out, number_out, number_out)
    fake_motion = declare(xtst, "XTestFakeMotionEvent", c_int, ref, c_int, c_int, c_int, ulong)
    fake_button = declare(xtst, "XTestFakeButtonEvent", c_int, ref, uint, c_int, ulong)
    fake_key = declare(xtst, "XTestFakeKeyEvent", c_int, ref, uint, c_int, ulong)
    if xrandr:
        randr_version = declare(xrandr, "XRRQueryVersion", c_int, ref, number_out, number_out)
        randr_has = declare(xrandr, "XRRQueryExtension", c_int, ref, number_out, number_out)
        get_monitors = declare(xrandr, "XRRGetMonitors", ctypes.POINTER(Monitor), ref, ulong, c_int, number_out)
        free_monitors = declare(xrandr, "XRRFreeMonitors", None, ctypes.POINTER(Monitor))

    # Xlib's own handler ends the program on any error; this one notes it.
    errors = []

    @on_error
    def note_error(_, event):
        errors.append(event.contents.error_code)
        return 0

    set_error_handler(note_error)

ALL_PLANES, Z_PIXMAP, MSB_FIRST, LOCK, CORE_KEYBOARD, VIEWABLE = 0xFFFFFFFFFFFFFFFF, 2, 1, 0x2, 0x100, 2
BUTTONS = {"left": 1, "middle": 2, "right": 3}
# X keysyms. Characters are their own keysyms up to U+00FF and
# 0x01000000 plus the code point above.
SHIFT, CONTROL, ALT, SUPER = 0xFFE1, 0xFFE3, 0xFFE9, 0xFFEB
# cmd and command mean the shortcut modifier, as mod does: ctrl here.
MODIFIERS = {"ctrl": CONTROL, "control": CONTROL, "mod": CONTROL, "cmd": CONTROL, "command": CONTROL, "shift": SHIFT,
             "alt": ALT, "option": ALT, "meta": SUPER, "win": SUPER, "windows": SUPER, "super": SUPER}
KEYS = {
    "return": 0xFF0D, "enter": 0xFF0D, "tab": 0xFF09, "space": 0x20, "backspace": 0xFF08, "delete": 0xFFFF,
    "insert": 0xFF63, "escape": 0xFF1B, "esc": 0xFF1B, "left": 0xFF51, "up": 0xFF52, "right": 0xFF53,
    "down": 0xFF54, "home": 0xFF50, "end": 0xFF57, "pageup": 0xFF55, "pagedown": 0xFF56,
    **{f"f{n}": 0xFFBD + n for n in range(1, 13)},
}


class Refused(Exception):
    pass


# Finding the desktop. Programs started for this tool may come without
# DISPLAY, so with --this-desktop the X server is looked for among the
# account's own processes.
X_SERVERS = {"Xtigervnc", "Xvnc", "Xorg", "X", "Xvfb", "Xwayland", "Xephyr", "Xnest", "Xdummy"}
NO_DESKTOP = "No desktop is running; open the desktop first."


def x_servers(processes):
    """The X servers among (owner, arguments) pairs: (owner, display number, authority file or None)."""
    found = []
    for owner, argv in processes:
        if not argv or os.path.basename(argv[0]) not in X_SERVERS:
            continue
        numbers = [int(arg[1:]) for arg in argv[1:] if re.fullmatch(r":\d{1,4}", arg)]
        if not numbers:
            continue
        auth = argv[argv.index("-auth") + 1] if "-auth" in argv[1:-1] else None
        found.append((owner, numbers[0], auth))
    return found


def choose_desktop(processes, uid, socket_owner, wanted=None):
    """The (display number, authority file) of the account's desktop, or None.

    Only servers the account runs count. One whose socket the account owns
    comes first, then the lowest display number, so the choice is the same
    every time."""
    mine = [(number, auth) for owner, number, auth in x_servers(processes) if owner == uid]
    if wanted is not None:
        mine = [entry for entry in mine if entry[0] == wanted]
    if not mine:
        return None
    return min(mine, key=lambda entry: (socket_owner(entry[0]) != uid, entry[0]))


def read_processes(proc="/proc"):
    found = []
    for entry in os.listdir(proc):
        if not entry.isdigit():
            continue
        try:
            owner = os.stat(os.path.join(proc, entry)).st_uid
            with open(os.path.join(proc, entry, "cmdline"), "rb") as file:
                argv = [part.decode("utf-8", "replace") for part in file.read().split(b"\0") if part]
        except OSError:
            continue
        found.append((owner, argv))
    return found


def socket_owner(number):
    try:
        return os.stat(f"/tmp/.X11-unix/X{number}").st_uid
    except OSError:
        return None


def find_desktop():
    wanted = int(CHOSEN.lstrip(":")) if CHOSEN else None
    chosen = choose_desktop(read_processes(), os.getuid(), socket_owner, wanted)
    if chosen is None:
        raise Refused(NO_DESKTOP)
    number, auth = chosen
    os.environ["DISPLAY"] = f":{number}"
    if auth and os.access(auth, os.R_OK):
        os.environ["XAUTHORITY"] = auth
    return f":{number}"


@contextlib.contextmanager
def connect(input=False):
    """A connection to the X display for the length of one call."""
    if not x11:
        raise Refused(LIBRARIES)
    if THIS_DESKTOP:
        name = find_desktop()
    else:
        name = os.environ.get("DISPLAY")
        if not name:
            raise Refused("No X11 display is available: DISPLAY is not set. This tool works in X11 sessions; under "
                          "Wayland it reaches only windows shown through XWayland, and needs DISPLAY set.")
    display = open_display(name.encode())
    if not display:
        if THIS_DESKTOP:
            raise Refused(NO_DESKTOP)
        raise Refused(f"The X11 display {name} cannot be opened. Make sure the session is running and this "
                      "program may connect to it (XAUTHORITY), then try again.")
    del errors[:]
    try:
        if input and not has_test(display, *(ctypes.byref(c_int()) for _ in range(4))):
            raise Refused("The display does not offer the XTEST extension, which mouse and keyboard input needs.")
        yield display
        sync(display, 0)
        if errors:
            raise Refused(f"the display refused the request (X error {errors[0]})")
    finally:
        close_display(display)


# Displays and positions. A position is in pixels of the latest full
# screenshot of a display; what each screenshot covered is kept here, so
# positions keep meaning what the picture showed.
shots = {}


def measure(wide, high):
    """The size of a picture of an area of the screen, at most LONGEST pixels on its longest side."""
    shrink = max(1.0, max(wide, high) / LONGEST)
    return max(1, round(wide / shrink)), max(1, round(high / shrink))


def monitors(display):
    """The displays as (x, y, width, height, main), main first, then from left to right."""
    screen = default_screen(display)
    whole = (0, 0, display_wide(display, screen), display_high(display, screen))
    found = []
    major, minor, event, error = c_int(), c_int(), c_int(), c_int()
    if (xrandr and randr_has(display, ctypes.byref(event), ctypes.byref(error))
            and randr_version(display, ctypes.byref(major), ctypes.byref(minor))
            and (major.value, minor.value) >= (1, 5)):
        count = c_int()
        listed = get_monitors(display, root_window(display, screen), 1, ctypes.byref(count))
        if listed:
            try:
                found = [(m.x, m.y, m.width, m.height, bool(m.primary)) for m in listed[:count.value]
                         if m.width > 0 and m.height > 0]
            finally:
                free_monitors(listed)
    if not found:
        found = [(*whole, True)]
    found.sort(key=lambda m: (m[0], m[1]))
    main = next((m for m in found if m[4]), found[0])
    return [main] + [m for m in found if m is not main]


def geometry(display, number):
    """What a full screenshot of a display covers: x, y, width, height in screen pixels, and the picture's size."""
    found = monitors(display)
    if not 0 <= number < len(found):
        raise Refused(f"there is no display {number}; list_displays shows the displays")
    x, y, wide, high, _ = found[number]
    return (x, y, wide, high, *measure(wide, high))


def shot(display, number):
    """The latest full screenshot of a display, or what one would cover now."""
    return shots.get(number) or geometry(display, number)


def display_number(arguments):
    number = arguments.get("display", 0)
    if number is None:
        number = 0
    if not isinstance(number, int) or isinstance(number, bool) or number < 0:
        raise Refused("display must be a whole number, as list_displays shows")
    return number


def place(display, arguments, x="x", y="y"):
    """A position given in pixels of a screenshot, in pixels of the screen."""
    try:
        px, py = float(arguments[x]), float(arguments[y])
    except (KeyError, TypeError, ValueError):
        raise Refused(f"{x} and {y} must be numbers, in pixels of the latest screenshot")
    left, top, wide, high, width, height = shot(display, display_number(arguments))
    if not (0 <= px <= width and 0 <= py <= height):
        raise Refused(f"that position is outside the display, which is {width}x{height} pixels in its screenshot")
    sx, sy = left + round(px * wide / width), top + round(py * high / height)
    return min(sx, left + wide - 1), min(sy, top + high - 1)


def where(display, sx, sy):
    """The display a point of the screen is on, and the point in pixels of its screenshot."""
    found = monitors(display)
    inside = [n for n, m in enumerate(found) if m[0] <= sx < m[0] + m[2] and m[1] <= sy < m[1] + m[3]]
    number = inside[0] if inside else 0
    left, top, wide, high, width, height = shot(display, number)
    return number, round((sx - left) * width / wide), round((sy - top) * height / high)


def pairs(source, target):
    """For each of target pixels along an edge, the two source pixels nearest its middle."""
    near = [min(max(int((i + 0.5) * source / target - 0.5), 0), source - 1) for i in range(target)]
    return near, [min(n + 1, source - 1) for n in near]


def average(a, b):
    """Each byte of a and b averaged, by arithmetic on all the bytes taken as one large number."""
    x, y = int.from_bytes(a, "little"), int.from_bytes(b, "little")
    mask = int.from_bytes(b"\xfe" * len(a), "little")
    return ((x & y) + (((x ^ y) & mask) >> 1)).to_bytes(len(a), "little")


def colours(image, width, height):
    """The pixels of an XImage as red, green and blue bytes, shrunk to width x height.

    Whole rows and columns are moved by slicing; nothing loops over single
    pixels in Python."""
    size = image.bits_per_pixel // 8
    if image.bits_per_pixel not in (24, 32) or image.depth < 24:
        raise Refused(f"The screen uses {image.depth}-bit colour at {image.bits_per_pixel} bits per pixel; this "
                      "tool reads only 24-bit colour.")
    offsets = []
    for mask in (image.red_mask, image.green_mask, image.blue_mask):
        shift = (mask & -mask).bit_length() - 1
        if mask >> shift != 0xFF or shift % 8:
            raise Refused("The screen uses a colour layout this tool cannot read.")
        offsets.append(size - 1 - shift // 8 if image.byte_order == MSB_FIRST else shift // 8)
    wide, high, line = image.width, image.height, image.bytes_per_line
    raw = ctypes.string_at(image.data, line * high)

    def rows(chosen):
        """The chosen rows, four bytes to a pixel."""
        joined = b"".join(raw[y * line:y * line + wide * size] for y in chosen)
        if size == 4:
            return joined
        four = bytearray(len(joined) // 3 * 4)
        for channel in range(3):
            four[channel::4] = joined[channel::3]
        return bytes(four)

    if (width, height) == (wide, high):
        pixels = rows(range(high))
    else:
        # Each picture pixel is the average of the 2 x 2 screen pixels
        # nearest its middle, so lines one pixel thin do not drop out.
        top, bottom = pairs(high, height)
        left, right = pairs(wide, width)
        tall = memoryview(average(rows(top), rows(bottom))).cast("I")
        halves = []
        for columns in (left, right):
            pick, picked = itemgetter(*columns), array("I")
            for row in range(height):
                taken = pick(tall[row * wide:(row + 1) * wide])
                picked.extend(taken if isinstance(taken, tuple) else (taken,))
            halves.append(picked.tobytes())
        pixels = average(*halves)
    rgb = bytearray(width * height * 3)
    for channel, offset in enumerate(offsets):
        rgb[channel::3] = pixels[offset::4]
    return rgb


def png(width, height, rgb):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    stride = width * 3
    lines = b"".join(b"\x00" + rgb[i:i + stride] for i in range(0, len(rgb), stride))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(lines, 6)) + chunk(b"IEND", b""))


def capture(display, x, y, wide, high):
    """A PNG of an area of the screen, in screen pixels, and its size."""
    screen = default_screen(display)
    width, height = measure(wide, high)
    image = get_image(display, root_window(display, screen), x, y, wide, high, ALL_PLANES, Z_PIXMAP)
    if not image:
        raise Refused("The screen cannot be read right now.")
    try:
        rgb = colours(image.contents, width, height)
    finally:
        destroy_image(image)
    return png(width, height, rgb), width, height


def clip(area, bounds):
    """The part of area (x, y, width, height) inside bounds, or None."""
    left, top = max(area[0], bounds[0]), max(area[1], bounds[1])
    right, bottom = min(area[0] + area[2], bounds[0] + bounds[2]), min(area[1] + area[3], bounds[1] + bounds[3])
    return (left, top, right - left, bottom - top) if right > left and bottom > top else None


def region_of(arguments):
    region = arguments.get("region")
    try:
        values = [float(region[key]) for key in ("x", "y", "width", "height")]
    except (KeyError, TypeError, ValueError):
        raise Refused("region needs x, y, width and height, numbers in pixels of the latest full screenshot")
    if values[2] <= 0 or values[3] <= 0:
        raise Refused("region needs a width and height above 0")
    return values


def screenshot(arguments):
    if arguments.get("region") is not None and arguments.get("window") is not None:
        raise Refused("give region or window, not both")
    with connect() as display:
        if arguments.get("window") is not None:
            window = arguments["window"]
            listed = {entry["id"]: entry for entry in windows(display)}
            if not isinstance(window, int) or window not in listed:
                raise Refused("there is no such window; list_windows shows the windows and their ids")
            entry = listed[window]
            number = entry["display"]
            area = (entry["x"], entry["y"], entry["width"], entry["height"])
            label = f"Window {window} on display {number}"
        elif arguments.get("region") is not None:
            number = display_number(arguments)
            shot(display, number)
            area = region_of(arguments)
            label = f"Display {number}, region"
        else:
            number = display_number(arguments)
            left, top, wide, high, width, height = shots[number] = geometry(display, number)
            data, width, height = capture(display, left, top, wide, high)
            return [{"type": "image", "data": base64.b64encode(data).decode(), "mimeType": "image/png"},
                    {"type": "text", "text": f"Display {number}: {width}x{height} pixels, showing the area of "
                                             f"{wide}x{high} at ({left}, {top}) in desktop coordinates. Positions "
                                             f"for the other tools on display {number} are pixels of this picture."}]
        left, top, wide, high, width, height = shot(display, number)
        scale_x, scale_y = wide / width, high / height
        wanted = (left + round(area[0] * scale_x), top + round(area[1] * scale_y),
                  round(area[2] * scale_x), round(area[3] * scale_y))
        part = clip(wanted, (left, top, wide, high))
        if not part:
            raise Refused(f"that area is outside display {number}, which is {width}x{height} pixels in its screenshot")
        data, shown_w, shown_h = capture(display, *part)
    ax, ay = round((part[0] - left) / scale_x), round((part[1] - top) / scale_y)
    aw, ah = round(part[2] / scale_x), round(part[3] / scale_y)
    return [{"type": "image", "data": base64.b64encode(data).decode(), "mimeType": "image/png"},
            {"type": "text", "text": f"{label}: the area at ({ax}, {ay}) of {aw}x{ah} pixels of the latest full "
                                     f"screenshot, shown at {shown_w}x{shown_h} pixels. This picture is only for "
                                     f"looking closer: positions for the other tools stay pixels of the full "
                                     f"screenshot of display {number} ({width}x{height})."}]


def list_displays(_):
    with connect() as display:
        found = monitors(display)
        listed = []
        for number, (x, y, wide, high, _) in enumerate(found):
            width, height = measure(wide, high)
            listed.append({"display": number, "main": number == 0, "x": x, "y": y, "width": wide, "height": high,
                           "scale": 1, "screenshot_width": width, "screenshot_height": height})
    return json.dumps({"displays": listed}, ensure_ascii=False)


# Windows.
def atom(display, name):
    return intern_atom(display, name.encode(), 1)


def prop(display, window, name, kind=0):
    """A window property as (format, items): bytes for format 8, a list of numbers for 32; None if unset."""
    wanted = atom(display, name)
    if not wanted:
        return None
    actual, fmt, count, after, data = ulong(), c_int(), ulong(), ulong(), ctypes.c_void_p()
    if get_property(display, window, wanted, 0, 1 << 16, 0, kind, ctypes.byref(actual), ctypes.byref(fmt),
                    ctypes.byref(count), ctypes.byref(after), ctypes.byref(data)) != 0 or not data.value:
        return None
    try:
        if fmt.value == 8:
            return 8, ctypes.string_at(data.value, count.value)
        if fmt.value == 32:  # Xlib hands 32-bit items back as C longs
            return 32, list((ulong * count.value).from_address(data.value))
        return None
    finally:
        free(data)


def children(display, window):
    root, parent, kids, count = ulong(), ulong(), ctypes.POINTER(ulong)(), uint()
    if not query_tree(display, window, ctypes.byref(root), ctypes.byref(parent), ctypes.byref(kids),
                      ctypes.byref(count)):
        return [], 0
    try:
        return [kids[i] for i in range(count.value)], parent.value
    finally:
        if kids:
            free(kids)


def text_prop(display, window, name):
    found = prop(display, window, name)
    if not found or found[0] != 8:
        return ""
    raw = found[1]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def windows(display):
    """The visible top-level windows, front to back, with their areas in screen pixels."""
    screen = default_screen(display)
    root = root_window(display, screen)
    stacking = prop(display, root, "_NET_CLIENT_LIST_STACKING") or prop(display, root, "_NET_CLIENT_LIST")
    if stacking and stacking[0] == 32:
        clients = stacking[1]
    else:
        # No window manager that lists its windows: the mapped windows below
        # the root, or the windows a frame holds.
        clients = []
        for top in children(display, root)[0]:
            if prop(display, top, "WM_STATE"):
                clients.append(top)
                continue
            held = [kid for kid in children(display, top)[0] if prop(display, kid, "WM_STATE")]
            clients.append(held[0] if held else top)
    skip_types = {atom(display, "_NET_WM_WINDOW_TYPE_DESKTOP"), atom(display, "_NET_WM_WINDOW_TYPE_DOCK")} - {0}
    hidden = atom(display, "_NET_WM_STATE_HIDDEN")
    active = prop(display, root, "_NET_ACTIVE_WINDOW")
    focus = active[1][0] if active and active[0] == 32 and active[1] else 0
    if not focus:
        held, revert = ulong(), c_int()
        input_focus(display, ctypes.byref(held), ctypes.byref(revert))
        focus = held.value
    # The focus may be inside a window: walk up to a listed one.
    chain, step = set(), focus
    for _ in range(50):
        if step in (0, 1, root):
            break
        chain.add(step)
        step = children(display, step)[1]
    found = []
    for window in reversed(clients):
        attributes = WindowAttributes()
        if not window_attributes(display, window, ctypes.byref(attributes)) or attributes.map_state != VIEWABLE:
            continue
        if not stacking and attributes.override_redirect:
            continue
        kinds = prop(display, window, "_NET_WM_WINDOW_TYPE")
        if kinds and kinds[0] == 32 and skip_types & set(kinds[1]):
            continue
        states = prop(display, window, "_NET_WM_STATE")
        if hidden and states and states[0] == 32 and hidden in states[1]:
            continue
        x, y, child = c_int(), c_int(), ulong()
        if not translate(display, window, root, 0, 0, ctypes.byref(x), ctypes.byref(y), ctypes.byref(child)):
            continue
        left, top, wide, high = x.value, y.value, attributes.width, attributes.height
        frame = prop(display, window, "_NET_FRAME_EXTENTS")
        if frame and frame[0] == 32 and len(frame[1]) == 4:
            fl, fr, ft, fb = (int(v) for v in frame[1])
            left, top, wide, high = left - fl, top - ft, wide + fl + fr, high + ft + fb
        title = text_prop(display, window, "_NET_WM_NAME") or text_prop(display, window, "WM_NAME")
        names = prop(display, window, "WM_CLASS")
        app = ""
        if names and names[0] == 8:
            parts = [part for part in names[1].decode("utf-8", "replace").split("\0") if part]
            app = parts[-1] if parts else ""
        if not app:
            pid = prop(display, window, "_NET_WM_PID")
            if pid and pid[0] == 32 and pid[1]:
                try:
                    with open(f"/proc/{int(pid[1][0])}/comm", encoding="utf-8") as file:
                        app = file.read().strip()
                except OSError:
                    pass
        found.append({"window": window, "area": (left, top, wide, high), "app": app, "title": title,
                      "focused": window in chain})
    # Each window on the display that holds most of it, in that display's
    # screenshot pixels.
    displays = monitors(display)
    listed = []
    for entry in found:
        area = entry["area"]
        overlaps = [(part[2] * part[3] if part else 0, -n) for n, m in enumerate(displays)
                    for part in [clip(area, m[:4])]]
        best, negative = max(overlaps)
        if best == 0:
            continue  # wholly off every display
        number = -negative
        left, top, wide, high, width, height = shot(display, number)
        listed.append({"id": int(entry["window"]), "app": entry["app"], "title": entry["title"], "display": number,
                       "x": round((area[0] - left) * width / wide), "y": round((area[1] - top) * height / high),
                       "width": round(area[2] * width / wide), "height": round(area[3] * height / high),
                       "focused": entry["focused"]})
    return listed


def list_windows(_):
    with connect() as display:
        listed = windows(display)
    return json.dumps({"windows": listed}, ensure_ascii=False)


def pointer(display):
    root_back, child, rx, ry, wx, wy, mask = ulong(), ulong(), c_int(), c_int(), c_int(), c_int(), uint()
    query_pointer(display, root_window(display, default_screen(display)), ctypes.byref(root_back),
                  ctypes.byref(child), ctypes.byref(rx), ctypes.byref(ry), ctypes.byref(wx), ctypes.byref(wy),
                  ctypes.byref(mask))
    return rx.value, ry.value


def cursor_position(_):
    with connect() as display:
        number, x, y = where(display, *pointer(display))
    return json.dumps({"display": number, "x": x, "y": y})


# Mouse.
held_buttons = set()


def move_to(display, at):
    fake_motion(display, default_screen(display), at[0], at[1], 0)
    flush(display)


def button(display, number, pressed):
    fake_button(display, number, pressed, 0)
    flush(display)


def button_of(arguments):
    which = arguments.get("button") or "left"
    if which not in BUTTONS:
        raise Refused("button is left, right or middle")
    return which


def modifier_codes(display, names):
    held = []
    for name in names:
        code = keysym_code(display, MODIFIERS[name])
        if not code:
            raise Refused(f"the keyboard has no {name} key")
        if code not in held:
            held.append(code)
    return held


def modifier_names(arguments):
    names = arguments.get("modifiers") or []
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise Refused("modifiers is a list of modifier names, such as [\"shift\"]")
    names = [name.lower() for name in names]
    for name in names:
        if name not in MODIFIERS:
            raise Refused(f"unknown modifier {name}; use ctrl, shift, alt, meta or mod")
    return names


def move(arguments):
    with connect(input=True) as display:
        move_to(display, place(display, arguments))
    return "moved"


def click(arguments):
    which = button_of(arguments)
    count = arguments.get("count", 1)
    if count is None:
        count = 1
    if count not in (1, 2, 3) or isinstance(count, bool):
        raise Refused("count is 1, 2 or 3")
    names = modifier_names(arguments)
    with connect(input=True) as display:
        point = place(display, arguments)
        held = modifier_codes(display, names)
        move_to(display, point)
        time.sleep(0.05)
        for code in held:
            fake_key(display, code, 1, 0)
        try:
            for _ in range(count):
                for pressed in (True, False):
                    button(display, BUTTONS[which], pressed)
                    time.sleep(0.02)
        finally:
            for code in reversed(held):
                fake_key(display, code, 0, 0)
            flush(display)
    return "clicked"


def drag(arguments):
    which = button_of(arguments)
    with connect(input=True) as display:
        start, end = place(display, arguments, "from_x", "from_y"), place(display, arguments, "to_x", "to_y")
        move_to(display, start)
        time.sleep(0.05)
        button(display, BUTTONS[which], True)
        try:
            for step in range(1, 11):
                time.sleep(0.02)
                move_to(display, (round(start[0] + (end[0] - start[0]) * step / 10),
                                  round(start[1] + (end[1] - start[1]) * step / 10)))
            time.sleep(0.05)
        finally:
            button(display, BUTTONS[which], False)
    return "dragged"


def mouse_down(arguments):
    which = button_of(arguments)
    with connect(input=True) as display:
        button(display, BUTTONS[which], True)
    held_buttons.add(which)
    return f"holding the {which} button"


def mouse_up(arguments):
    which = button_of(arguments)
    with connect(input=True) as display:
        button(display, BUTTONS[which], False)
    held_buttons.discard(which)
    return f"let go of the {which} button"


def release_all():
    """Let go of buttons still held when the server stops."""
    if not held_buttons:
        return
    try:
        with connect(input=True) as display:
            for which in held_buttons:
                button(display, BUTTONS[which], False)
    except Refused:
        pass


def scroll(arguments):
    try:
        down, right = int(arguments.get("down") or 0), int(arguments.get("right") or 0)
    except (TypeError, ValueError):
        raise Refused("down and right must be whole numbers of wheel notches")
    if not -100 <= down <= 100 or not -100 <= right <= 100 or (down == 0 and right == 0):
        raise Refused("give down or right, between -100 and 100 wheel notches")
    with connect(input=True) as display:
        point = place(display, arguments)
        move_to(display, point)
        time.sleep(0.05)
        # The wheel is buttons 4 and 5, and 6 and 7 sideways, one click a notch.
        for steps, forward, back in ((down, 5, 4), (right, 7, 6)):
            for _ in range(abs(steps)):
                for pressed in (True, False):
                    button(display, forward if steps > 0 else back, pressed)
                time.sleep(0.01)
    return "scrolled"


# Keyboard.
def keysym(character):
    """The keysym of a character, or None for a control character other than newline and tab."""
    if character == "\n":
        return KEYS["return"]
    if character == "\t":
        return KEYS["tab"]
    point = ord(character)
    if point < 0x20 or 0x7F <= point < 0xA0:
        return None
    return point if point < 0x100 else 0x01000000 + point


# How long a borrowed key rests after its last press before it is given
# another character. A program that is behind reads the keys as they are when
# it catches up, so a key changed too soon would type the wrong character.
REST = 0.3


class Keyboard:
    """The keys of the keyboard for one call. A character no key produces is
    put on a key that produces nothing until the call ends, so typing does not
    depend on the keyboard layout or the clipboard."""

    def __init__(self, display):
        self.display = display
        low, high, per = c_int(), c_int(), c_int()
        keycodes(display, ctypes.byref(low), ctypes.byref(high))
        count = high.value - low.value + 1
        table = get_mapping(display, low.value, count, ctypes.byref(per))
        if not table:
            raise Refused("The keyboard layout cannot be read.")
        try:
            symbols = table[:count * per.value]
        finally:
            free(table)
        self.per = per.value
        keys = [symbols[i * self.per:(i + 1) * self.per] for i in range(count)]
        state = KeyboardState()
        group, self.locked, self.released = 0, False, False
        if keyboard_state(display, CORE_KEYBOARD, ctypes.byref(state)) == 0:
            group, self.locked = state.group, bool(state.locked_mods & LOCK)
        self.shift = keysym_code(display, SHIFT)
        # Keysyms the keyboard already has: on which key, and whether with
        # shift. With another layout group active, the first group's keys
        # would type something else, so only keys outside the characters are
        # taken then.
        self.found = {}
        for level in (0, 1) if self.shift else (0,):
            for index, symbols in enumerate(keys):
                symbol = symbols[level] if level < len(symbols) else 0
                if symbol and symbol not in self.found and (group == 0 or symbol >= 0xFF00):
                    self.found[symbol] = (low.value + index, level == 1)
        # Each key that produces nothing can carry two characters, the
        # second typed with shift.
        spare = [low.value + index for index, symbols in enumerate(keys) if not any(symbols)]
        self.free = [(code, 0) for code in spare] + ([(code, 1) for code in spare] if self.shift else [])
        self.carries = {code: [0, 0] for code in spare}
        self.borrowed, self.holder, self.used = {}, {}, {}

    def press(self, code, pressed):
        fake_key(self.display, code, pressed, 0)
        flush(self.display)

    @staticmethod
    def rest(since):
        wait = since + REST - time.monotonic()
        if wait > 0:
            time.sleep(wait)

    def borrow(self, symbol):
        """Put a keysym on a key that produces nothing, or on the borrowed key pressed longest ago."""
        if self.free:
            place = self.free.pop(0)
        elif self.holder:
            place = min(self.holder, key=self.used.__getitem__)
            del self.borrowed[self.holder.pop(place)]
            self.rest(self.used[place])
        else:
            raise Refused("The keyboard has no unused key to type this character with.")
        code, level = place
        self.carries[code][level] = symbol
        # A key with one letter alone types it lowercase, so until the key
        # carries a second character, it carries the first twice.
        first, second = self.carries[code]
        change_mapping(self.display, code, 2, (ulong * 2)(first, second or first), 1)
        sync(self.display, 0)
        self.borrowed[symbol], self.holder[place], self.used[place] = place, symbol, time.monotonic()
        time.sleep(0.02)  # for programs to take in the changed key

    def unlock(self):
        """Release caps lock, if it is on, until close: it would change the case of what is typed."""
        if self.locked and not self.released:
            lock_modifiers(self.display, CORE_KEYBOARD, LOCK, 0)
            sync(self.display, 0)
            self.released = True

    def close(self):
        """Return the borrowed keys to producing nothing, once programs have had time to read them."""
        if self.used:
            sync(self.display, 0)
            self.rest(max(self.used.values()) + 0.2)
            for code in {code for code, _ in self.used}:
                change_mapping(self.display, code, self.per, (ulong * self.per)(), 1)
            sync(self.display, 0)
            self.borrowed, self.holder, self.used = {}, {}, {}
        if self.released:
            lock_modifiers(self.display, CORE_KEYBOARD, LOCK, LOCK)
            self.released = False

    def tap(self, symbol, held=()):
        if symbol not in self.found and symbol not in self.borrowed:
            self.borrow(symbol)
        place = self.borrowed.get(symbol)
        code, shifted = (place[0], place[1] == 1) if place else self.found[symbol]
        if shifted and self.shift not in held:
            held = (*held, self.shift)
        for modifier in held:
            self.press(modifier, True)
        try:
            self.press(code, True)
            time.sleep(0.001)
            self.press(code, False)
        finally:
            for modifier in reversed(held):
                self.press(modifier, False)
        if place:
            self.used[place] = time.monotonic()
        time.sleep(0.002)


def type_text(arguments):
    text = arguments.get("text")
    if not isinstance(text, str) or not text or len(text) > 5000:
        raise Refused("text must be 1 to 5000 characters")
    symbols = [s for s in map(keysym, text.replace("\r\n", "\n").replace("\r", "\n")) if s is not None]
    with connect(input=True) as display:
        keyboard = Keyboard(display)
        try:
            keyboard.unlock()
            for symbol in symbols:
                keyboard.tap(symbol)
        finally:
            keyboard.close()
    return "typed"


def split_keys(keys):
    """Modifier names and the key of a combination such as ctrl+shift+a or ctrl++."""
    keys = keys.lower()
    if keys == "+" or keys.endswith("++"):
        return [name for name in keys[:-2].split("+") if name] if keys != "+" else [], "+"
    names = keys.split("+")
    return names[:-1], names[-1]


def press_key(arguments):
    keys = arguments.get("keys")
    if not isinstance(keys, str) or not keys:
        raise Refused("keys is a key, or modifiers and a key joined by +, such as mod+c")
    names, last = split_keys(keys)
    if last in KEYS:
        symbol = KEYS[last]
    elif len(last) == 1 and keysym(last) is not None:
        symbol = keysym(last)
    else:
        raise Refused(f"unknown key {last}")
    for name in names:
        if name not in MODIFIERS:
            raise Refused(f"unknown modifier {name}; use ctrl, shift, alt, meta or mod")
    with connect(input=True) as display:
        held = modifier_codes(display, names)
        keyboard = Keyboard(display)
        try:
            keyboard.tap(symbol, tuple(held))
        finally:
            keyboard.close()
    return "pressed"


def wait(arguments):
    seconds = arguments.get("seconds")
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not 0 <= seconds <= 30:
        raise Refused("seconds is a number from 0 to 30")
    time.sleep(seconds)
    return "done waiting"


HANDLERS = {"screenshot": screenshot, "list_displays": list_displays, "list_windows": list_windows,
            "cursor_position": cursor_position, "click": click, "move_pointer": move, "drag": drag,
            "mouse_down": mouse_down, "mouse_up": mouse_up, "scroll": scroll, "type_text": type_text,
            "press_key": press_key, "wait": wait}


def load_tools():
    with open(os.path.join(HERE, "tools.json"), encoding="utf-8") as file:
        tools = json.loads(file.read().replace("{computer}", SUBJECT))["tools"]
    # A tool's text that names another tool names it as listed. Only names
    # with an underscore are tool names in the text; "screenshot" alone is
    # also the plain word.
    named = [other for other in HANDLERS if "_" in other] if PREFIX else []
    for tool in tools:
        tool["name"] = PREFIX + tool["name"]
        for other in named:
            tool["description"] = re.sub(rf"\b{other}\b", PREFIX + other, tool["description"])
            for spec in tool["inputSchema"]["properties"].values():
                if "description" in spec:
                    spec["description"] = re.sub(rf"\b{other}\b", PREFIX + other, spec["description"])
    return tools


TOOLS = load_tools()


def answer(message):
    method = message.get("method")
    if method == "initialize":
        return {"protocolVersion": message["params"]["protocolVersion"], "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER, "version": VERSION}}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        name = message["params"].get("name", "")
        function = HANDLERS.get(name[len(PREFIX):]) if name.startswith(PREFIX) else None
        if function is None:
            return None
        try:
            result = function(message["params"].get("arguments") or {})
        except Refused as refusal:
            return {"content": [{"type": "text", "text": str(refusal)}], "isError": True}
        except OSError as failure:
            return {"content": [{"type": "text", "text": f"failed: {failure}"}], "isError": True}
        return {"content": result if isinstance(result, list) else [{"type": "text", "text": result}]}
    if method == "ping":
        return {}
    return None


def main():
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            request = json.loads(line)
            if "id" not in request:
                continue  # a notification needs no reply
            result = answer(request)
            reply = {"jsonrpc": "2.0", "id": request["id"]}
            if result is None:
                reply["error"] = {"code": -32601, "message": "method not found"}
            else:
                reply["result"] = result
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
    finally:
        release_all()


if __name__ == "__main__":
    main()
