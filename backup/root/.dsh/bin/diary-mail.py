#!/usr/bin/env python3
# 每日日记邮件：提取昨晚（昨天日期）的两本日记篇章，早8点寄出；发过不再重复。
import sys, os, re
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from send_mail import load_cfg, send

YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
SENT = '/root/.dsh/.diary-mail-sent'
FILES = [
    ('公开日记', '/root/.dsh/whale-diary.md'),
    ('私人日记', '/root/.dsh/whale-diary-private.md'),
]

def chapter(path):
    try:
        txt = open(path, encoding='utf-8').read()
    except OSError:
        return ''
    m = re.search(r'^# ' + re.escape(YESTERDAY) + r'.*?$', txt, re.M)
    if not m:
        return ''
    nxt = re.search(r'^# ', txt[m.end():], re.M)
    end = m.end() + nxt.start() if nxt else len(txt)
    return txt[m.start():end].strip()

def main():
    cfg = load_cfg()
    if not cfg.get('enabled', False) or not cfg.get('send_diary', True):
        return
    try:
        with open(SENT, encoding='utf-8') as f:
            if YESTERDAY in f.read().split():
                return
    except OSError:
        pass
    parts = []
    for label, path in FILES:
        c = chapter(path)
        if c:
            parts.append('== ' + label + ' ==\n' + c)
    if not parts:
        return
    send(cfg, '鱼的日记 · ' + YESTERDAY, '\n\n'.join(parts))
    with open(SENT, 'a', encoding='utf-8') as f:
        f.write(YESTERDAY + '\n')

if __name__ == '__main__':
    main()
