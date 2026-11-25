# An MCP server on standard input and output that takes pictures of the
# screen and sends mouse and keyboard input. macOS only; it needs nothing
# beyond Python's standard library and the system's own frameworks.
#
# The tools are described in tools.json beside this file, which the Windows
# and Linux versions read as well, so all three offer the same tools.
import base64
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time

VERSION = "0.3.4"
# The longest edge of a picture handed back, in pixels.
LONGEST = 1568
HERE = os.path.dirname(os.path.abspath(__file__))
SUBJECT = "the user's computer"

cg = ctypes.CDLL("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")


class Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class Size(ctypes.Structure):
    _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]


class Rect(ctypes.Structure):
    _fields_ = [("origin", Point), ("size", Size)]


def declare(library, name, result, *arguments):
    function = getattr(library, name)
    function.restype, function.argtypes = result, list(arguments)
    return function


ref, u16, u32, i32, size_t = ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint32, ctypes.c_int32, ctypes.c_size_t
index = ctypes.c_long  # CFIndex
mouse_event = declare(cg, "CGEventCreateMouseEvent", ref, ref, u32, Point, u32)
key_event = declare(cg, "CGEventCreateKeyboardEvent", ref, ref, u16, ctypes.c_bool)
set_unicode = declare(cg, "CGEventKeyboardSetUnicodeString", None, ref, ctypes.c_ulong, ctypes.POINTER(u16))
scroll_event = declare(cg, "CGEventCreateScrollWheelEvent2", ref, ref, u32, u32, i32, i32, i32)
new_event = declare(cg, "CGEventCreate", ref, ref)
event_location = declare(cg, "CGEventGetLocation", Point, ref)
set_flags = declare(cg, "CGEventSetFlags", None, ref, ctypes.c_uint64)
set_field = declare(cg, "CGEventSetIntegerValueField", None, ref, u32, ctypes.c_int64)
post = declare(cg, "CGEventPost", None, u32, ref)
main_display = declare(cg, "CGMainDisplayID", u32)
active_displays = declare(cg, "CGGetActiveDisplayList", i32, u32, ctypes.POINTER(u32), ctypes.POINTER(u32))
display_bounds = declare(cg, "CGDisplayBounds", Rect, u32)
mirrors = declare(cg, "CGDisplayMirrorsDisplay", u32, u32)
copy_mode = declare(cg, "CGDisplayCopyDisplayMode", ref, u32)
mode_pixels_wide = declare(cg, "CGDisplayModeGetPixelWidth", size_t, ref)
mode_wide = declare(cg, "CGDisplayModeGetWidth", size_t, ref)
release_mode = declare(cg, "CGDisplayModeRelease", None, ref)
window_info = declare(cg, "CGWindowListCopyWindowInfo", ref, u32, u32)
rect_from = declare(cg, "CGRectMakeWithDictionaryRepresentation", ctypes.c_bool, ref, ctypes.POINTER(Rect))
may_see = declare(cg, "CGPreflightScreenCaptureAccess", ctypes.c_bool)
ask_to_see = declare(cg, "CGRequestScreenCaptureAccess", ctypes.c_bool)
may_act = declare(cg, "AXIsProcessTrusted", ctypes.c_bool)
may_act_asking = declare(cg, "AXIsProcessTrustedWithOptions", ctypes.c_bool, ref)
release = declare(cf, "CFRelease", None, ref)
array_count = declare(cf, "CFArrayGetCount", index, ref)
array_item = declare(cf, "CFArrayGetValueAtIndex", ref, ref, index)
dictionary_value = declare(cf, "CFDictionaryGetValue", ref, ref, ref)
type_of = declare(cf, "CFGetTypeID", ctypes.c_ulong, ref)
string_type = declare(cf, "CFStringGetTypeID", ctypes.c_ulong)
number_type = declare(cf, "CFNumberGetTypeID", ctypes.c_ulong)
number_value = declare(cf, "CFNumberGetValue", ctypes.c_bool, ref, index, ctypes.c_void_p)
string_length = declare(cf, "CFStringGetLength", index, ref)
string_most = declare(cf, "CFStringGetMaximumSizeForEncoding", index, index, u32)
string_bytes = declare(cf, "CFStringGetCString", ctypes.c_bool, ref, ctypes.c_char_p, index, u32)
cf.CFDictionaryCreate.restype = ref
cf.CFDictionaryCreate.argtypes = [ref, ctypes.POINTER(ref), ctypes.POINTER(ref), index, ref, ref]
UTF8, SINT64, DOUBLE = 0x08000100, 4, 13
ON_SCREEN_ONLY, EXCLUDE_DESKTOP = 1 << 0, 1 << 4


def ask_to_act():
    """Have the system show its own request, which lists the application in Settings."""
    key, yes = ref.in_dll(cg, "kAXTrustedCheckOptionPrompt"), ref.in_dll(cf, "kCFBooleanTrue")
    options = cf.CFDictionaryCreate(None, ctypes.byref(key), ctypes.byref(yes), 1,
                                    ctypes.addressof(ref.in_dll(cf, "kCFTypeDictionaryKeyCallBacks")),
                                    ctypes.addressof(ref.in_dll(cf, "kCFTypeDictionaryValueCallBacks")))
    if options:
        may_act_asking(options)
        release(options)


# Event types: down, up, dragged; and the button's number.
BUTTONS = {"left": (1, 2, 6, 0), "right": (3, 4, 7, 1), "middle": (25, 26, 27, 2)}
MOVED, CLICK_STATE, LINE = 5, 1, 1  # LINE: kCGScrollEventUnitLine
CMD, SHIFT, CTRL, ALT = 0x100000, 0x20000, 0x40000, 0x80000
MODIFIERS = {"ctrl": CTRL, "control": CTRL, "shift": SHIFT, "alt": ALT, "option": ALT, "meta": CMD, "cmd": CMD,
             "command": CMD, "win": CMD, "windows": CMD, "super": CMD, "mod": CMD}
# Key codes by position on a US keyboard.
KEYS = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9, "b": 11, "q": 12, "w": 13,
    "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25,
    "7": 26, "-": 27, "8": 28, "0": 29, "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35, "l": 37, "j": 38,
    "'": 39, "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44, "n": 45, "m": 46, ".": 47, "`": 50,
    "return": 36, "enter": 36, "tab": 48, "space": 49, "backspace": 51, "delete": 117, "insert": 114,
    "escape": 53, "esc": 53, "left": 123, "right": 124, "down": 125, "up": 126, "home": 115, "end": 119,
    "pageup": 116, "pagedown": 121, "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98,
    "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
}
# Characters typed with shift on a US keyboard, and the key they are on.
SHIFTED = dict(zip('~!@#$%^&*()_+{}|:"<>?', "`1234567890-=[]\\;',./"))
# Lines one wheel notch scrolls, about what one notch scrolls on Windows and Linux.
LINES_PER_NOTCH = 3
# UTF-16 units handed over with one key event when typing.
CHUNK = 20


class Refused(Exception):
    pass


def send(event):
    if not event:
        raise Refused("the system did not accept the input")
    post(0, event)
    release(event)


def need_input():
    if not may_act():
        ask_to_act()
        raise Refused("Input is not allowed yet. In System Settings > Privacy & Security > Accessibility, turn on the "
                      "application that runs this tool, then try again.")


def need_screen():
    if not may_see():
        ask_to_see()
        raise Refused("Seeing the screen is not allowed yet. In System Settings > Privacy & Security > Screen & System "
                      "Audio Recording, turn on the application that runs this tool, restart it, then try again.")


# Displays and positions. A position is in pixels of the latest full
# screenshot of a display; what each screenshot covered is kept here, so
# positions keep meaning what the picture showed.
shots = {}


def measure(wide, high):
    """The size of a picture of an area, at most LONGEST pixels on its longest side."""
    shrink = max(1.0, max(wide, high) / LONGEST)
    return max(1, round(wide / shrink)), max(1, round(high / shrink))


def monitors():
    """The displays as (x, y, width, height, scale, main) in points, main first, then from left to right."""
    ids, count = (u32 * 32)(), u32()
    if active_displays(32, ids, ctypes.byref(count)) != 0:
        raise Refused("The displays cannot be read right now.")
    main = main_display()
    found = []
    for number in ids[:count.value]:
        if mirrors(number) != 0:
            continue  # shows the same as another display
        bounds = display_bounds(number)
        scale, mode = 1.0, copy_mode(number)
        if mode:
            try:
                points = mode_wide(mode)
                if points:
                    scale = mode_pixels_wide(mode) / points
            finally:
                release_mode(mode)
        found.append((bounds.origin.x, bounds.origin.y, bounds.size.width, bounds.size.height, scale,
                      number == main))
    if not found:
        raise Refused("No display is active.")
    found.sort(key=lambda m: (m[0], m[1]))
    first = next((m for m in found if m[5]), found[0])
    return [first] + [m for m in found if m is not first]


def geometry(number):
    """What a full screenshot of a display covers: x, y, width, height in points, and the picture's size."""
    found = monitors()
    if not 0 <= number < len(found):
        raise Refused(f"there is no display {number}; list_displays shows the displays")
    x, y, wide, high, scale, _ = found[number]
    return (x, y, wide, high, *measure(round(wide * scale), round(high * scale)))


def shot(number):
    """The latest full screenshot of a display, or what one would cover now."""
    return shots.get(number) or geometry(number)


def display_number(arguments):
    number = arguments.get("display", 0)
    if number is None:
        number = 0
    if not isinstance(number, int) or isinstance(number, bool) or number < 0:
        raise Refused("display must be a whole number, as list_displays shows")
    return number


def place(arguments, x="x", y="y"):
    """A position given in pixels of a screenshot, as a point of the desktop."""
    try:
        px, py = float(arguments[x]), float(arguments[y])
    except (KeyError, TypeError, ValueError):
        raise Refused(f"{x} and {y} must be numbers, in pixels of the latest screenshot")
    left, top, wide, high, width, height = shot(display_number(arguments))
    if not (0 <= px <= width and 0 <= py <= height):
        raise Refused(f"that position is outside the display, which is {width}x{height} pixels in its screenshot")
    return Point(min(left + px * wide / width, left + wide - 1), min(top + py * high / height, top + high - 1))


def where(at):
    """The display a point of the desktop is on, and the point in pixels of its screenshot."""
    found = monitors()
    inside = [n for n, m in enumerate(found) if m[0] <= at.x < m[0] + m[2] and m[1] <= at.y < m[1] + m[3]]
    number = inside[0] if inside else 0
    left, top, wide, high, width, height = shot(number)
    return number, round((at.x - left) * width / wide), round((at.y - top) * height / high)


def jpeg_size(data):
    """The width and height in a JPEG's frame header."""
    at = 2
    while at + 9 < len(data):
        if data[at] != 0xFF:
            break
        marker, length = data[at + 1], int.from_bytes(data[at + 2:at + 4], "big")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            return int.from_bytes(data[at + 7:at + 9], "big"), int.from_bytes(data[at + 5:at + 7], "big")
        at += 2 + length
    raise Refused("The picture of the screen could not be read.")


def capture(x, y, wide, high):
    """A JPEG of an area of the desktop given in points, at most LONGEST pixels on its longest side."""
    need_screen()
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "screen.jpg")
        area = f"{x:g},{y:g},{wide:g},{high:g}"
        subprocess.run(["/usr/sbin/screencapture", "-x", "-t", "jpg", "-R" + area, path], check=True, timeout=20,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open(path, "rb") as file:
            data = file.read()
        width, height = jpeg_size(data)
        wanted = measure(width, height)
        if wanted != (width, height):
            subprocess.run(["/usr/bin/sips", "-z", str(wanted[1]), str(wanted[0]), path], check=True, timeout=20,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with open(path, "rb") as file:
                data = file.read()
            width, height = jpeg_size(data)
    return data, width, height


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


def image(data):
    return {"type": "image", "data": base64.b64encode(data).decode(), "mimeType": "image/jpeg"}


def screenshot(arguments):
    if arguments.get("region") is not None and arguments.get("window") is not None:
        raise Refused("give region or window, not both")
    if arguments.get("window") is not None:
        window = arguments["window"]
        listed = {entry["id"]: entry for entry in windows()}
        if not isinstance(window, int) or window not in listed:
            raise Refused("there is no such window; list_windows shows the windows and their ids")
        entry = listed[window]
        number = entry["display"]
        area = (entry["x"], entry["y"], entry["width"], entry["height"])
        label = f"Window {window} on display {number}"
    elif arguments.get("region") is not None:
        number = display_number(arguments)
        shot(number)
        area = region_of(arguments)
        label = f"Display {number}, region"
    else:
        number = display_number(arguments)
        left, top, wide, high, width, height = geometry(number)
        data, width, height = capture(left, top, wide, high)
        shots[number] = (left, top, wide, high, width, height)
        return [image(data), {"type": "text", "text": f"Display {number}: {width}x{height} pixels, showing the area "
                                                      f"of {wide:g}x{high:g} at ({left:g}, {top:g}) in desktop "
                                                      f"coordinates. Positions for the other tools on display "
                                                      f"{number} are pixels of this picture."}]
    left, top, wide, high, width, height = shot(number)
    scale_x, scale_y = wide / width, high / height
    wanted = (left + round(area[0] * scale_x), top + round(area[1] * scale_y),
              round(area[2] * scale_x), round(area[3] * scale_y))
    part = clip(wanted, (left, top, wide, high))
    if not part:
        raise Refused(f"that area is outside display {number}, which is {width}x{height} pixels in its screenshot")
    data, shown_w, shown_h = capture(*part)
    ax, ay = round((part[0] - left) / scale_x), round((part[1] - top) / scale_y)
    aw, ah = round(part[2] / scale_x), round(part[3] / scale_y)
    return [image(data), {"type": "text", "text": f"{label}: the area at ({ax}, {ay}) of {aw}x{ah} pixels of the "
                                                  f"latest full screenshot, shown at {shown_w}x{shown_h} pixels. This "
                                                  f"picture is only for looking closer: positions for the other tools "
                                                  f"stay pixels of the full screenshot of display {number} "
                                                  f"({width}x{height})."}]


def list_displays(_):
    listed = []
    for number, (x, y, wide, high, scale, _) in enumerate(monitors()):
        width, height = measure(round(wide * scale), round(high * scale))
        scale = round(scale, 2)
        listed.append({"display": number, "main": number == 0, "x": round(x), "y": round(y), "width": round(wide),
                       "height": round(high), "scale": int(scale) if scale == int(scale) else scale,
                       "screenshot_width": width,
                       "screenshot_height": height})
    return json.dumps({"displays": listed}, ensure_ascii=False)


# Windows.
def key_string(name):
    return ref.in_dll(cg, name).value


def cf_text(value):
    if not value or type_of(value) != string_type():
        return ""
    size = string_most(string_length(value), UTF8) + 1
    buffer = ctypes.create_string_buffer(size)
    return buffer.value.decode("utf-8", "replace") if string_bytes(value, buffer, size, UTF8) else ""


def cf_number(value, kind=SINT64):
    if not value or type_of(value) != number_type():
        return None
    out = ctypes.c_int64() if kind == SINT64 else ctypes.c_double()
    return out.value if number_value(value, kind, ctypes.byref(out)) else None


def windows():
    """The visible windows, front to back, in pixels of their display's screenshot.

    The system lists windows front to back; the first ordinary window is the
    one in front, which has the keyboard focus."""
    info = window_info(ON_SCREEN_ONLY | EXCLUDE_DESKTOP, 0)
    if not info:
        return []
    keys = {name: key_string(name) for name in ("kCGWindowNumber", "kCGWindowLayer", "kCGWindowAlpha",
                                                "kCGWindowBounds", "kCGWindowOwnerName", "kCGWindowName")}
    found = []
    try:
        for i in range(array_count(info)):
            entry = array_item(info, i)
            if cf_number(dictionary_value(entry, keys["kCGWindowLayer"])) != 0:
                continue  # menus, the menu bar, the Dock and other layers
            alpha = cf_number(dictionary_value(entry, keys["kCGWindowAlpha"]), DOUBLE)
            if alpha is not None and alpha <= 0:
                continue
            bounds = Rect()
            if not rect_from(dictionary_value(entry, keys["kCGWindowBounds"]), ctypes.byref(bounds)):
                continue
            if bounds.size.width < 2 or bounds.size.height < 2:
                continue
            found.append({"id": cf_number(dictionary_value(entry, keys["kCGWindowNumber"])),
                          "app": cf_text(dictionary_value(entry, keys["kCGWindowOwnerName"])),
                          "title": cf_text(dictionary_value(entry, keys["kCGWindowName"])),
                          "area": (bounds.origin.x, bounds.origin.y, bounds.size.width, bounds.size.height)})
    finally:
        release(info)
    displays = monitors()
    listed = []
    for entry in found:
        area = entry["area"]
        overlaps = [(part[2] * part[3] if part else 0, -n) for n, m in enumerate(displays)
                    for part in [clip(area, m[:4])]]
        best, negative = max(overlaps)
        if best == 0:
            continue  # wholly off every display
        number = -negative
        left, top, wide, high, width, height = shot(number)
        listed.append({"id": entry["id"], "app": entry["app"], "title": entry["title"], "display": number,
                       "x": round((area[0] - left) * width / wide), "y": round((area[1] - top) * height / high),
                       "width": round(area[2] * width / wide), "height": round(area[3] * height / high),
                       "focused": not listed})
    return listed


def list_windows(_):
    return json.dumps({"windows": windows()}, ensure_ascii=False)


def pointer():
    event = new_event(None)
    if not event:
        raise Refused("The pointer cannot be found right now.")
    try:
        return event_location(event)
    finally:
        release(event)


def cursor_position(_):
    number, x, y = where(pointer())
    return json.dumps({"display": number, "x": x, "y": y})


# Mouse.
held_buttons = []


def button_of(arguments):
    which = arguments.get("button") or "left"
    if which not in BUTTONS:
        raise Refused("button is left, right or middle")
    return which


def modifier_flags(arguments):
    names = arguments.get("modifiers") or []
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise Refused("modifiers is a list of modifier names, such as [\"shift\"]")
    flags = 0
    for name in (name.lower() for name in names):
        if name not in MODIFIERS:
            raise Refused(f"unknown modifier {name}; use ctrl, shift, alt, meta or mod")
        flags |= MODIFIERS[name]
    return flags


def mouse(kind, at, number=0, flags=None, press=None):
    event = mouse_event(None, kind, at, number)
    if event:
        if flags is not None:
            set_flags(event, flags)
        if press is not None:
            set_field(event, CLICK_STATE, press)  # which click of a double or triple click this is
    send(event)


def move_to(at):
    """Move the pointer; with a button held, as a drag of that button."""
    if held_buttons:
        _, _, dragged, number = BUTTONS[held_buttons[0]]
        mouse(dragged, at, number)
    else:
        mouse(MOVED, at)


def move(arguments):
    need_input()
    move_to(place(arguments))
    return "moved"


def click(arguments):
    need_input()
    which = button_of(arguments)
    count = arguments.get("count", 1)
    if count is None:
        count = 1
    if count not in (1, 2, 3) or isinstance(count, bool):
        raise Refused("count is 1, 2 or 3")
    flags = modifier_flags(arguments) or None
    point = place(arguments)
    down, up, _, number = BUTTONS[which]
    mouse(MOVED, point, 0, flags)
    time.sleep(0.05)
    for press in range(1, count + 1):
        for kind in (down, up):
            mouse(kind, point, number, flags, press)
            time.sleep(0.02)
    return "clicked"


def drag(arguments):
    need_input()
    which = button_of(arguments)
    start, end = place(arguments, "from_x", "from_y"), place(arguments, "to_x", "to_y")
    down, up, dragged, number = BUTTONS[which]
    mouse(MOVED, start)
    time.sleep(0.05)
    mouse(down, start, number)
    try:
        for step in range(1, 11):
            time.sleep(0.02)
            mouse(dragged, Point(start.x + (end.x - start.x) * step / 10, start.y + (end.y - start.y) * step / 10),
                  number)
        time.sleep(0.05)
    finally:
        mouse(up, end, number)
    return "dragged"


def mouse_down(arguments):
    need_input()
    which = button_of(arguments)
    down, _, _, number = BUTTONS[which]
    mouse(down, pointer(), number)
    if which not in held_buttons:
        held_buttons.append(which)
    return f"holding the {which} button"


def mouse_up(arguments):
    need_input()
    which = button_of(arguments)
    _, up, _, number = BUTTONS[which]
    mouse(up, pointer(), number)
    if which in held_buttons:
        held_buttons.remove(which)
    return f"let go of the {which} button"


def release_all():
    """Let go of buttons still held when the server stops."""
    for which in list(held_buttons):
        try:
            _, up, _, number = BUTTONS[which]
            mouse(up, pointer(), number)
        except Refused:
            pass
    del held_buttons[:]


def scroll(arguments):
    need_input()
    try:
        down, right = int(arguments.get("down") or 0), int(arguments.get("right") or 0)
    except (TypeError, ValueError):
        raise Refused("down and right must be whole numbers of wheel notches")
    if not -100 <= down <= 100 or not -100 <= right <= 100 or (down == 0 and right == 0):
        raise Refused("give down or right, between -100 and 100 wheel notches")
    mouse(MOVED, place(arguments))
    time.sleep(0.05)
    # One event a notch, in lines; positive wheel values scroll up and left.
    for _ in range(abs(down)):
        send(scroll_event(None, LINE, 1, -LINES_PER_NOTCH if down > 0 else LINES_PER_NOTCH, 0, 0))
        time.sleep(0.01)
    for _ in range(abs(right)):
        send(scroll_event(None, LINE, 2, 0, -LINES_PER_NOTCH if right > 0 else LINES_PER_NOTCH, 0))
        time.sleep(0.01)
    return "scrolled"


# Keyboard.
def key(code, flags=0):
    for pressed in (True, False):
        event = key_event(None, code, pressed)
        if event:
            set_flags(event, flags)
        send(event)
        time.sleep(0.02)


def unicode_keys(text):
    """Type text as characters carried by key events, CHUNK UTF-16 units at a time, so neither the
    keyboard layout nor the clipboard is involved."""
    raw = text.encode("utf-16-le")
    units = [int.from_bytes(raw[i:i + 2], "little") for i in range(0, len(raw), 2)]
    start = 0
    while start < len(units):
        end = min(start + CHUNK, len(units))
        if end < len(units) and 0xD800 <= units[end - 1] <= 0xDBFF:
            end -= 1  # keep the two halves of a character together
        chunk = (u16 * (end - start))(*units[start:end])
        for pressed in (True, False):
            event = key_event(None, 0, pressed)
            if event:
                set_flags(event, 0)
                set_unicode(event, end - start, chunk)
            send(event)
        time.sleep(0.01)
        start = end


def type_text(arguments):
    need_input()
    text = arguments.get("text")
    if not isinstance(text, str) or not text or len(text) > 5000:
        raise Refused("text must be 1 to 5000 characters")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    run = []
    for character in text + "\0":
        point = ord(character)
        if character in "\n\t\0":
            if run:
                unicode_keys("".join(run))
                run = []
            if character == "\n":
                key(KEYS["return"])
            elif character == "\t":
                key(KEYS["tab"])
        elif point >= 0x20 and not 0x7F <= point < 0xA0:
            run.append(character)
    return "typed"


def split_keys(keys):
    """Modifier names and the key of a combination such as ctrl+shift+a or ctrl++."""
    keys = keys.lower()
    if keys == "+" or keys.endswith("++"):
        return [name for name in keys[:-2].split("+") if name] if keys != "+" else [], "+"
    names = keys.split("+")
    return names[:-1], names[-1]


def press_key(arguments):
    need_input()
    keys = arguments.get("keys")
    if not isinstance(keys, str) or not keys:
        raise Refused("keys is a key, or modifiers and a key joined by +, such as mod+c")
    names, last = split_keys(keys)
    flags = 0
    for name in names:
        if name not in MODIFIERS:
            raise Refused(f"unknown modifier {name}; use ctrl, shift, alt, meta or mod")
        flags |= MODIFIERS[name]
    if last in KEYS:
        key(KEYS[last], flags)
    elif last in SHIFTED:
        key(KEYS[SHIFTED[last]], flags | SHIFT)
    elif len(last) == 1 and ord(last) >= 0x20 and not names:
        unicode_keys(last)  # a character no key of a US keyboard has
    else:
        raise Refused(f"unknown key {last}")
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

with open(os.path.join(HERE, "tools.json"), encoding="utf-8") as tools_file:
    TOOLS = json.loads(tools_file.read().replace("{computer}", SUBJECT))["tools"]


def answer(message):
    method = message.get("method")
    if method == "initialize":
        return {"protocolVersion": message["params"]["protocolVersion"], "capabilities": {"tools": {}},
                "serverInfo": {"name": "desktop-control", "version": VERSION}}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        function = HANDLERS.get(message["params"].get("name"))
        if function is None:
            return None
        try:
            result = function(message["params"].get("arguments") or {})
        except Refused as refusal:
            return {"content": [{"type": "text", "text": str(refusal)}], "isError": True}
        except (subprocess.SubprocessError, OSError) as failure:
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
