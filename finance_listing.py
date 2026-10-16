"""finance_listing.py - สั่ง "ดูรายการรายรับ / รายจ่าย ของเดือน" ในโหมดรายรับรายจ่าย

แสดงเป็นหน้า HTML แบบการ์ด (พื้นมืด วันที่ + ป้ายหมวด + ยอดเงิน + ชื่อรายการ + หมายเหตุ) อ่านอย่างเดียว
ไม่มีปุ่ม เพิ่ม/แก้ไข/ลบ; เขียนหน้าใหม่ในไฟล์นี้เอง ไม่เรียกโค้ดของ ChanaFinance
อ่านฐานข้อมูลด้วย SELECT อย่างเดียว ไม่เรียก AI ยอดรวมโค้ดคำนวณเอง

คำสั่ง (โค้ดตรวจจับเอง ต้องมีคำว่า รายรับ หรือ รายจ่าย อย่างใดอย่างหนึ่ง + คำขอดู):
  "ขอดูรายรับเดือนนี้", "รายรับเดือนนี้เป็นอย่างไรบ้าง", "ช่วยบอกรายละเอียดของรายรับหน่อย",
  "เดือนกันยายน รายรับมีอะไรบ้าง", "แสดงรายจ่ายเดือน 9 ปี 2569"
  ไม่บอกเดือน = เดือนปัจจุบัน; ไม่บอกปี = ปีปัจจุบัน
  ประโยคที่มี สรุป/ยอด/รายงาน/รายปี หรือมีคำว่า "บาท" ไม่ใช่คำสั่งนี้ (ให้สรุปยอด/บันทึกรายการจัดการ)
ขึ้นป๊อปอัปยืนยันเดือน/ปีก่อนแสดง; ถ้าเดือนนั้นไม่มีรายการ แจ้งในแชท
ใช้ไฟล์ที่ใช้ล่าสุด (เปลี่ยนด้วยคำสั่ง "เปลี่ยนไฟล์")
callback เป็น bound method + ui.delay(เมธอด, 0.3) ตามบทเรียนกันล่ม
"""
import datetime
import os
import re
import sqlite3

import ui
import config
import finance_db as fdb
import finance_tools as ft
from overlays import ChoiceOverlay
from debug_log import log as debug_log

INCOME = 'income'
EXPENSE = 'expense'

_MONTHS = ['', 'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
           'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']
_ABBR = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
         'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
_INTENT = ('ดู', 'แสดง', 'รายการ', 'รายละเอียด', 'มีอะไร', 'เป็นอย่างไร', 'เป็นยังไง', 'บอก')
_EXCLUDE = ('สรุป', 'ยอด', 'รายงาน', 'รายปี', 'ทั้งปี', 'ประจำปี', 'ทั้งไฟล์')
_PREV_MONTH = ('เดือนที่แล้ว', 'เดือนก่อน', 'เดือนที่ผ่านมา')
_MAX_LEN = 60  # ประโยคยาวมักเป็นเรื่องอื่น

_VIEWS = []  # เก็บหน้าที่เปิดแล้วไว้ไม่ให้ถูกทำลายขณะ native ยังอ้างถึง (บทเรียนกันล่ม)


def _shift_month(year, month, delta):
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


_NUM_WORDS = {'หนึ่ง': 1, 'สอง': 2, 'สาม': 3, 'สี่': 4, 'ห้า': 5, 'หก': 6,
              'เจ็ด': 7, 'แปด': 8, 'เก้า': 9, 'สิบ': 10}
_REL_RE = re.compile(r'(\d{1,2}|หนึ่ง|สอง|สาม|สี่|ห้า|หก|เจ็ด|แปด|เก้า|สิบ)?'
                     r'เดือน(ที่แล้ว|ที่ผ่านมา|ก่อน|หน้า)')
# ใช้ลบคำบอกเดือนสัมพัทธ์ก่อนเช็กตัวเลขที่เหลือ (finance_filter)
REL_DIGIT_RE = re.compile(r'\d{1,2}(?=เดือน(?:ที่แล้ว|ที่ผ่านมา|ก่อน|หน้า))')


def relative_month(v, today):
    """เดือนสัมพัทธ์: เดือนที่แล้ว/เดือนก่อน/เดือนที่ผ่านมา/เดือนหน้า และมีจำนวนนำหน้าได้
    (สองเดือนที่แล้ว, 3เดือนที่แล้ว, สามเดือนหน้า) -> (year, month) หรือ None"""
    m = _REL_RE.search(v)
    if not m:
        return None
    count = m.group(1)
    n = 1 if not count else (int(count) if count.isdigit() else _NUM_WORDS[count])
    if not 1 <= n <= 36:
        return None
    return _shift_month(today.year, today.month, n if m.group(2) == 'หน้า' else -n)


def _parse_month_year(v, today):
    """v = ข้อความที่ตัดช่องว่างและแปลงเลขไทยแล้ว -> (month, year ค.ศ.) ไม่บอกเดือน = เดือนปัจจุบัน"""
    month = year = year_rel = None
    rel = relative_month(v, today)
    if 'เดือนนี้' in v:
        month = today.month
    elif rel is not None:
        year_rel, month = rel
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
        month = today.month
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
    return month, year


def parse_request(text, today=None):
    """คืน None (ไม่ใช่คำสั่งดูรายการ) หรือ {'kind': 'income'|'expense', 'year': y, 'month': m}"""
    today = today or datetime.date.today()
    v = ''.join(str(text or '').translate(ft._DIGITS).split())
    if not v or len(v) > _MAX_LEN or 'บาท' in v:  # มี "บาท" = คำสั่งบันทึกรายการ
        return None
    if any(w in v for w in _EXCLUDE):  # สรุปยอด/รายปี ให้ finance_summary จัดการ
        return None
    has_income = 'รายรับ' in v
    has_expense = 'รายจ่าย' in v
    if has_income == has_expense:  # ไม่มีเลย หรือมีทั้งสอง = ไม่ชัด ไม่จับ
        return None
    if not any(w in v for w in _INTENT):
        return None
    month, year = _parse_month_year(v, today)
    return {'kind': INCOME if has_income else EXPENSE, 'year': year, 'month': month}


def kind_text(kind):
    return 'รายรับ' if kind == INCOME else 'รายจ่าย'


# ---------- อ่านข้อมูล (SELECT อย่างเดียว) ----------
_SQL = {
    INCOME: '''
        SELECT t.date,
               COALESCE(NULLIF(TRIM(t.detail_text), ''),
                        (SELECT detail_name FROM detail_master WHERE id = t.detail_id), ''),
               COALESCE(c.name, ''), t.amount, COALESCE(t.note, '')
        FROM income t LEFT JOIN category_income c ON t.category_id = c.id
        WHERE t.year = ? AND t.month = ?
        ORDER BY t.date DESC, t.id DESC''',
    EXPENSE: '''
        SELECT t.date,
               COALESCE(NULLIF(TRIM(t.detail_text), ''),
                        (SELECT detail_name FROM detail_master WHERE id = t.detail_id), ''),
               COALESCE(c.name, ''), t.amount, COALESCE(t.note, '')
        FROM expense t LEFT JOIN category_expense c ON t.category_id = c.id
        WHERE t.year = ? AND t.month = ?
        ORDER BY t.date DESC, t.id DESC''',
}


def fetch_month(db_path, kind, year, month):
    """คืน list ของ (date, detail, category, amount, note) เรียงใหม่ -> เก่า"""
    conn = sqlite3.connect(db_path, timeout=5)
    try:
        return conn.execute(_SQL[kind], (year, month)).fetchall()
    finally:
        conn.close()


def total_amount(rows):
    total = 0.0
    for r in rows:
        try:
            total += float(r[3])
        except (TypeError, ValueError):
            pass
    return round(total, 2)


# ---------- HTML ----------
_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #1c1c1e; color: #e5e5ea; padding: 12px 12px 28px 12px;
  font-family: -apple-system, "Helvetica Neue", sans-serif; font-size: 15px; }
h2 { text-align: center; font-size: 19px; color: #fff; padding: 8px 0 14px 0; }
.bar { display: flex; justify-content: space-between; align-items: baseline;
  padding: 0 4px 12px 4px; color: #98989f; font-size: 14px; }
.bar .total { font-weight: bold; font-size: 16px; }
.card { background: #2c2c2e; border-radius: 16px; padding: 14px 16px; margin-bottom: 10px; }
.row1 { display: flex; align-items: center; gap: 10px; }
.date { color: #98989f; font-size: 14px; white-space: nowrap; }
.chip { background: #1f3a5f; color: #6aa9ff; border-radius: 8px; padding: 3px 10px;
  font-size: 13px; }
.amt { margin-left: auto; font-weight: bold; font-size: 20px; white-space: nowrap;
  font-variant-numeric: tabular-nums; }
.income { color: #4cd964; }
.expense { color: #ff5a4d; }
.detail { color: #fff; font-size: 17px; padding-top: 8px; word-break: break-word; }
.note { color: #98989f; font-size: 14px; padding-top: 4px; word-break: break-word; }
.empty { text-align: center; color: #636366; padding: 40px 0; }
"""


def _esc(text):
    text = str(text) if text is not None else ''
    return (text.strip().replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def month_title(year, month):
    return '%s %d (พ.ศ. %d)' % (_MONTHS[month], year, year + 543)


def build_html(kind, year, month, rows):
    cls = 'income' if kind == INCOME else 'expense'
    cards = []
    for date, detail, category, amount, note in rows:
        try:
            amt = '{:,.2f}'.format(float(amount))
        except (TypeError, ValueError):
            amt = ''
        chip = '<span class="chip">%s</span>' % _esc(category) if str(category or '').strip() else ''
        note_html = '<div class="note">%s</div>' % _esc(note) if str(note or '').strip() else ''
        cards.append(
            '<div class="card"><div class="row1"><span class="date">%s</span>%s'
            '<span class="amt %s">%s</span></div><div class="detail">%s</div>%s</div>'
            % (_esc(date), chip, cls, amt, _esc(detail), note_html))
    title = '%s %s' % (kind_text(kind), month_title(year, month))
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<style>' + _CSS + '</style></head><body>'
        '<h2>' + _esc(title) + '</h2>'
        '<div class="bar"><span>ทั้งหมด %d รายการ</span>'
        '<span class="total %s">รวม %s บาท</span></div>'
        % (len(rows), cls, '{:,.2f}'.format(total_amount(rows)))
        + (''.join(cards) if cards else '<div class="empty">ไม่มีรายการ</div>')
        + '</body></html>')


class _ResultView(ui.View):
    def __init__(self, title, html):
        super().__init__()
        self.name = title
        self.background_color = '#1c1c1e'
        wv = ui.WebView()
        wv.flex = 'WH'
        wv.scales_page_to_fit = False
        self.add_subview(wv)
        self._wv = wv
        wv.load_html(html)

    def layout(self):
        self._wv.frame = self.bounds


# ---------- ลำดับงาน ----------
class Lister:
    def __init__(self, host, text, req):
        self.host = host
        self.text = text
        self.req = req
        self.folder = None
        self.db = None
        self.done = False

    def show(self):
        host = self.host
        host._listing_runner = self  # เก็บไว้ให้อยู่จนจบ
        host._live = {'time': config.now_text(), 'model': config.get_current_model(),
                      'user': self.text, 'ai': '', 'status': 'live'}
        req = self.req
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
            self.finish('แสดงรายการไม่ได้: %s' % e)
            return
        if self.db is None:
            self.finish('ไม่พบไฟล์ .db ในโฟลเดอร์ ChanaFinance')
            return
        title = 'แสดงรายการ%s\n%s ใช่ไหม?' % (kind_text(req['kind']), month_title(req['year'], req['month']))
        host.show_overlay(ChoiceOverlay(title, [('แสดงรายการ', 'ok')], self.on_pick, self.on_cancel))

    def on_pick(self, value):
        ui.delay(self.do_pick, 0.3)

    def on_cancel(self):
        ui.delay(self.do_cancel, 0.3)

    def do_cancel(self):
        self.finish('ไม่ได้แสดงรายการ')

    def do_pick(self):
        try:
            self._show_list()
        except Exception as e:
            debug_log('finance_listing: error %r' % (e,))
            self.finish('แสดงรายการไม่สำเร็จ: %s' % e)

    def _show_list(self):
        global _VIEWS
        path, name = self.db['path'], self.db['name']
        if not os.path.isfile(path):  # กัน sqlite สร้างไฟล์เปล่าใหม่
            self.finish('ไม่พบไฟล์ %s แล้ว' % name)
            return
        problems = fdb.check_schema(path)
        if problems:
            if any('locked' in p or 'busy' in p for p in problems):
                self.finish('ไฟล์ %s กำลังถูกใช้งานอยู่ (ถูกล็อก) ลองใหม่อีกครั้งสักครู่' % name)
            else:
                self.finish('ไฟล์ %s โครงสร้างไม่ครบ แสดงรายการไม่ได้: %s' % (name, problems[0]))
            return
        req = self.req
        kind, y, m = req['kind'], req['year'], req['month']
        rows = fetch_month(path, kind, y, m)
        label = kind_text(kind)
        if not rows:
            self.finish('ไม่มีรายการ%sเดือน%s %d ในไฟล์ %s' % (label, _MONTHS[m], y, name))
            return
        html = build_html(kind, y, m, rows)
        view = _ResultView('%s %s %d' % (label, _MONTHS[m], y + 543), html)
        _VIEWS = _VIEWS[-2:] + [view]
        view.present('fullscreen', animated=True)
        self.finish('แสดงรายการ%s %s แล้ว: %d รายการ รวม %s บาท (ไฟล์ %s)'
                    % (label, month_title(y, m), len(rows), '{:,.2f}'.format(total_amount(rows)), name))

    def finish(self, message):
        if self.done:
            return
        self.done = True
        host = self.host
        if getattr(host, '_listing_runner', None) is self:
            host._listing_runner = None
        host._finish_turn(message, 'ok', tool=True)  # tool=True: ไม่ให้ AI จำรอบนี้เป็นบทสนทนา
        try:
            host.input.text = ''
        except Exception:
            pass
