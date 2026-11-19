#!/usr/bin/env python3
# 家检：鱼出勤 + 昨晚日记 + 今日榜单日报 + 昨日用量日报。全绿退出码0，异常打印报告并退出码1。
import json, os, sys, re
from datetime import date, datetime, timedelta

TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
issues = []

# 1) 鱼昨晚出勤：醒来的看视频与触发的翘班都会占用 usedCount 里「日期|窗口」的键
#    （whale-night.json 在午夜就预生成新一天的计划，date 字段不能作为出勤依据）
try:
    night = json.load(open('/root/.dsh/whale-night.json', encoding='utf-8'))
    windows = []
    try:
        cfg = json.load(open('/root/.dsh/bili-whale.config.json', encoding='utf-8'))
        windows = [w['start'] + '–' + w['end'] for w in cfg.get('night', {}).get('windows', [])]
    except Exception:
        pass
    if not windows:
        windows = ['18:00–22:00']
    used = night.get('usedCount', {}) or {}
    attended = any((used.get(YESTERDAY + '|' + w) or 0) >= 1 for w in windows)
    # 兜底：还没跨天归档时，昨夜刚触发的翘班/醒来记录在顶层字段里
    if not attended and night.get('date') == YESTERDAY:
        attended = (night.get('action') == 'skip' and night.get('fired')) or bool(night.get('wokeAt'))
    if not attended:
        issues.append('**鱼昨晚没醒**：whale-night.json 里没有 ' + YESTERDAY + ' 的出勤或翘班记录（醒来、正当翘班都不会报警，只有完全没记录才算异常）。')
except Exception as e:
    issues.append('**鱼昨晚没醒**：whale-night.json 读取失败（' + str(e) + '）。')

# 2) 昨晚的日记：翘班夜按约定也照写日记
try:
    txt = open('/root/.dsh/whale-diary.md', encoding='utf-8').read()
    if not re.search(r'^# ' + re.escape(YESTERDAY) + r'\b', txt, re.M):
        issues.append('**昨晚没写日记**：whale-diary.md 里没有 ' + YESTERDAY + ' 的篇章（翘班夜按约定也会写日记说明跳过理由）。')
except Exception as e:
    issues.append('**昨晚没写日记**：whale-diary.md 读取失败（' + str(e) + '）。')

# 3) 今天的榜单日报：8:30 cron 跑完后应存在
trend = '/root/notes/trending/daily/' + TODAY[:7] + '/' + TODAY + '.md'
if not os.path.exists(trend):
    issues.append('**榜单日报缺失**：' + trend + ' 不存在（8:30 的榜单定时任务可能没跑成功，可查 /root/.dsh/github-trending/mail.log）。')

# 4) 昨天的用量日报
usage = '/root/.dsh/session-stats/reports/' + YESTERDAY + '.md'
if not os.path.exists(usage):
    issues.append('**用量日报缺失**：' + usage + ' 不存在（session-stats 定时任务可能没跑，可查 /root/.dsh/session-stats/）。')

if not issues:
    sys.exit(0)

report = '# 家检异常 · ' + TODAY + '\n\n检查时间 ' + datetime.now().strftime('%H:%M') + '，以下 ' + str(len(issues)) + ' 项需要看一眼：\n\n'
for i, x in enumerate(issues, 1):
    report += str(i) + '. ' + x + '\n'
print(report)
sys.exit(1)
