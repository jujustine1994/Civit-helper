"""Human-readable run history (runtime/執行紀錄.txt); civit.log stays the technical log for AI/debugging."""
from datetime import datetime

from .state import RUNTIME

HISTORY_FILE = RUNTIME / '執行紀錄.txt'
SOURCES = {'scheduled': '排程', 'manual': '手動'}
RESULTS = {'complete': '✅ 完成', 'partial': '⚠️ 部分完成', 'stalled': '⚠️ 部分完成', 'unconfirmed': '⚠️ 待確認',
           'cancelled': '⏹ 已取消', 'waiting': '⏹ 未到時間', 'interrupted': '⚠️ 中斷', 'running': '▶ 執行中',
           'login_required': '❌ 需要登入', 'verification_required': '❌ 需要人工驗證', 'error': '❌ 失敗'}


def duration(started, ended):
    if not ended:
        return '—'
    seconds = int((datetime.fromisoformat(ended) - datetime.fromisoformat(started)).total_seconds())
    return f'{seconds // 60}分{seconds % 60:02d}秒' if seconds >= 60 else f'{seconds}秒'


def row_fields(run):
    total = run['day_total']
    return {
        'time': run['started'][:16].replace('T', ' '),
        'source': SOURCES.get(run['source'], run['source']),
        'result': RESULTS.get(run['status'], run['status']),
        'heart': f"+{run['added']['heart']}",
        'follow': f"+{run['added']['follow']}",
        # Plain counts: a later extra round raises the goal, which would make old rows read 50/100.
        'day': f"{total['heart']}、{total['follow']}",
        'duration': duration(run['started'], run['ended']),
        # Success needs no explanation; failures keep the reason the tool recorded.
        'note': '' if run['status'] == 'complete' else run['message'],
    }


def format_history(runs):
    lines = ['Civit Helper 執行紀錄（最新在上）',
             '時間 | 方式 | 結果 | 這次愛心 | 這次追蹤 | 當日累計（愛心、追蹤） | 耗時 | 說明', '']
    for run in runs:
        f = row_fields(run)
        lines.append(' | '.join([f['time'], f['source'], f['result'], f['heart'], f['follow'],
                                 f['day'], f['duration'], f['note']]).rstrip(' |'))
    if not runs:
        lines.append('尚無執行紀錄。')
    return '\n'.join(lines) + '\n'


def write_history(store):
    try:
        RUNTIME.mkdir(exist_ok=True)
        HISTORY_FILE.write_text(format_history(store.history()), encoding='utf-8-sig')
    except OSError:
        pass  # The human summary must never break a run.
