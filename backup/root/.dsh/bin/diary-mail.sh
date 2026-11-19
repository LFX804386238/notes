#!/bin/bash
# 每天早8点寄昨晚的鱼日记；开关 mail.json 的 enabled + send_diary
set -u
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root
python3 /root/.dsh/bin/diary-mail.py >> /root/.dsh/diary-mail.log 2>&1
