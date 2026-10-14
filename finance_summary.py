"""finance_summary.py - สั่ง "สรุปยอดรายเดือน / รายปี" ในโหมดรายรับรายจ่าย

ใช้หน้ารายงาน HTML ของ ChanaFinance ตัวเดิม (monthly_summary.py / yearly_summary.py) โดยโหลดจากโฟลเดอร์
ChanaFinance ด้วยพาธตรง ๆ ไม่แก้ไฟล์เดิม ไม่ลอกโค้ด -> หน้าตากับตัวเลขตรงกับแอปเดิมทุกจุด
อ่านฐานข้อมูลอย่างเดียว ไม่เรียก AI

คำสั่ง (โค้ดตรวจจับเอง):
  รายเดือน: "สรุปรายจ่ายเดือนนี้", "สรุปเดือนกันยายน", "สรุปเดือน 9 ปี 2025", "ยอดเดือนที่แล้ว", "สรุป 9/2569"
            ไม่บอกปี = ปีปัจจุบัน; ไม่บอกเดือน (พิมพ์แค่ "สรุปรายเดือน") = เดือนปัจจุบัน
  รายปี:   "สรุปรายปี", "สรุปทั้งปี" -> ข้อมูลทั้งไฟล์ (ไม่สนว่าปีไหน เหมือน ChanaFinance)
ขึ้นป๊อปอัปยืนยันก่อนแสดง; ถ้าเดือนนั้นไม่มีข้อมูลในไฟล์ แจ้งว่าไม่มีข้อมูล
ใช้ไฟล์ที่ใช้ล่าสุด (เปลี่ยนด้วยคำสั่ง "เปลี่ยนไฟล์")
callback เป็น bound method + ui.delay(เมธอด, 0.3) ตามบทเรียนกันล่ม
"""
import datetime
import importlib.util
import inspect
import os
import re
import sqlite3

import ui
import config
import finance_db as fdb
import finance_tools as ft
from overlays import ChoiceOverlay
from debug_log import log as debug_log

_MONTHS = ['', 'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
           'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']
_ABBR = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
         'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
_TRIGGERS = ('สรุป', 'ยอด', 'รายงาน')
_YEAR_WORDS = ('รายปี', 'ทั้งปี', 'ประจำปี', 'ทั้งไฟล์')
_PREV_MONTH = ('เดือนที่แล้ว', 'เดือนก่อน', 'เดือนที่ผ่านมา')
_MAX_LEN = 60  # ประโยคยาวมักเป็นเรื่องอื่น


def _shift_month(year, month, delta):
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def parse_request(text, today=None):
    """คืน None (ไม่ใช่คำสั่งสรุป) หรือ {'kind': 'year'} / {'kind': 'month', 'year': y, 'month': m}"""
    today = today or datetime.date.today()
    v = ''.join(str(text or '').translate(ft._DIGITS).split())
    if not v or len(v) > _MAX_LEN or 'บาท' in v:  # มี "บาท" = คำสั่งบันทึกรายการ ไม่ใช่ขอดูสรุป
        return None
    if not any(w in v for w in _TRIGGERS):
        return None
    if any(w in v for w in _YEAR_WORDS):
        return {'kind': 'year'}

    month = year = year_rel = None
    if 'เดือนนี้' in v:
        month = today.month
    elif any(w in v for w in _PREV_MONTH):
        year_rel, month = _shift_month(today.year, today.month, -1)
    if month is None:
        m = re.search(r'(?<!\d)(\d{1,2})/(\d{4})(?!\d)', v)  # 9/2569
        if m:
            month, year = int(m.group(1)), int(m.group(2))
    if month is None:
        best = None
        for i in range(1, 13):
            for name in (_MONTHS[i], _ABBR[i]):
                pos = v.find(name)
                if pos >= 0 and (best is None or pos < best[0]):
                    best = (pos, i)
        if best:
            month = best[1]
    if month is None:
        m = re.search(r'เดือน(?:ที่)?(\d{1,2})(?!\d)', v)  # เดือน 9
        if m:
            month = int(m.group(1))
    if month is None:
        if 'เดือน' not in v:
            return None
        month = today.month  # พิมพ์แค่ "สรุปรายเดือน" -> เดือนปัจจุบัน (มีป๊อปอัปให้ตรวจก่อนแสดง)

    if year is None:
        m = re.search(r'(?<![\d/])(1[89]\d\d|2\d{3})(?![\d/])', v)
        if m:
            year = int(m.group(1))
        elif 'ปีที่แล้ว' in v or 'ปีก่อน' in v:
            year = today.year - 1
        elif year_rel is not None:
            year = year_rel  # "เดือนที่แล้ว" ตอนเดือนมกราคม = ธันวาคมปีก่อน
        else:
            year = today.year
    if year >= 2400:
        year -= 543  # พ.ศ. -> ค.ศ.
    return {'kind': 'month', 'year': year, 'month': month}


# ---------- โหลดรายงานของ ChanaFinance ----------
_MODS = {}


def _load(folder, name):
    mod = _MODS.get(name)
    if mod is not None:
        return mod
    path = os.path.join(folder, name + '.py')
    if not os.path.isfile(path):
        raise RuntimeError('ไม่พบ %s.py ในโฟลเดอร์ ChanaFinance' % name)
    spec = importlib.util.spec_from_file_location('chana_' + name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _MODS[name] = mod
    return mod


class Summarizer:
    def __init__(self, host, text, req):
        self.host = host
        self.text = text
        self.req = req
        self.folder = None
        self.db = None
        self.done = False

    def show(self):
        host = self.host
        host._summary_runner = self  # เก็บไว้ให้อยู่จนจบ
        host._live = {'time': config.now_text(), 'model': config.get_current_model(),
                      'user': self.text, 'ai': '', 'status': 'live'}
        req = self.req
        if req['kind'] == 'month':
            if not 1 <= req['month'] <= 12:
                self.finish('เดือน %s ไม่ถูกต้อง (ต้อง 1-12)' % req['month'])
                return
            if not 2000 <= req['year'] <= 2100:
                self.finish('ปี %s ไม่ถูกต้อง' % req['year'])
                return
        try:
            self.folder = fdb.find_finance_folder()
            self.db = fdb.guess_default_db(self.folder)
        except fdb.FinanceDBError as e:
            self.finish('แสดงสรุปไม่ได้: %s' % e)
            return
        if self.db is None:
            self.finish('ไม่พบไฟล์ .db ในโฟลเดอร์ ChanaFinance')
            return
        if req['kind'] == 'month':
            title = 'แสดงสรุปรายเดือน\n%s %d (พ.ศ. %d) ใช่ไหม?' % (
                _MONTHS[req['month']], req['year'], req['year'] + 543)
        else:
            title = 'แสดงสรุปรายปี\n(ข้อมูลทั้งไฟล์) ใช่ไหม?'
        host.show_overlay(ChoiceOverlay(title, [('แสดงสรุป', 'ok')], self.on_pick, self.on_cancel))

    def on_pick(self, value):
        ui.delay(self.do_pick, 0.3)

    def on_cancel(self):
        ui.delay(self.do_cancel, 0.3)

    def do_cancel(self):
        self.finish('ไม่ได้แสดงสรุป')

    def do_pick(self):
        try:
            self._show_report()
        except Exception as e:
            debug_log('finance_summary: error %r' % (e,))
            self.finish('แสดงสรุปไม่สำเร็จ: %s' % e)

    def _show_report(self):
        path, name = self.db['path'], self.db['name']
        if not os.path.isfile(path):  # กัน sqlite สร้างไฟล์เปล่าใหม่
            self.finish('ไม่พบไฟล์ %s แล้ว' % name)
            return
        req = self.req
        if req['kind'] == 'month':
            y, m = req['year'], req['month']
            mod = _load(self.folder, 'monthly_summary')
            income_rows = mod._fetch_income_summary(path, y, m)
            expense_rows = mod._fetch_expense_summary(path, y, m)
            if not income_rows and not expense_rows:
                self.finish('ไม่มีข้อมูลเดือน%s %d ในไฟล์ %s' % (_MONTHS[m], y, name))
                return
            html = mod._build_html(y, m, income_rows, expense_rows)
            view = mod._ResultView('สรุป %s %d' % (mod.THAI_MONTHS[m], y + 543), html)
            message = 'แสดงสรุปรายเดือน %s %d แล้ว (ไฟล์ %s)' % (_MONTHS[m], y, name)
        else:
            mod = _load(self.folder, 'yearly_summary')
            # ChanaFinance has had two yearly-summary APIs:
            # the current all-file version takes only db_path, while an older
            # version takes db_path and year. Support both without editing it.
            fetch_params = inspect.signature(mod._fetch_data).parameters
            if len(fetch_params) >= 2:
                year = self._latest_data_year(path)
                if year is None:
                    self.finish('ยังไม่มีข้อมูลในไฟล์ %s' % name)
                    return
                data = mod._fetch_data(path, year)
                html = mod._build_html(data, year)
                message = 'แสดงสรุปรายปี %d (ปีล่าสุดในไฟล์ %s) แล้ว' % (year, name)
            else:
                data = mod._fetch_data(path)
                html = mod._build_html(data)
                message = 'แสดงสรุปรายปี (ข้อมูลทั้งไฟล์) แล้ว (ไฟล์ %s)' % name
            if not data:
                self.finish('ยังไม่มีข้อมูลในไฟล์ %s' % name)
                return
            view = mod._ResultView(html)
        view.present('fullscreen', animated=True)
        self.finish(message)

    def _latest_data_year(self, path):
        """เลือกรอบปีล่าสุดสำหรับ yearly_summary รุ่นที่รับ year แยกต่างหาก."""
        conn = sqlite3.connect(path)
        try:
            years = []
            for table in ('income', 'expense'):
                row = conn.execute('SELECT MAX(year) FROM ' + table).fetchone()
                if row and row[0] is not None:
                    years.append(int(row[0]))
            return max(years) if years else None
        finally:
            conn.close()

    def finish(self, message):
        if self.done:
            return
        self.done = True
        host = self.host
        if getattr(host, '_summary_runner', None) is self:
            host._summary_runner = None
        host._finish_turn(message, 'ok', tool=True)  # tool=True: ไม่ให้ AI จำรอบนี้เป็นบทสนทนา
        try:
            host.input.text = ''
        except Exception:
            pass
