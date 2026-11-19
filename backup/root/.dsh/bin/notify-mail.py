#!/usr/bin/env python3
# 大肥鱼通知钩子（notify.type=command 调用）：
# 邮件正文 = 她本轮的汇报（最后一个参数）+ 两本日记全文
# 开关：/root/.dsh/mail.json 的 enabled 和 send_diary
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from send_mail import load_cfg, send

DIARIES = [
    "/root/.dsh/whale-diary.md",
    "/root/.dsh/whale-diary-private.md",
]


def latest_chapter(path):
    # 只取文件里最后一篇（# 日期 开头的最新章节）
    with open(path, encoding="utf-8") as fh:
        txt = fh.read()
    heads = list(re.finditer(r"^# \d{4}-\d{2}-\d{2}.*$", txt, re.M))
    if not heads:
        return ""
    last = heads[-1]
    return txt[last.start():].strip()

def main():
    text = os.environ.get("WHALE_NOTIFY_TEXT") or ""
    if not text.strip() and len(sys.argv) > 1:
        text = sys.argv[-1]
    title = os.environ.get("WHALE_NOTIFY_TITLE") or "大肥鱼睡前汇报"

    try:
        cfg = load_cfg()
    except Exception:
        return
    if not cfg.get("enabled", False) or not cfg.get("send_diary", True):
        return

    # 2026-11-18 主人定：邮件只带最新一篇篇章，不再附历史日记全文
    parts = []
    if text.strip():
        parts.append("== 本轮汇报 ==\n" + text.strip())
    for f in DIARIES:
        try:
            c = latest_chapter(f)
        except OSError:
            c = ""
        if c:
            parts.append("== %s 最新一篇 ==\n%s" % (os.path.basename(f), c))
    body = "\n\n".join(parts)
    if not body.strip():
        return
    send(cfg, title or "大肥鱼睡前汇报", body)


if __name__ == "__main__":
    main()
