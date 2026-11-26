"""One host-side decision per Unity menu request. This helper never calls Unity."""
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import unicodedata

APPROVED = 23
REVIEW_SECONDS = 90
DENIED = "Menu not executed: approval was declined, cancelled, timed out, or unavailable."


def validate_path(path):
    if not isinstance(path, str) or not 3 <= len(path) <= 240:
        raise ValueError("Expected a complete Unity menu path")
    if unicodedata.normalize("NFKC", path) != path or not path.isprintable():
        raise ValueError("Use a visible, canonical menu path")
    parts = path.split("/")
    if len(parts) < 2 or any(not part or part != part.strip() or part in {".", ".."} for part in parts):
        raise ValueError("Use an exact slash-separated menu path")
    if any(char in path for char in "\\:<>"):
        raise ValueError("Invalid menu path")
    folded = path.casefold()
    if (parts[0].casefold() in {"help", "帮助", "幫助"} or
            any(word in folded for word in ("blender", "documentation", "文档", "文件總管", "文檔", "手册", "手冊")) or
            re.search(r"\b(?:docs?|manual|explorer|finder|browser|terminal)\b", folded) or
            folded in {"file/quit", "assets/open", "assets/open c# project"}):
        raise ValueError("Document and external application menu entries are blocked")


def ask_once(project, path, cancelled):
    # No command-line interpolation. Unavailable UI, helper failure and ordinary
    # process exit all deny. Only the affirmative button produces APPROVED.
    if cancelled.is_set() or not project.isprintable() or len(project) > 160:
        return False
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        with subprocess.Popen([sys.executable, "-I", str(Path(__file__).resolve())],
                              stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, creationflags=flags) as dialog:
            try:
                dialog.stdin.write(json.dumps([project, path]).encode("ascii"))
                dialog.stdin.close()
                deadline = time.monotonic() + REVIEW_SECONDS
                while not cancelled.wait(0.1) and time.monotonic() < deadline:
                    status = dialog.poll()
                    if status is not None:
                        return status == APPROVED
                return False
            finally:
                if dialog.poll() is None:
                    dialog.kill()
    except (OSError, ValueError):
        return False


def windows_approval_button(frame, finish):
    """Win32 delivers input origin during dispatch. An ordinary automated click
    or an accessibility Invoke alone must not authorize the menu."""
    import ctypes as ct
    from ctypes import wintypes as w

    user = ct.WinDLL("user32", use_last_error=True)
    common = ct.WinDLL("comctl32", use_last_error=True)
    pointer = ct.c_size_t
    result = ct.c_ssize_t
    subclass = ct.WINFUNCTYPE(result, w.HWND, w.UINT, w.WPARAM, w.LPARAM, pointer, pointer)

    class Source(ct.Structure):
        _fields_ = [("device", w.INT), ("origin", w.INT)]

    user.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
        w.INT, w.INT, w.INT, w.INT, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]
    user.CreateWindowExW.restype = w.HWND
    user.GetCurrentInputMessageSource.argtypes = [ct.POINTER(Source)]
    user.GetCurrentInputMessageSource.restype = w.BOOL
    user.GetClientRect.argtypes = [w.HWND, ct.POINTER(w.RECT)]
    user.GetClientRect.restype = w.BOOL
    user.GetAncestor.argtypes = [w.HWND, w.UINT]
    user.GetAncestor.restype = w.HWND
    user.GetForegroundWindow.restype = w.HWND
    common.SetWindowSubclass.argtypes = [w.HWND, subclass, pointer, pointer]
    common.SetWindowSubclass.restype = w.BOOL
    common.DefSubclassProc.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
    common.DefSubclassProc.restype = result
    # WS_CHILD | WS_VISIBLE, with a real HWND so input is checked before Tk translates it.
    button = user.CreateWindowExW(0, "BUTTON", "允许执行这一次", 0x50000000, 0, 0,
                                  frame.winfo_reqwidth(), frame.winfo_reqheight(), frame.winfo_id(), None, None, None)
    if not button:
        raise ct.WinError(ct.get_last_error())

    pressed = False
    @subclass
    def on_message(hwnd, msg, wp, lp, subclass_id, data):
        nonlocal pressed
        if msg in (0x0201, 0x0202):  # WM_LBUTTONDOWN / WM_LBUTTONUP
            source = Source()
            physical = (user.GetCurrentInputMessageSource(ct.byref(source)) and source.origin == 1
                        and user.GetForegroundWindow() == user.GetAncestor(hwnd, 2))
            if msg == 0x0201:
                pressed = bool(physical)
            else:
                accepted, pressed = pressed and physical, False
                x, y = ct.c_short(lp & 0xffff).value, ct.c_short((lp >> 16) & 0xffff).value
                rect = w.RECT()
                if accepted and user.GetClientRect(hwnd, ct.byref(rect)) and 0 <= x < rect.right and 0 <= y < rect.bottom:
                    frame.after_idle(finish)
        elif msg in (0x001f, 0x0215):  # WM_CANCELMODE / WM_CAPTURECHANGED
            pressed = False
        return common.DefSubclassProc(hwnd, msg, wp, lp)

    if not common.SetWindowSubclass(button, on_message, 1, 0):
        raise RuntimeError("Cannot validate input on the review window")
    return on_message  # retain the native callback until the window has been destroyed


def show_dialog(project, path):
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.withdraw()
    root.title("Unity 菜单执行审核")
    root.attributes("-topmost", True)
    root.resizable(False, False)
    approved = False

    def approve():
        nonlocal approved
        approved = True
        root.quit()

    try:
        body = ttk.Frame(root, padding=18)
        body.pack()
        for line in ("是否允许在 Unity 中执行一次菜单？", "项目　" + project,
                     "菜单　" + path, "该回调以 Unity 的权限运行，可能读写文件、联网或启动外部程序。"):
            ttk.Label(body, text=line, wraplength=480, justify="left").pack(anchor="w", pady=4)
        buttons = ttk.Frame(body)
        buttons.pack(anchor="e", pady=(12, 0))
        deny = ttk.Button(buttons, text="拒绝", command=root.quit)
        deny.pack(side="left", padx=8)
        if sys.platform == "win32":
            slot = ttk.Frame(buttons, width=140, height=32)
            slot.pack(side="left")
            root.update_idletasks()
            native_callback = windows_approval_button(slot, approve)
        else:
            ttk.Button(buttons, text="允许执行这一次", command=approve).pack(side="left")
        root.protocol("WM_DELETE_WINDOW", root.quit)
        root.bind("<Escape>", lambda event: root.quit())
        root.after(REVIEW_SECONDS * 1000, root.quit)
        root.deiconify()
        deny.focus_set()
        root.mainloop()
        return approved
    finally:
        root.destroy()


if __name__ == "__main__":
    project, path = json.load(sys.stdin.buffer)
    validate_path(path)
    sys.exit(APPROVED if show_dialog(project, path) else 1)
