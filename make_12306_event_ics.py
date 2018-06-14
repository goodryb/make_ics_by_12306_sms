#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import re
from datetime import datetime
import pytz
import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
import sqlite3

# 全局设定
# 经常去的站点可以设置在这里，如果目的地中包含这些站点，会自动选中
default_station = [u"杭州东", u"上海虹桥", u"杭州"]


def get_travel(t):
    dcc = []
    print t
    m_c = re.compile(ur"\w\d*次").search(t)  # 查找车次信息

    # print str(m_c.group(0)[:-1])

    # 获取车次网页信息
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
    # print dcc
    for i in dcc:
        m = re.compile(i["name"]).search(t)
        if m:
            start_station_name = m.group(0)
            start_station_index = dcc.index(i)

    print u"出发站：" + start_station_name, u"出发站序号：" + str(start_station_index)
    print u"请选择目的地："

    k = 0  # 初始化显示站点序列号

    # 设置常用的目的地
    default_to_station_index = 0
    default_to_station_name = ""

    for i in dcc:
        if k > start_station_index:
            print str(k) + u"：" + i["name"]
            if i["name"] in default_station:
                default_to_station_index = k
                default_to_station_name = i["name"]
        k += 1

    # 到达站序号
    # 自动设置到达站
    if default_to_station_index > 0:
        print u"回车确认到达 " + default_to_station_name + u"站"
        to_station_index = raw_input()
        if not to_station_index:
            to_station_index = default_to_station_index
            return start_station_index, to_station_index, dcc

    to_station_index = int(raw_input())
    while to_station_index > len(dcc) - 1 or to_station_index <= start_station_index:
        print u"目的地选择有误，请重新选择"
        to_station_index = int(raw_input())

    return start_station_index, to_station_index, dcc


def con_t(cost):
    r_hour = re.compile(ur"\d*小时").search(cost)
    r_min = re.compile(ur"\d*分").search(cost)

    total_min = 0

    if r_hour:
        total_min += int(r_hour.group(0)[:-2]) * 60

    if r_min:
        total_min += int(r_min.group(0)[:-1])

    return total_min


def get_costs(s, e, dcc):
    s_total = con_t(dcc[s]["cost"])
    e_total = con_t(dcc[e]["cost"])

    hour = (e_total - s_total) / 60
    mains = (e_total - s_total) % 60

    return hour, mains


def get_info(t):
    s, e, dcc = get_travel(t)
    start_station_name = dcc[s]["name"]
    to_station_name = dcc[e]["name"]
    cost_hour, cost_mins = get_costs(s, e, dcc)
    cc = re.compile(ur"\w\d*次").search(t).group(0)[:-1]
    zc = re.compile(ur"\d*车\d*\w号").search(t).group(0)
    day = re.compile(ur"\d*日").search(t).group(0)[:-1]
    month = re.compile(ur"\d*月").search(t).group(0)[:-1]
    start_time = dcc[s]["start"]
    end_time = dcc[e]["end"]
    # check_in = re.compile(ur"检票口：\d*").search(t).group(0)[3:]
    # print check_in
    return start_station_name, to_station_name, cost_hour, cost_mins, cc, zc, day, month, start_time, end_time


def make_ics(t):
    start_station_name, to_station_name, cost_hour, cost_mins, cc, zc, day, month, start_time, end_time = get_info(
        t)

    year = datetime.now().year

    cal = Calendar()
    event = Event()
    event.add('dtstart',
              datetime(int(year), int(month), int(day), int(start_time.split(":")[0]), int(start_time.split(":")[1]), 0,
                       tzinfo=pytz.timezone("Asia/Shanghai")))
    event.add('dtend',
              datetime(int(year), int(month), int(day), int(end_time.split(":")[0]), int(end_time.split(":")[1]), 0,
                       tzinfo=pytz.timezone("Asia/Shanghai")))
    event.add('summary', start_station_name + u'-' + to_station_name + str(cost_hour) + u"小时" + str(cost_mins) + u"分")
    event.add('LOCATION', cc + u" " + zc)
    event.add('DESCRIPTION', t)
    cal.add_component(event)
    f = open(os.path.join('/tmp', 'cal.ics'), 'wb')
    f.write(cal.to_ical())
    f.close()


def _new_connection():
    # The current logged-in user's Messages sqlite database is found at:
    # ~/Library/Messages/chat.db
    import getpass
    user = getpass.getuser()
    db_path = '/Users/' + user + '/Library/Messages/chat.db'
    return sqlite3.connect(db_path)


def get_messages_for_recipient(id):
    connection = _new_connection()
    c = connection.cursor()

    # The `message` table stores all exchanged iMessages.
    c.execute("SELECT * FROM message WHERE handle_id=" + str(id) + " order by date desc limit 1")
    for row in c:
        text = row[2]
    connection.close()
    return text


def get_12306_ROWID():
    # 12306 headle ROWID
    ROWID = 0
    connection = _new_connection()
    c = connection.cursor()
    c.execute("SELECT * FROM handle WHERE id=12306")
    for row in c:
        ROWID = row[0]
    connection.close()
    return ROWID


if __name__ == "__main__":
    # t = u"订单E11053xxxx,XXX您已购4月24日G7609次x车xF号南京南13:57开,检票口B11。【铁路客服】"
    if len(sys.argv) == 2:
        t = unicode(sys.argv[1], "utf-8")
    if len(sys.argv) == 1:
        ROWID = get_12306_ROWID()
        t = get_messages_for_recipient(ROWID)
    if len(sys.argv) > 2:
        print u"参数有误！"
        sys.exit(1)
    print u"订单信息：" + t
    make_ics(t)
    os.system('open /tmp/cal.ics')
