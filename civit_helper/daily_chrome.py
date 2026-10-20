"""Start the daily Chrome minimized when it is closed, so the extension can connect.

Normal launch only: no debugging port, no automation flags, user's own profile.
--no-startup-window was tested and exits within seconds (nothing keeps Chrome alive),
so a minimized startup window is used and closed again after the run.
"""
import ctypes
import json
import logging
import os
import subprocess
import time
from ctypes import wintypes
from pathlib import Path

from .login import chrome_path

EXTENSION_ID = 'jlnbjhdpocefkcpgiegdhmanhpekgmki'
SW_SHOWMINNOACTIVE = 7
WM_CLOSE = 0x0010
CREATE_NO_WINDOW = 0x08000000


def extension_profile(user_data=None):
    """Profile folder that has the extension; avoids the multi-profile picker on startup."""
    user_data = Path(user_data or Path(os.environ['LOCALAPPDATA']) / 'Google' / 'Chrome' / 'User Data')
    try:
        state = json.loads((user_data / 'Local State').read_text(encoding='utf-8'))
        profiles = list(state['profile']['info_cache'])
        last_used = state['profile'].get('last_used')
    except (OSError, ValueError, KeyError):
        return None
    if last_used in profiles:
        profiles.remove(last_used)
        profiles.insert(0, last_used)
    for name in profiles:
        for prefs in ('Secure Preferences', 'Preferences'):
            try:
                if EXTENSION_ID in (user_data / name / prefs).read_text(encoding='utf-8', errors='ignore'):
                    return name
            except OSError:
                continue
    return None


def launch_command(chrome, profile):
    return [str(chrome)] + (['--profile-directory=' + profile] if profile else [])


def chrome_running():
    try:
        output = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe', '/FO', 'CSV', '/NH'],
                                capture_output=True, text=True, creationflags=CREATE_NO_WINDOW, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return True  # Unknown: never risk a second Chrome window.
    return '"chrome.exe"' in output.lower()


def minimize_windows(hwnds):
    """Minimize without activating; already minimized or vanished windows are skipped."""
    user32 = ctypes.windll.user32
    for hwnd in hwnds:
        if user32.IsWindow(hwnd) and not user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_SHOWMINNOACTIVE)


def chrome_windows():
    """Visible top-level windows that belong to chrome.exe processes."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def collect(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if handle:
            try:
                buffer = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(len(buffer))
                if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)) \
                        and buffer.value.lower().endswith('\\chrome.exe'):
                    found.append(hwnd)
            finally:
                kernel32.CloseHandle(handle)
        return True

    user32.EnumWindows(collect, 0)
    return found


class DailyChrome:
    """Context manager: launch minimized only if Chrome is closed; afterwards close only that window."""

    def __init__(self, wait=8):
        self.wait = wait
        self.startup_windows = []

    def __enter__(self):
        if chrome_running():
            return self
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = SW_SHOWMINNOACTIVE
        profile = extension_profile()
        subprocess.Popen(launch_command(chrome_path(), profile), startupinfo=info)
        # Chrome may restore a saved maximized placement or session windows, ignoring the
        # STARTUPINFO hint; minimize every window it opens during startup ourselves.
        deadline = time.time() + self.wait
        while time.time() < deadline:
            time.sleep(0.5)
            for hwnd in chrome_windows():
                if hwnd not in self.startup_windows:
                    self.startup_windows.append(hwnd)
            minimize_windows(self.startup_windows)
        logging.info('daily Chrome was closed; started minimized profile=%s windows=%s',
                     profile, len(self.startup_windows))
        return self

    def __exit__(self, *args):
        user32 = ctypes.windll.user32
        closed = 0
        for hwnd in self.startup_windows:
            # A restored window means someone is using it now; leave it alone.
            if user32.IsWindow(hwnd) and user32.IsIconic(hwnd):
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                closed += 1
        if self.startup_windows:
            logging.info('closed tool-started Chrome windows=%s', closed)
        return False
