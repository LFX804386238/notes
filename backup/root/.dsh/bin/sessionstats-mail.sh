#!/bin/bash
# DSH 用量日报：发现新报告（session-stats/reports/*.md）就渲染寄邮箱
# 开关：/root/.dsh/mail.json 的 enabled 和 send_usage
# 防重复：寄成功的文件名记录在 /root/.dsh/bin/.sessionstats-sent
set -u
CFG=/root/.dsh/mail.json
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root

STATE=$(python3 - "$CFG" <<'PY'
import json, sys
try:
    c = json.load(open(sys.argv[1], encoding="utf-8"))
    print("ON" if c.get("enabled") and c.get("send_usage") else "OFF")
except Exception:
    print("OFF")
PY
)
if [ "$STATE" != "ON" ]; then
    echo "[mail-switch off] skip"
    exit 0
fi

REPORT_DIR=/root/.dsh/session-stats/reports
SENT=/root/.dsh/bin/.sessionstats-sent
touch "$SENT"

for f in $(ls -t "$REPORT_DIR"/*.md 2>/dev/null); do
    name=$(basename "$f")
    grep -qxF "$name" "$SENT" && continue
    if python3 /root/.dsh/bin/send_mail.py \
        --subject "DSH 用量日报 ${name%.md}" \
        --body-file "$f"; then
        echo "$name" >> "$SENT"
        echo "[sent] $name"
    else
        echo "[send failed] $name（下轮重试）"
    fi
done
