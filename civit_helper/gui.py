import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox

from .state import ROOT, RUNTIME, Store, taipei_now

LABELS = {'running': '執行中', 'complete': '今日已完成', 'partial': '部分完成，等待補跑',
          'stalled': '搜尋停滯，等待補跑', 'unconfirmed': '操作結果待確認',
          'login_required': '請先登入', 'verification_required': '需要人工檢查',
          'error': '執行失敗，進度已保留', 'interrupted': '上次中斷，可補跑', 'ready': '已就緒'}


def launch():
    root = tk.Tk()
    root.title('Civit Helper')
    root.geometry('680x440')
    root.minsize(640, 420)
    root.configure(bg='#f4f6fa')
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('TFrame', background='#f4f6fa')
    style.configure('TLabel', background='#f4f6fa', font=('Microsoft JhengHei UI', 10))
    style.configure('Title.TLabel', font=('Microsoft JhengHei UI', 21, 'bold'))
    style.configure('Progress.TLabel', font=('Microsoft JhengHei UI', 16, 'bold'))
    style.configure('TButton', font=('Microsoft JhengHei UI', 10), padding=(12, 8))
    frame = ttk.Frame(root, padding=26)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Civit Helper', style='Title.TLabel').pack(anchor='w')
    ttk.Label(frame, text='每天台灣時間 04:00 背景執行 · 未完成每 30 分鐘補跑').pack(anchor='w', pady=(6, 18))
    progress = ttk.Label(frame, style='Progress.TLabel')
    progress.pack(anchor='w')
    date_label = ttk.Label(frame)
    date_label.pack(anchor='w', pady=(6, 14))
    status = ttk.Label(frame, wraplength=610)
    status.pack(anchor='w')
    detail = ttk.Label(frame, wraplength=610)
    detail.pack(anchor='w', pady=(6, 16))
    buttons = ttk.Frame(frame)
    buttons.pack(anchor='w')
    state = {'child': None, 'log': None}
    controls = []

    def start(command):
        if state['child'] and state['child'].poll() is None:
            messagebox.showinfo('執行中', '請等目前工作結束；登入視窗需要由你親自完成登入。')
            return
        RUNTIME.mkdir(exist_ok=True)
        stream = open(RUNTIME / 'launcher.log', 'ab')
        state['log'] = stream
        state['child'] = subprocess.Popen(
            [sys.executable, str(ROOT / 'app.py'), command], cwd=ROOT,
            stdout=stream, stderr=stream, creationflags=subprocess.CREATE_NO_WINDOW)
        detail.configure(text='已啟動。' + ('請在專用 Chrome 登入；成功後關閉這個專用視窗，工具才會檢查登入。' if command == 'login' else '結果將自動更新。'))

    for label, command in [('立即執行', 'run'), ('登入／重新登入', 'login'), ('檢查網站', 'inspect')]:
        button = ttk.Button(buttons, text=label, command=lambda cmd=command: start(cmd))
        button.pack(side='left', padx=(0, 8))
        controls.append(button)

    def view_logs():
        window = tk.Toplevel(root)
        window.title('Civit Helper · 執行紀錄')
        window.geometry('960x560')
        text = tk.Text(window, wrap='word', font=('Consolas', 10))
        text.pack(fill='both', expand=True)
        path = RUNTIME / 'logs' / 'civit.log'
        content = path.read_text(encoding='utf-8', errors='replace')[-60000:] if path.exists() else '尚無執行紀錄。'
        text.insert('1.0', content)
        text.configure(state='disabled')
        text.see('end')

    ttk.Button(frame, text='查看 log 紀錄', command=view_logs).pack(anchor='w', pady=(12, 0))
    ttk.Label(frame, text='首次使用：登入 → 檢查網站 → 立即執行。\n關閉此工具視窗不會取消已啟動的工作或每日排程。',
              foreground='#566274').pack(anchor='w', pady=(16, 0))

    def refresh():
        try:
            store = Store()
            try:
                data = store.status()
            finally:
                store.close()
            counts = data['progress']
            progress.configure(text=f'❤️ 愛心 {counts["heart"]} / 50     ·     追蹤 {counts["follow"]} / 3')
            date_label.configure(text=f'台灣日期：{data["day"]}   ·   待確認操作：{data["pending"]}')
            run = data['last_run']
            status.configure(text=LABELS.get(run['status'], run['status']) if run else '尚未設定登入，請先登入工具專用 Chrome。')
            if run:
                detail.configure(text=run['message'])
            child = state['child']
            busy = child is not None and child.poll() is None
            for button in controls:
                button.configure(state='disabled' if busy else 'normal')
            if child is not None and not busy:
                if child.returncode == 5:
                    detail.configure(text='另一個工作或登入正在執行，請稍後再試。')
                elif child.returncode not in (0, 2):
                    detail.configure(text='啟動失敗，請檢查 runtime/launcher.log。')
                state['child'] = None
                if state['log']:
                    state['log'].close()
                    state['log'] = None
        except Exception:
            status.configure(text='暫時無法讀取紀錄，稍後會自動更新。')
        root.after(2000, refresh)

    refresh()
    root.mainloop()
