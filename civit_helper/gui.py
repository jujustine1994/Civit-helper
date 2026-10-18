import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox

from .state import ROOT, RUNTIME, Store, taipei_now

LABELS = {'running': '執行中', 'complete': '今日已完成', 'partial': '部分完成，等待補跑',
          'stalled': '搜尋停滯，等待補跑', 'unconfirmed': '操作結果待確認',
          'login_required': '請先登入', 'verification_required': '需要人工檢查',
          'error': '執行失敗，進度已保留', 'interrupted': '上次中斷，可補跑', 'ready': '已就緒',
          'cancelled': '已取消這次排程', 'setup_required': '請完成登入及擴充功能設定', 'waiting': '等待每日執行時間'}


def launch():
    root = tk.Tk()
    root.title('Civit Helper')
    root.geometry('720x510')
    root.minsize(680, 490)
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
    ttk.Label(frame, text='日常 Chrome 擴充功能 · 每天 04:00 · 排程前 3 分鐘倒數').pack(anchor='w', pady=(6, 18))
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
        detail.configure(text='已啟動。' + ('請在日常 Chrome 正常登入 Civitai。' if command == 'login' else '請確認日常 Chrome 已載入 Civit Helper；結果將自動更新。'))

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
    def extension_folder():
        from .bridge import ensure_extension_config
        ensure_extension_config()
        os.startfile(ROOT / 'extension')

    ttk.Button(frame, text='開啟擴充功能資料夾', command=extension_folder).pack(anchor='w', pady=(10, 0))
    ttk.Label(frame, text='首次使用：Chrome 載入 extension 資料夾 → 檢查網站 → 立即執行。\n手動執行不倒數；排程通知按 X 可取消當次。',
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
            status.configure(text=LABELS.get(run['status'], run['status']) if run else '請先在日常 Chrome 載入擴充功能並登入 Civitai。')
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
