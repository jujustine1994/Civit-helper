import math
import time
import tkinter as tk
from tkinter import ttk


def requires_warning(command, source):
    return command == 'run' and source == 'scheduled'


class Countdown:
    def __init__(self, seconds=180, now=time.monotonic):
        self.now = now
        self.deadline = now() + seconds
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def remaining(self):
        return max(0, math.ceil(self.deadline - self.now()))

    def decision(self):
        if self.cancelled:
            return 'cancelled'
        return 'execute' if self.remaining() == 0 else 'waiting'


def confirm_scheduled_run():
    """Closing this notice cancels this invocation; timeout allows execution."""
    countdown = Countdown()
    window = tk.Tk()
    window.title('Civit Helper · 排程執行提醒')
    window.geometry('550x260')
    window.resizable(False, False)
    window.attributes('-topmost', True)
    frame = ttk.Frame(window, padding=24)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='即將執行 Civitai 每日任務',
              font=('Microsoft JhengHei UI', 16, 'bold')).pack(anchor='w')
    label = ttk.Label(frame, font=('Microsoft JhengHei UI', 25, 'bold'))
    label.pack(anchor='w', pady=(10, 8))
    ttk.Label(frame, text='每日目標：50 個愛心、追蹤 3 位新作者。\n若你仍在使用電腦，請按關閉取消這次執行。\n沒有操作，倒數結束後會自動開始。',
              font=('Microsoft JhengHei UI', 10)).pack(anchor='w')

    def cancel():
        countdown.cancel()
        window.destroy()

    ttk.Button(frame, text='關閉／取消這次', command=cancel).pack(anchor='e', pady=(12, 0))
    window.protocol('WM_DELETE_WINDOW', cancel)

    def tick():
        remaining = countdown.remaining()
        label.configure(text=f'{remaining // 60:02d}:{remaining % 60:02d}')
        if countdown.decision() == 'execute':
            window.destroy()
        else:
            window.after(200, tick)

    tick()
    window.mainloop()
    return countdown.decision() == 'execute'
