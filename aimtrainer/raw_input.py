"""Windows Raw Input (WM_INPUT) ueber ctypes.

Warum: Raw Input liefert die unveraenderten Sensor-Counts der Maus, BEVOR Windows
"Zeigerbeschleunigung verbessern" (Enhance Pointer Precision) oder die
Windows-Zeigergeschwindigkeit anwendet. Genau so liest Valorant die Maus.

Ein eigener Thread erzeugt ein unsichtbares Message-Only-Fenster, registriert sich
mit RIDEV_INPUTSINK fuer die Maus (UsagePage 0x01, Usage 0x02) und schreibt jedes
Event mit Zeitstempel (perf_counter) in eine Queue. Die Spiel-Schleife arbeitet die
Events in der Originalreihenfolge ab -> Klicks werden mit exakt der Blickrichtung
ausgewertet, die zum Zeitpunkt des Klicks bestand (nicht erst am Frame-Ende).
"""
import ctypes
import sys
import threading
import time
from collections import deque
from ctypes import wintypes

LEFT_DOWN, LEFT_UP = 0x0001, 0x0002


class RawEvent:
    __slots__ = ("t", "dx", "dy", "left_down", "left_up")

    def __init__(self, t, dx, dy, left_down=False, left_up=False):
        self.t, self.dx, self.dy, self.left_down, self.left_up = t, dx, dy, left_down, left_up


class RawMouse:
    """Plattformneutrale Schnittstelle. Auf Nicht-Windows bleibt `available` False."""

    def __init__(self):
        self.available = False
        self._queue = deque()
        self._lock = threading.Lock()
        self._thread = None
        self._thread_id = None
        self._ready = threading.Event()

    def start(self) -> bool:
        if sys.platform != "win32":
            return False
        self._thread = threading.Thread(target=self._run, name="RawInput", daemon=True)
        self._thread.start()
        self._ready.wait(2.0)
        return self.available

    def stop(self):
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)  # WM_QUIT

    def drain(self):
        with self._lock:
            events = list(self._queue)
            self._queue.clear()
        return events

    # ------------------------------------------------------------------
    def _run(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                        ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                        ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]

        class RAWINPUTDEVICE(ctypes.Structure):
            _fields_ = [("usUsagePage", wintypes.USHORT), ("usUsage", wintypes.USHORT),
                        ("dwFlags", wintypes.DWORD), ("hwndTarget", wintypes.HWND)]

        class RAWINPUTHEADER(ctypes.Structure):
            _fields_ = [("dwType", wintypes.DWORD), ("dwSize", wintypes.DWORD),
                        ("hDevice", wintypes.HANDLE), ("wParam", wintypes.WPARAM)]

        class _BTN(ctypes.Structure):
            _fields_ = [("usButtonFlags", wintypes.USHORT), ("usButtonData", wintypes.USHORT)]

        class _BTNU(ctypes.Union):
            _fields_ = [("ulButtons", wintypes.ULONG), ("s", _BTN)]

        class RAWMOUSE(ctypes.Structure):
            _fields_ = [("usFlags", wintypes.USHORT), ("u", _BTNU), ("ulRawButtons", wintypes.ULONG),
                        ("lLastX", wintypes.LONG), ("lLastY", wintypes.LONG),
                        ("ulExtraInformation", wintypes.ULONG)]

        class RAWINPUT(ctypes.Structure):
            _fields_ = [("header", RAWINPUTHEADER), ("mouse", RAWMOUSE)]

        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = LRESULT
        user32.GetRawInputData.argtypes = [wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p,
                                           ctypes.POINTER(wintypes.UINT), wintypes.UINT]
        user32.GetRawInputData.restype = wintypes.UINT
        user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                           ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                           wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
        user32.CreateWindowExW.restype = wintypes.HWND

        WM_INPUT, RID_INPUT, RIM_TYPEMOUSE = 0x00FF, 0x10000003, 0
        MOUSE_MOVE_ABSOLUTE, RIDEV_INPUTSINK = 0x01, 0x00000100
        HWND_MESSAGE = wintypes.HWND(-3)
        header_size = ctypes.sizeof(RAWINPUTHEADER)
        buf = ctypes.create_string_buffer(256)

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_INPUT:
                size = wintypes.UINT(ctypes.sizeof(buf))
                if user32.GetRawInputData(lparam, RID_INPUT, buf, ctypes.byref(size), header_size) != 0xFFFFFFFF:
                    ri = RAWINPUT.from_buffer(buf)
                    if ri.header.dwType == RIM_TYPEMOUSE:
                        m = ri.mouse
                        flags = m.u.s.usButtonFlags
                        # Absolute Koordinaten (Tablet/RDP) sind keine Sensor-Counts -> ignorieren
                        dx, dy = (0, 0) if m.usFlags & MOUSE_MOVE_ABSOLUTE else (m.lLastX, m.lLastY)
                        if dx or dy or flags & (LEFT_DOWN | LEFT_UP):
                            ev = RawEvent(time.perf_counter(), dx, dy,
                                          bool(flags & LEFT_DOWN), bool(flags & LEFT_UP))
                            with self._lock:
                                self._queue.append(ev)
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc = WNDPROC(wndproc)  # Referenz halten, sonst GC-Crash
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW(lpfnWndProc=self._wndproc, hInstance=hinst, lpszClassName="AimTrainerRawInput")
        user32.RegisterClassW(ctypes.byref(wc))
        hwnd = user32.CreateWindowExW(0, wc.lpszClassName, "", 0, 0, 0, 0, 0, HWND_MESSAGE, None, hinst, None)
        rid = RAWINPUTDEVICE(0x01, 0x02, RIDEV_INPUTSINK, hwnd)
        ok = hwnd and user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid))
        self.available = bool(ok)
        self._thread_id = kernel32.GetCurrentThreadId()
        self._ready.set()
        if not ok:
            return

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        user32.DestroyWindow(hwnd)
