"""finance_filter.py - สั่ง "ดูรายการเฉพาะหมวด" ของเดือน ในโหมดรายรับรายจ่าย (อ่านอย่างเดียว ไม่เรียก AI)

ตัวอย่าง:
  "เดือนนี้ได้รับปันผลมาเท่าไหร่แล้ว ลองแสดงรายละเอียดให้ดูด้วย"
  "เดือนนี้(จ่ายเงิน) เสียเงินค่าอาหารไปเท่าไหร่ ช่วยแจกแจงที"
กติกา:
  - กรองเฉพาะ "หมวด" (ไม่ค้นจากชื่อรายการ); เทียบคำในประโยคกับชื่อหมวดจริงในไฟล์ ไม่สร้างหมวดเอง
  - พูดถึง "ปันผล" -> รวม 3 หมวดแสดงทีเดียว: เงินปันผลจากหุ้น, เงินปันผลจากกองทุน, เงินคืนทุนจากหุ้น
    (ถ้าพูดเจาะจง "ปันผลจากหุ้น"/"ปันผลจากกองทุน" ใช้เฉพาะหมวดนั้น; พูดแค่ "เงินคืนทุน/เงินคืน" ใช้หมวดคืนทุน)
  - ไม่บอกเดือน = เดือนปัจจุบัน; ไม่บอกปี = ปีปัจจุบัน; ขึ้นป๊อปอัปยืนยันเดือน/ปีก่อนแสดง
  - ยอดรวมโค้ดบวกเอง; หน้าตาเหมือน finance_listing (การ์ด อ่านอย่างเดียว ไม่มีปุ่ม)
try_start(host, text) คืน True เมื่อรับคำสั่งนี้ (ไม่ตรง/มีปัญหาอ่านไฟล์ = False ให้ขั้นตอนอื่นทำต่อ)
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
import finance_listing as fl
from overlays import ChoiceOverlay
from debug_log import log as debug_log

INCOME = fl.INCOME
EXPENSE = fl.EXPENSE
_MAX_LEN = 80
_INTENT = ('เท่าไหร่', 'เท่าไร', 'รายละเอียด', 'แจกแจง', 'แสดง', 'ดู', 'มีอะไร', 'บ้าง', 'ทั้งหมด')
_YEAR_WORDS = ('รายปี', 'ทั้งปี', 'ประจำปี', 'ทั้งไฟล์')
_DIVIDEND_GROUP = ('เงินปันผลจากหุ้น', 'เงินปันผลจากกองทุน', 'เงินคืนทุนจากหุ้น')
_DIVIDEND_LABEL = 'เงินปันผล + เงินคืนทุน'
_LISTS_KEY = {INCOME: 'category_income', EXPENSE: 'category_expense'}


def _norm(s):
    return ''.join(str(s or '').split())


def _clean(text):
    return ''.join(str(text or '').translate(ft._DIGITS).split())


def looks_like_filter_request(text):
    """ตรวจเบื้องต้นแบบไม่แตะไฟล์: เป็นคำถาม/ขอดู ไม่ใช่คำสั่งบันทึกรายการ"""
    v = _clean(text)
    if not v or len(v) > _MAX_LEN:
        return False
    if any(w in v for w in _YEAR_WORDS):
        return False
    if not any(w in v for w in _INTENT):
        return False
    rest = fl.REL_DIGIT_RE.sub('', v)  # 2เดือนที่แล้ว
    rest = re.sub(r'(?<!\d)\d{1,2}/\d{4}(?!\d)', '', rest)  # 9/2569
    rest = re.sub(r'เดือน(?:ที่)?\d{1,2}(?!\d)', '', rest)  # เดือน 9
    rest = re.sub(r'(?<![\d/])(?:1[89]\d\d|2\d{3})(?![\d/])', '', rest)  # ปี
    return not re.search(r'\d', rest)  # เหลือตัวเลขอื่น = น่าจะเป็นจำนวนเงิน/วันที่ ของคำสั่งบันทึก


def _candidates(name):
    """คำที่ใช้เทียบกับประโยคของหมวดนี้ (ยาวอย่างน้อย 3 ตัวอักษร)"""
    nn = _norm(name)
    out = {nn}
    if nn.startswith('เงิน') and len(nn) > 6:
        out.add(nn[len('เงิน'):])
    for part in str(name or '').split():
        if len(part) >= 3:
            out.add(part)
    return [c for c in out if len(c) >= 3]


def _match_kind(v, cats):
    """cats = [(id, name)] -> (label, [(id, name)]) หรือ None"""
    if 'ปันผล' in v and not ('ปันผลจากหุ้น' in v or 'ปันผลจากกองทุน' in v):
        group = [(i, n) for i, n in cats if _norm(n) in _DIVIDEND_GROUP]
        if group:
            return _DIVIDEND_LABEL, group
    if 'คืนทุน' in v or 'เงินคืน' in v:
        group = [(i, n) for i, n in cats if 'คืนทุน' in _norm(n)]
        if group:
            return ' / '.join(n for _, n in group), group
    found = []  # (id, name, คำที่ตรง)
    for cid, name in cats:
        hits = [c for c in _candidates(name) if c in v]
        if hits:
            found.append((cid, name, max(hits, key=len)))
    keep = []
    for e in found:  # "ค่าน้ำมัน" ไม่ควรตรงกับหมวด "ค่าน้ำ" ด้วย
        if not any(f[0] != e[0] and e[2] != f[2] and e[2] in f[2] for f in found):
            keep.append(e)
    if not keep:
        return None
    return ' / '.join(n for _, n, _m in keep), [(i, n) for i, n, _m in keep]


def match_categories(text, lists):
    """คืน None หรือ {'kind', 'label', 'cats': [(id, name)]} ; ตรงทั้งรายรับและรายจ่าย = ไม่ชัด คืน None"""
    v = _clean(text)
    results = {}
    for kind in (INCOME, EXPENSE):
        res = _match_kind(v, lists.get(_LISTS_KEY[kind]) or [])
        if res:
            results[kind] = res
    if len(results) != 1:
        return None
    kind = next(iter(results))
    label, cats = results[kind]
    return {'kind': kind, 'label': label, 'cats': cats}


# ---------- อ่านข้อมูล (SELECT อย่างเดียว) ----------
_SQL = {
    INCOME: '''
        SELECT t.date,
               COALESCE(NULLIF(TRIM(t.detail_text), ''),
                        (SELECT detail_name FROM detail_master WHERE id = t.detail_id), ''),
               COALESCE(c.name, ''), t.amount, COALESCE(t.note, '')
        FROM income t LEFT JOIN category_income c ON t.category_id = c.id
        WHERE t.year = ? AND t.month = ? AND t.category_id IN (%s)
        ORDER BY t.date DESC, t.id DESC''',
    EXPENSE: '''
        SELECT t.date,
               COALESCE(NULLIF(TRIM(t.detail_text), ''),
                        (SELECT detail_name FROM detail_master WHERE id = t.detail_id), ''),
               COALESCE(c.name, ''), t.amount, COALESCE(t.note, '')
        FROM expense t LEFT JOIN category_expense c ON t.category_id = c.id
        WHERE t.year = ? AND t.month = ? AND t.category_id IN (%s)
        ORDER BY t.date DESC, t.id DESC''',
}


def fetch_month_categories(db_path, kind, year, month, cat_ids):
    ids = [int(i) for i in cat_ids]
    sql = _SQL[kind] % ','.join('?' * len(ids))
    conn = sqlite3.connect(db_path, timeout=5)
    try:
        return conn.execute(sql, [year, month] + ids).fetchall()
    finally:
        conn.close()


def category_totals(cats, rows):
    """[(ชื่อหมวด, จำนวนรายการ, ยอดรวม)] ตามลำดับหมวดที่ตรง (หมวดที่ไม่มีรายการได้ 0)"""
    out = []
    for _cid, name in cats:
        mine = [r for r in rows if r[2] == name]
        out.append((name, len(mine), fl.total_amount(mine)))
    return out


# ---------- HTML ----------
_EXTRA_CSS = """
.sub { background: #2c2c2e; border-radius: 16px; padding: 10px 16px; margin-bottom: 12px; }
.sub .r { display: flex; justify-content: space-between; align-items: baseline; padding: 5px 0;
  font-size: 14px; color: #e5e5ea; }
.sub .r span:last-child { font-variant-numeric: tabular-nums; white-space: nowrap; }
.sub .c { color: #98989f; font-size: 13px; }
"""


def build_html(kind, year, month, label, cats, rows):
    cls = 'income' if kind == INCOME else 'expense'
    cards = []
    for date, detail, category, amount, note in rows:
        try:
            amt = '{:,.2f}'.format(float(amount))
        except (TypeError, ValueError):
            amt = ''
        chip = '<span class="chip">%s</span>' % fl._esc(category) if str(category or '').strip() else ''
        note_html = '<div class="note">%s</div>' % fl._esc(note) if str(note or '').strip() else ''
        cards.append(
            '<div class="card"><div class="row1"><span class="date">%s</span>%s'
            '<span class="amt %s">%s</span></div><div class="detail">%s</div>%s</div>'
            % (fl._esc(date), chip, cls, amt, fl._esc(detail), note_html))
    sub = ''
    if len(cats) > 1:
        lines = ''.join(
            '<div class="r"><span>%s <span class="c">(%d รายการ)</span></span><span class="%s">%s</span></div>'
            % (fl._esc(n), cnt, cls, '{:,.2f}'.format(s)) for n, cnt, s in category_totals(cats, rows))
        sub = '<div class="sub">%s</div>' % lines
    title = '%s %s' % (label, fl.month_title(year, month))
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<style>' + fl._CSS + _EXTRA_CSS + '</style></head><body>'
        '<h2>' + fl._esc(title) + '</h2>'
        '<div class="bar"><span>ทั้งหมด %d รายการ</span>'
        '<span class="total %s">รวม %s บาท</span></div>'
        % (len(rows), cls, '{:,.2f}'.format(fl.total_amount(rows)))
        + sub + ''.join(cards) + '</body></html>')


# ---------- ลำดับงาน ----------
def try_start(host, text):
    """เรียกจาก finance_flow.ask_date_first; True = รับคำสั่งนี้แล้ว (แสดงป๊อปอัป)"""
    if not looks_like_filter_request(text):
        return False
    try:
        folder = fdb.find_finance_folder()
        db = fdb.guess_default_db(folder)
        if db is None or not os.path.isfile(db['path']):
            return False
        lists = fdb.read_lists(db['path'])
        match = match_categories(text, lists)
        if match is None:
            return False
        month, year = fl._parse_month_year(_clean(text), datetime.date.today())
    except Exception as e:  # อ่านไฟล์ไม่ได้ ฯลฯ ให้ขั้นตอนอื่นรายงานแทน
        debug_log('finance_filter: pre-check skipped %r' % (e,))
        return False
    Filterer(host, text, match, {'year': year, 'month': month}, folder, db).show()
    return True


class Filterer:
    def __init__(self, host, text, match, when, folder, db):
        self.host = host
        self.text = text
        self.match = match
        self.when = when
        self.folder = folder
        self.db = db
        self.done = False

    def show(self):
        host = self.host
        host._filter_runner = self  # เก็บไว้ให้อยู่จนจบ
        host._live = {'time': config.now_text(), 'model': config.get_current_model(),
                      'user': self.text, 'ai': '', 'status': 'live'}
        y, m = self.when['year'], self.when['month']
        if not 1 <= m <= 12:
            self.finish('เดือน %s ไม่ถูกต้อง (ต้อง 1-12)' % m)
            return
        if not 2000 <= y <= 2100:
            self.finish('ปี %s ไม่ถูกต้อง' % y)
            return
        label = self.match['label']
        if len(label) > 30:
            label = label[:29] + '…'
        title = 'แสดงรายการ %s\n%s ใช่ไหม?' % (label, fl.month_title(y, m))
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
            debug_log('finance_filter: error %r' % (e,))
            self.finish('แสดงรายการไม่สำเร็จ: %s' % e)

    def _show_list(self):
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
        kind, label, cats = self.match['kind'], self.match['label'], self.match['cats']
        y, m = self.when['year'], self.when['month']
        rows = fetch_month_categories(path, kind, y, m, [c[0] for c in cats])
        if not rows:
            self.finish('ไม่มีรายการ %s เดือน%s %d ในไฟล์ %s' % (label, fl._MONTHS[m], y, name))
            return
        html = build_html(kind, y, m, label, cats, rows)
        view = fl._ResultView('%s %s %d' % (label, fl._MONTHS[m], y + 543), html)
        fl._VIEWS = fl._VIEWS[-2:] + [view]
        view.present('fullscreen', animated=True)
        self.finish('แสดงรายการ %s %s แล้ว: %d รายการ รวม %s บาท (ไฟล์ %s)'
                    % (label, fl.month_title(y, m), len(rows),
                       '{:,.2f}'.format(fl.total_amount(rows)), name))

    def finish(self, message):
        if self.done:
            return
        self.done = True
        host = self.host
        if getattr(host, '_filter_runner', None) is self:
            host._filter_runner = None
        host._finish_turn(message, 'ok', tool=True)  # tool=True: ไม่ให้ AI จำรอบนี้เป็นบทสนทนา
        try:
            host.input.text = ''
        except Exception:
            pass
