"""Explicitly authorized Windows mouse input, restricted to one Blender window.

No service, hooks, elevation, registry changes or generic process control.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as W
import math
import os
from pathlib import Path
import time


def gesture_points(source, via, target):
    points = [source, via, target]
    if any(len(p) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float))
                             or not math.isfinite(v) or v < 0 for v in p) for p in points):
        raise ValueError('Expected three finite nonnegative coordinate pairs')
    if math.dist(source, via) < 8:
        raise ValueError('An actual source-internal movement of at least 8 pixels is required')
    result = [tuple(source), tuple(via)]
    result.extend(tuple(via[j] + (target[j]-via[j])*i/12 for j in (0, 1))
                  for i in range(1, 13))
    return result


class BlenderMouse:
    def __init__(self, pid: int, executable: Path):
        if os.name != 'nt':
            raise RuntimeError('Windows desktop input requires Windows')
        expected = executable.resolve(strict=True)
        if expected.name.casefold() != 'blender.exe':
            raise ValueError('Only an explicitly selected Blender executable is accepted')
        self.pid = pid
        self.u = ctypes.WinDLL('user32', use_last_error=True)
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        k.OpenProcess.argtypes, k.OpenProcess.restype = [W.DWORD, W.BOOL, W.DWORD], W.HANDLE
        k.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)]
        k.CloseHandle.argtypes = [W.HANDLE]
        handle = k.OpenProcess(0x1000, False, pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            text, length = ctypes.create_unicode_buffer(32768), W.DWORD(32768)
            if not k.QueryFullProcessImageNameW(handle, 0, text, ctypes.byref(length)):
                raise ctypes.WinError(ctypes.get_last_error())
            if Path(text.value).resolve() != expected:
                raise ValueError('PID does not belong to the approved Blender executable')
        finally:
            k.CloseHandle(handle)
        u = self.u
        u.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
        u.IsWindowVisible.argtypes, u.IsWindowVisible.restype = [W.HWND], W.BOOL
        u.GetWindow.argtypes, u.GetWindow.restype = [W.HWND, W.UINT], W.HWND
        u.GetForegroundWindow.restype = W.HWND
        u.SetForegroundWindow.argtypes, u.SetForegroundWindow.restype = [W.HWND], W.BOOL
        u.WindowFromPoint.argtypes, u.WindowFromPoint.restype = [W.POINT], W.HWND
        u.GetWindowRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
        u.GetClientRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
        u.ScreenToClient.argtypes = [W.HWND, ctypes.POINTER(W.POINT)]
        u.GetAsyncKeyState.argtypes, u.GetAsyncKeyState.restype = [ctypes.c_int], ctypes.c_short
        self.callback_type = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
        u.EnumWindows.argtypes = [self.callback_type, W.LPARAM]
        windows = []
        @self.callback_type
        def collect(hwnd, _):
            if self.window_pid(hwnd) == pid and u.IsWindowVisible(hwnd) and not u.GetWindow(hwnd, 4):
                windows.append(hwnd)
            return True
        if not u.EnumWindows(collect, 0) or len(windows) != 1:
            raise RuntimeError('Expected exactly one visible unowned Blender window')
        self.hwnd = windows[0]
        self.old_dpi = None
        u.SetThreadDpiAwarenessContext.argtypes = [W.HANDLE]
        u.SetThreadDpiAwarenessContext.restype = W.HANDLE
        self.old_dpi = u.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        self.dwm = ctypes.WinDLL('dwmapi')
        self.dwm.DwmGetWindowAttribute.argtypes = [W.HWND, W.DWORD, W.LPVOID, W.DWORD]
        try:
            self.initial_geometry = self.geometry()
            self.rect = W.RECT(*self.initial_geometry[:4])
        except Exception:
            self.close()
            raise
        class MouseInput(ctypes.Structure):
            _fields_ = [('dx',W.LONG),('dy',W.LONG),('mouseData',W.DWORD),
                        ('dwFlags',W.DWORD),('time',W.DWORD),('dwExtraInfo',W.WPARAM)]
        class InputUnion(ctypes.Union):
            _fields_ = [('mi',MouseInput)]
        class Input(ctypes.Structure):
            _anonymous_ = ('data',)
            _fields_ = [('type',W.DWORD),('data',InputUnion)]
        self.Input = Input
        u.SendInput.argtypes, u.SendInput.restype = [W.UINT, ctypes.POINTER(Input), ctypes.c_int], W.UINT

    def close(self):
        if getattr(self, 'old_dpi', None):
            self.u.SetThreadDpiAwarenessContext(self.old_dpi)
            self.old_dpi = None

    def window_pid(self, hwnd):
        pid = W.DWORD()
        self.u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def geometry(self):
        bounds, client, origin = W.RECT(), W.RECT(), W.POINT(0, 0)
        if self.dwm.DwmGetWindowAttribute(self.hwnd, 9, ctypes.byref(bounds), ctypes.sizeof(bounds)):
            if not self.u.GetWindowRect(self.hwnd, ctypes.byref(bounds)):
                raise ctypes.WinError(ctypes.get_last_error())
        if not self.u.GetClientRect(self.hwnd, ctypes.byref(client)) or not self.u.ScreenToClient(self.hwnd, ctypes.byref(origin)):
            raise ctypes.WinError(ctypes.get_last_error())
        return (bounds.left, bounds.top, bounds.right, bounds.bottom,
                client.left, client.top, client.right, client.bottom, origin.x, origin.y)

    def screen_point(self, point, screenshot_size):
        width, height = screenshot_size
        if width <= 0 or height <= 0 or not (0 <= point[0] < width and 0 <= point[1] < height):
            raise ValueError('Point is outside the observed screenshot')
        return (self.rect.left + round(point[0]*(self.rect.right-self.rect.left)/width),
                self.rect.top + round(point[1]*(self.rect.bottom-self.rect.top)/height))

    def guard(self, point):
        if self.geometry() != self.initial_geometry:
            raise RuntimeError('Blender window moved or resized; stopped input')
        if self.u.GetForegroundWindow() != self.hwnd:
            raise RuntimeError('Blender lost foreground focus; stopped input')
        if self.window_pid(self.u.WindowFromPoint(W.POINT(*point))) != self.pid:
            raise RuntimeError('Pointer path is covered by another process; no input allowed there')
        if self.u.GetAsyncKeyState(0x1B) & 0x8000:
            raise RuntimeError('Escape pressed; stopped input')

    def blender_point(self, screen_point):
        point, rect = W.POINT(*screen_point), W.RECT()
        if not self.u.ScreenToClient(self.hwnd, ctypes.byref(point)) or not self.u.GetClientRect(self.hwnd, ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        return (point.x, rect.bottom-point.y-1)

    def send(self, flags, point=None):
        item = self.Input()
        item.type = 0
        item.mi.dwFlags = flags
        if point is not None:
            x0,y0 = self.u.GetSystemMetrics(76),self.u.GetSystemMetrics(77)
            width,height = self.u.GetSystemMetrics(78),self.u.GetSystemMetrics(79)
            item.mi.dx = round((point[0]-x0)*65535/(width-1))
            item.mi.dy = round((point[1]-y0)*65535/(height-1))
        if self.u.SendInput(1, ctypes.byref(item), ctypes.sizeof(item)) != 1:
            raise RuntimeError('Windows refused mouse input; no elevation attempted')

    def drag(self, source, via, target, screenshot_size, *, execute=False):
        logical = gesture_points(source, via, target)
        points = [self.screen_point(p, screenshot_size) for p in logical]
        if not self.u.SetForegroundWindow(self.hwnd):
            if self.u.GetForegroundWindow() != self.hwnd:
                raise RuntimeError('Cannot activate the selected Blender window')
        time.sleep(.15)
        for point in points:
            self.guard(point)
        result = {'pid':self.pid,'window':int(self.hwnd),'mode':'normal-Windows-mouse',
                  'dry_run':not execute,'source':points[0],'via':points[1],'target':points[-1]}
        if not execute:
            return result
        if self.u.GetAsyncKeyState(1) & 0x8000:
            raise RuntimeError('Mouse button is already held; refused to interfere')
        events = []
        held = False
        try:
            self.send(0x0001|0x8000|0x4000|0x2000, points[0])
            time.sleep(.2)
            self.guard(points[0])
            self.send(0x0002)
            held = True
            events.append('LEFT_DOWN')
            time.sleep(.15)
            for i, point in enumerate(points[1:]):
                self.guard(point)
                self.send(0x0001|0x8000|0x4000|0x2000, point)
                events.append('MOVE_SOURCE_HELD' if i == 0 else 'MOVE_HELD')
                time.sleep(.18 if i == 0 else .025)
            self.guard(points[-1])
        finally:
            if held:
                self.send(0x0004)
                events.append('LEFT_UP')
        result['events'] = events
        return result
