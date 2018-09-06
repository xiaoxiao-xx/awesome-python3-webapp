#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import smtplib
import time
from email import encoders
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr,formataddr

def _format_addr(s):
    name, addr = parseaddr(s)
    return formataddr((Header(name, 'utf-8').encode(), addr))

from_addr ='320662842@qq.com'
password = 'aifltvtwvbpebidh'
# to_addr = '17781822889@163.com'
smtp_server='smtp.qq.com'
t = str(time.time())

def send_user_email(to_addr,name,passwd):
    msg = MIMEText('<html><body><h1>Hello,欢迎注册小小日志用户</h1>' +
        '<p>点击完成邮箱验证<a href="http://127.0.0.1:9000/api/user_yes?name='+name+'&em='+to_addr+'&mm='+passwd+'&t='+t+'">是我，是我</a></p>' +
        '<p>该邮件30分钟验证有效</p></body></html>', 'html', 'utf-8')
    msg['From'] = _format_addr('小小 <%s>' % from_addr)
    msg['To'] = _format_addr('亲爱的会员<%s>' % to_addr)
    msg['Subject'] = Header('来自小小日志的注册验证。。。', 'utf-8').encode()
    server = smtplib.SMTP_SSL(smtp_server, 465)
    # server.set_debuglevel(1)
    server.login(from_addr,password)
    server.sendmail(from_addr, [to_addr], msg.as_string())
    server.quit()


print(int(float(t)))