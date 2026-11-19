#!/bin/bash
# 鱼窝每日备份：日记 + 脚本与数据 → GitHub 归档仓库
# 1) /root/.dsh/whale-diary.md（公开日记） → notes/diary/whale-diary.md
# 2) 台账脚本/数据 + 大肥鱼公开配置 → notes/backup/site-<weekday>.tar.gz（7 天轮换）
# 不含任何凭据文件：mail.json / .env / credentials.json / dsh-computer.key 永不入包
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
NOTES=/root/notes
LOG=/root/.dsh/backup.log
ts(){ date '+%F %T'; }
set -a; source /root/.dsh/.env 2>/dev/null; set +a

mkdir -p $NOTES/diary $NOTES/backup

# --- 1) 日记归档 ---
cp -f /root/.dsh/whale-diary.md $NOTES/diary/whale-diary.md 2>/dev/null

# --- 2) 站点与配置打包（7 天轮换，周日~周六） ---
DOW=$(date +%u)  # 1=周一 ... 7=周日
WD=$(echo 周一 周二 周三 周四 周五 周六 周日 | cut -d' ' -f$DOW)
TARF=$NOTES/backup/site-$WD.tar.gz
tar czf $TARF \
  --exclude='*.log' --exclude='*.pyc' \
  /root/asset-ledger/scan.py /root/asset-ledger/notes.json /root/asset-ledger/state.json \
  /root/asset-ledger/history.json /root/asset-ledger/ds-balance.jsonl /root/asset-ledger/site-born 2>/dev/null
tar czf $TARF.2 \
  --exclude='*.log' --exclude='*.pyc' --exclude='__pycache__' \
  /root/.dsh/bili-whale.config.json /root/.dsh/whale-listen.json /root/.dsh/bin /root/.dsh/whale-roles 2>/dev/null
cd $NOTES/backup && tar xzf $TARF.2 2>/dev/null && rm -f $TARF.2

# --- 3) 有变化才提交推送 ---
cd $NOTES
git add -A >/dev/null 2>&1
if git diff --cached --quiet 2>/dev/null; then
  echo "[$(ts)] no changes, skip push" >> $LOG
  exit 0
fi
git commit -qm "chore(backup): diary & site config $(date +%F-%H%M)" >> $LOG 2>&1
if git push -q "https://x-access-token:${GITHUB_TOKEN}@github.com/LFX804386238/notes.git" HEAD:main 2>>$LOG; then
  echo "[$(ts)] backup pushed ok" >> $LOG
else
  echo "[$(ts)] BACKUP PUSH FAILED" >> $LOG
fi
