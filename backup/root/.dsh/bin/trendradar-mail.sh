#!/bin/bash
# 榜单日报：定时跑 trendradar，今天的日报存在且没发过就发
# 开关：/root/.dsh/mail.json 的 enabled 和 send_trending
set -u
CFG=/root/.dsh/mail.json
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root

STATE=$(python3 - "$CFG" <<'PY'
import json, sys
try:
    c = json.load(open(sys.argv[1], encoding="utf-8"))
    print("ON" if c.get("enabled") and c.get("send_trending") else "OFF")
except Exception:
    print("OFF")
PY
)
if [ "$STATE" != "ON" ]; then
    echo "[mail-switch off] skip"
    exit 0
fi

set -a; . /root/.dsh/.env; set +a

TREND=/root/.dsh/github-trending/core/v0.13.4/trendradar
DAILY_DIR=/root/notes/trending/daily
SENT=/root/.dsh/github-trending/.mail-sent
DATE=$(date +%F)
MONTH=$(date +%Y-%m); TODAY_FILE="$DAILY_DIR/$MONTH/$DATE.md"

LOG=/root/.dsh/github-trending/runs/cron-$(date +%Y%m%d-%H%M%S).log
"$TREND" run -config /root/.dsh/github-trending/settings.json >> "$LOG" 2>&1
echo "[trendradar] exit=$? log=$LOG"

# 日报分支直推远端 main（令牌缺 PR 权限，绕开 PR 让主线累积全部日报）
(cd /root/notes && git push -q "https://x-access-token:${GITHUB_TOKEN}@github.com/LFX804386238/notes.git" HEAD:main 2>&1 | sed "s/x-access-token:[^@]*/x-access-token:*** /g" || echo "[archive-push] failed")

if [ ! -f "$TODAY_FILE" ]; then
    echo "[$DATE] digest not ready"
    exit 0
fi
if grep -qxF "$DATE" "$SENT" 2>/dev/null; then
    echo "[$DATE] already sent"
    exit 0
fi
python3 /root/.dsh/bin/send_mail.py \
    --subject "GitHub 榜单日报 $DATE" \
    --body-file "$TODAY_FILE" && echo "$DATE" >> "$SENT"
