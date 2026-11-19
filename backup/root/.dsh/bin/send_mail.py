#!/usr/bin/env python3
# 通用发信模块：读 /root/.dsh/mail.json，enabled=false 时静默退出
# 用法：echo 正文 | python3 send_mail.py --subject "标题"
#      python3 send_mail.py --subject "标题" --body-file /path/to/file.md
# 2026-11-18 升级：正文按 Markdown 渲染成网页格式（邮箱里直接是排版好的样子），
#   同时带一份纯文本备胎；渲染失败时退回纯文本。
import sys, json, argparse, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

CFG_PATH = "/root/.dsh/mail.json"

# 简洁样式：手机邮箱里也舒服
STYLE = """
<style>
  body { font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
         color: #2c3e50; line-height: 1.7; max-width: 720px; margin: 24px auto; padding: 0 16px; }
  h1, h2, h3 { color: #1a5276; }
  h2 { border-bottom: 2px solid #d6eaf8; padding-bottom: 6px; }
  code { background: #f4f6f7; padding: 1px 5px; border-radius: 3px; }
  blockquote { border-left: 4px solid #aed6f1; margin-left: 0; padding-left: 12px; color: #566573; }
  a { color: #2980b9; }
  table { border-collapse: collapse; }
  td, th { border: 1px solid #d5dbdb; padding: 4px 10px; }
</style>
"""


def load_cfg():
    with open(CFG_PATH, encoding="utf-8") as f:
        return json.load(f)


def render_html(body_md):
    """Markdown -> HTML；失败返回 None"""
    try:
        import markdown
        return STYLE + markdown.markdown(body_md, extensions=["tables", "fenced_code"])
    except Exception:
        return None


def send(cfg, subject, body):
    smtp = cfg["smtp"]
    to = cfg.get("to") or smtp["user"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = smtp["user"]
    msg["To"] = to
    msg.attach(MIMEText(body, "plain", "utf-8"))
    html = render_html(body)
    if html:
        msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL(smtp["host"], int(smtp["port"]), timeout=30) as s:
        s.login(smtp["user"], smtp["pass"])
        s.sendmail(smtp["user"], [to], msg.as_string())
    mode = "html" if html else "plain"
    print(f"mail sent ({mode}) -> {to} ({subject})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", default="通知")
    ap.add_argument("--body-file", default=None)
    args = ap.parse_args()

    cfg = load_cfg()
    if not cfg.get("enabled", False):
        print("mail disabled, skip")
        return

    if args.body_file:
        with open(args.body_file, encoding="utf-8") as f:
            body = f.read()
    else:
        body = sys.stdin.read()
    if not body.strip():
        print("empty body, skip")
        return
    send(cfg, args.subject, body)


if __name__ == "__main__":
    main()
