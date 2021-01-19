#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
import os
import poplib
import telnetlib
import time
from email.header import decode_header
from email.parser import Parser
from email.utils import parseaddr
import re
import pytz
import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event

# 全局设定
# 经常去的站点可以设置在这里，如果目的地中包含这些站点，会自动选中
default_station = ["杭州东", "上海虹桥"]
mail_12306 = "12306@rails.com.cn"
# 乘车人姓名
name = 'xxx'
# 输入邮件地址, 口令和POP3服务器地址:
user = 'xxxx@163.com'
# 此处密码是授权码,用于登录第三方邮件客户端
password = 'xxx'
eamil_server = 'pop.163.com'


# 字符编码转换
def decode_str(str_in):
    value, charset = decode_header(str_in)[0]
    if charset:
        value = value.decode(charset)
    return value


def decodeBody(msgPart):
    contentType = msgPart.get_content_type()
    textContent = ""
    if contentType == 'text/plain' or contentType == 'text/html':
        content = msgPart.get_payload(decode=True)
        charset = msgPart.get_charset()
        if charset is None:
            contentType = msgPart.get('Content-Type', '').lower()
            position = contentType.find('charset=')
            if position >= 0:
                charset = contentType[position + 8:].strip()
        if charset:
            textContent = content.decode(charset)
    return textContent


def get_travel(t):
    dcc = []
    m_c = re.compile("\w\d*次").search(t)
    url = "http://search.huochepiao.com/checi/" + str(m_c.group(0)[:-1])
    header = {'User-Agent': 'Mozilla/5.0'}
    req = requests.get(url, headers=header)

    # 处理车次详细信息
    soup = BeautifulSoup(req.content, 'lxml')
    table = soup.find_all("table")[6]
    td_th = re.compile('t[dh]')

    for row in table.findAll("tr"):
        tmp = {}
        cells = row.findAll(td_th)
        if len(cells) == 12 or len(cells) == 13:
            tmp["name"] = cells[2].find(text=True)
            tmp["end"] = cells[3].find(text=True)
            tmp["start"] = cells[4].find(text=True)
            tmp["cost"] = cells[6].find(text=True)
            dcc.append(tmp)

    start_station_index = 0  # 出发站序号
    start_station_name = ""  # 出发站名称

    for i in dcc:
        m = re.compile(i["name"]).search(t)
        if m:
            start_station_name = m.group(0)
            start_station_index = dcc.index(i)
            break

    print(u"出发站：" + start_station_name, u"出发站序号：" + str(start_station_index))
    print(u"请选择目的地：")

    k = 0  # 初始化显示站点序列号

    # 设置常用的目的地
    default_to_station_index = 0
    default_to_station_name = ""

    for i in dcc:
        if k > start_station_index:
            print(str(k) + u"：" + i["name"])
            if i["name"] in default_station:
                default_to_station_index = k
                default_to_station_name = i["name"]
        k += 1

    # 到达站序号
    # 自动设置到达站
    if default_to_station_index > 0:
        to_station_index = input("回车确认到达 " + default_to_station_name + "站: ")
        if not to_station_index:
            to_station_index = default_to_station_index
            return start_station_index, to_station_index, dcc
        else:
            return start_station_index, int(to_station_index), dcc

    to_station_index = int(input('请选择目的地，输入序号：'))
    while to_station_index > len(dcc) - 1 or to_station_index <= start_station_index:
        to_station_index = int(input("目的地选择有误，请重新选择： "))

    return start_station_index, to_station_index, dcc


def con_t(cost):
    r_hour = re.compile("\d*小时").search(cost)
    r_min = re.compile("\d*分").search(cost)

    total_min = 0

    if r_hour:
        total_min += int(r_hour.group(0)[:-2]) * 60

    if r_min:
        total_min += int(r_min.group(0)[:-1])

    return total_min


def get_costs(s, e, dcc):
    s_total = con_t(dcc[s]["cost"])
    e_total = con_t(dcc[e]["cost"])

    hour = (e_total - s_total) // 60
    mains = (e_total - s_total) % 60

    return hour, mains


def get_info(t):
    s, e, dcc = get_travel(t)
    start_station_name = dcc[s]["name"]
    to_station_name = dcc[e]["name"]
    cost_hour, cost_mins = get_costs(s, e, dcc)
    cc = re.compile("\w\d*次").search(t).group(0)[:-1]
    zc = re.compile("\d*车\d*\w").search(t).group(0)
    day = re.compile("\d*日").search(t).group(0)[:-1]
    month = re.compile("\d*月").search(t).group(0)[:-1]
    year = re.compile("\d*年").search(t).group(0)[:-1]
    start_time = dcc[s]["start"]
    end_time = dcc[e]["end"]
    # check_in = re.compile(ur"检票口：\d*").search(t).group(0)[3:]
    return start_station_name, to_station_name, cost_hour, cost_mins, cc, zc, day, month, year, start_time, end_time


def make_ics(t):
    start_station_name, to_station_name, cost_hour, cost_mins, cc, zc, day, month, year, start_time, end_time = get_info(
        t)

    cal = Calendar()
    event = Event()
    event.add('dtstart',
              datetime(int(year), int(month), int(day), int(start_time.split(":")[0]), int(start_time.split(":")[1]), 0,
                       tzinfo=pytz.timezone("Asia/Shanghai")))
    event.add('dtend',
              datetime(int(year), int(month), int(day), int(end_time.split(":")[0]), int(end_time.split(":")[1]), 0,
                       tzinfo=pytz.timezone("Asia/Shanghai")))
    event.add('summary', start_station_name + u'-' + to_station_name + str(cost_hour) + u"小时" + str(cost_mins) + u"分")
    event.add('LOCATION', start_station_name + u"站")
    event.add('DESCRIPTION', t)
    cal.add_component(event)
    f = open(os.path.join('/tmp', 'cal.ics'), 'wb')
    f.write(cal.to_ical())
    f.close()


def get_mgs_content(server, id):
    resp, lines, octets = server.retr(id)
    msg_content = b'\r\n'.join(lines).decode('utf-8')

    # 解析邮件:
    msg = Parser().parsestr(msg_content)
    From = parseaddr(msg.get('from'))[1]
    To = parseaddr(msg.get('To'))[1]
    Subject = decode_str(msg.get('Subject'))

    # 获取邮件正文内容
    msgBodyContents = []
    if msg.is_multipart():
        messageParts = msg.get_payload()
        for messagePart in messageParts:
            bodyContent = decodeBody(messagePart)
            if bodyContent:
                msgBodyContents.append(bodyContent)
    else:
        bodyContent = decodeBody(msg)
        if bodyContent:
            msgBodyContents.append(bodyContent)
    return {"From": From, "To": To, "Subject": Subject, "content": msgBodyContents}


def run_ing(user, password, pop3_server):
    # 连接到POP3服务器,有些邮箱服务器需要ssl加密，可以使用poplib.POP3_SSL
    try:
        telnetlib.Telnet(pop3_server, 995)
        server = poplib.POP3_SSL(pop3_server, 995, timeout=10)
    except:
        time.sleep(5)
        server = poplib.POP3(pop3_server, 110, timeout=10)
    # 身份认证:
    server.user(user)
    server.pass_(password)

    # list()返回所有邮件的编号:
    resp, mails, octets = server.list()
    # 可以查看返回的列表类似[b'1 82923', b'2 2184', ...]
    # print(mails)

    index = len(mails)
    mail_list = []
    for i in range(index, 0, -1):
        msg_dic = get_mgs_content(server, i)
        From = msg_dic.get('From')
        msgBodyContents = msg_dic.get('content')
        if From == mail_12306:
            for o in msgBodyContents[0].split('\r\n'):
                if name in o:
                    mail_list.append(o)

    for j in mail_list:
        # 打印车次列表
        print("ID:", mail_list.index(j) + 1, j.split('.')[1:][0])

    s = input('请选择要生成日历事件的订单ID，回车选择第1个订单: ')
    if not s:
        t_id = 1
    else:
        t_id = int(s)

    make_ics(mail_list[t_id - 1])
    os.system('open /tmp/cal.ics')


if __name__ == '__main__':
    run_ing(user, password, eamil_server)
