#!/bin/bash
# 家检：每天10:00跑一次，全绿静默不发，有异常才寄一封说明邮件
# 开关：/root/.dsh/mail.json 的 enabled 总闸 + send_homecheck 分项（缺省视为开）
set -u
CFG=/root/.dsh/mail.json
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root
LOG=/root/.dsh/homecheck.log

STATE=$(python3 - "$CFG" <<'PY'
import json, sys
try:
    c = json.load(open(sys.argv[1], encoding="utf-8"))
    print("ON" if c.get("enabled") and c.get("send_homecheck", True) else "OFF")
except Exception:
    print("OFF")
PY
)
if [ "$STATE" != "ON" ]; then
    echo "[homecheck] switch off, skip"
    exit 0
fi

python3 /root/.dsh/bin/homecheck.py > /tmp/homecheck-report.md 2>&1
RC=$?
if [ "$RC" -eq 0 ]; then
    echo "[$(date '+%F %T')] all green, silent" >> "$LOG"
    exit 0
fi
echo "[$(date '+%F %T')] issues found, sending mail" >> "$LOG"
python3 /root/.dsh/bin/send_mail.py --subject "家检异常 $(date +%Y-%m-%d)" --body-file /tmp/homecheck-report.md
