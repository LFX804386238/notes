#!/bin/bash
# 大肥鱼（DSH）每日定时重启：清内存、按原参数原地拉起
# 挂在宝塔计划任务：每天 01:00
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
LOG=/root/.dsh/dsh-restart.log
ts(){ date '+%F %T'; }

PID=$(pgrep -f 'dsh.*lib/bin\.js web' | head -1)
if [ -n "$PID" ]; then
  RSS=$(awk '/VmRSS/{print int($1/1024)"MB"}' /proc/$PID/status 2>/dev/null)
  CMD=$(tr '\0' ' ' < /proc/$PID/cmdline | sed 's/ $//')
  echo "[$(ts)] restarting dsh pid=$PID rss=$RSS" >> $LOG
  kill "$PID" 2>/dev/null
  for i in $(seq 1 20); do kill -0 "$PID" 2>/dev/null || break; sleep 1; done
  kill -9 "$PID" 2>/dev/null
  sleep 2
else
  CMD="node /root/dsh-app/node_modules/.bin/../.pnpm/@deepseek-ai+dsh@0.2.2-rc.3_225f26e8eb1acf5d3127b5ea568d630c/node_modules/@deepseek-ai/dsh/lib/bin.js web --no-open --host 172.31.9.83 --public-url http://114.116.224.172:3080 --trusted-host 114.116.224.172:3080"
  echo "[$(ts)] dsh not running, start fresh" >> $LOG
fi

cd /root/dsh-app || exit 1
export DSH_PERMISSION_MODE=danger-full-access
nohup $CMD >> /root/.dsh/dsh-web-restart.log 2>&1 &
sleep 8
NEW=$(pgrep -f 'dsh.*lib/bin\.js web' | head -1)
if [ -n "$NEW" ]; then
  echo "[$(ts)] dsh restarted ok pid=$NEW" >> $LOG
else
  echo "[$(ts)] DSH RESTART FAILED" >> $LOG
fi
