"""Interactive authentication in the installed, unautomated Chrome browser."""
import os
import subprocess
from pathlib import Path

from .state import RUNTIME


def chrome_path():
    for folder in [os.environ.get('PROGRAMFILES'), os.environ.get('PROGRAMFILES(X86)'), os.environ.get('LOCALAPPDATA')]:
        if folder:
            candidate = Path(folder) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe'
            if candidate.is_file():
                return candidate
    raise FileNotFoundError('找不到已安裝的 Chrome。')


def login_command(chrome, profile):
    return [str(chrome), '--user-data-dir=' + str(profile), '--new-window', 'https://civitai.red/images']


def open_native_login(chrome=None, profile=None):
    command = login_command(chrome or chrome_path(), profile or RUNTIME / 'chrome-profile')
    # No driver, debugging connection or injected scripts during authentication.
    # The process lock stays held until the user closes this dedicated Chrome.
    process = subprocess.Popen(command)
    process.wait()
