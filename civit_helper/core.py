import logging
import random
import time

from .state import TARGETS, TAIPEI, taipei_now


def automatic_allowed(now):
    if now.tzinfo is not None:
        now = now.astimezone(TAIPEI)
    return now.hour >= 4


def execute(store, site, *, now=taipei_now, seconds=1200):
    day = now().date().isoformat()
    deadline = time.monotonic() + seconds
    account = str(site.account())
    store.bind(account)

    def result(status, message):
        return {'status': status, 'message': message, 'progress': store.progress(day)}

    def expired():
        return now().date().isoformat() != day or time.monotonic() >= deadline

    for original_day, kind, target in store.pending():
        if expired():
            return result('partial', '已達時間上限或跨日，保留進度等待補跑。')
        state = site.state(kind, target)
        if state is True:
            store.confirm(original_day, kind, target)
        elif state is False:
            store.discard_pending(kind, target)
        else:
            return result('unconfirmed', '有操作結果無法確認，已停止，避免重複點擊。')

    if all(store.progress(day)[k] >= n for k, n in TARGETS.items()):
        return result('complete', '當日任務已完成。')

    checked = {'heart': set(), 'follow': set()}
    for batch in site.candidates():
        random.shuffle(batch)
        for candidate in batch:
            for kind, key in [('heart', 'image'), ('follow', 'author')]:
                if expired():
                    return result('partial', '已達時間上限或跨日，保留進度等待補跑。')
                target = str(candidate.get(key) or '')
                if (not target or store.progress(day)[kind] >= TARGETS[kind]
                        or target in checked[kind] or store.seen(kind, target)
                        or (kind == 'follow' and target == account)):
                    continue
                checked[kind].add(target)
                before = site.state(kind, target)
                if before is True:
                    continue
                if before is not False:
                    return result('unconfirmed', '無法辨識操作前狀態，已停止。')
                if expired():
                    return result('partial', '已達時間上限或跨日，保留進度等待補跑。')
                store.prepare(day, kind, target)
                site.apply(kind, target)
                after = site.state(kind, target)
                if after is not True:
                    return result('unconfirmed', '網站尚未確認成功，保留操作供下次核對。')
                store.confirm(day, kind, target)
                logging.info('progress %s', store.progress(day))
            if all(store.progress(day)[k] >= n for k, n in TARGETS.items()):
                return result('complete', '愛心 50/50、追蹤 3/3，當日任務已完成。')
    return result('stalled', '搜尋流程停滯或來源已用盡，任務未完成，稍後將重試。')
