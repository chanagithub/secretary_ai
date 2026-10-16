"""finance_flow.py - ลำดับงานของโหมดรายรับรายจ่าย (API เหมือน assistant_flow ที่ app_ui เรียกใช้)

  ask_ai(sent_text, on_chunk, token, model, history) -> (text, calls)
  prepare_actions(calls, host)                       -> actions (ตรวจค่าที่ AI ส่งมาแล้ว)
  run_actions(host, actions, on_done)                 -> เริ่มลำดับป๊อปอัป; on_done(lines, redo, saved)

ลำดับต่อหนึ่งรายการ: วันที่ (ถ้าไม่ได้พูด) -> หมวด (ว่าง/ไม่ตรง) -> ประเภทชำระ (รายจ่าย ว่าง) -> ยืนยัน
  กด "ตกลง" -> finance_write.save_record (เขียน + อ่านกลับตรวจ) แล้วค่อยแจ้ง "บันทึกแล้ว ✓"
  กด "แก้ไข" -> เมนูเลือกช่อง (วันที่/รายการ/หมวด/ชำระ/จำนวนเงิน/หมายเหตุ/ไฟล์) แก้ทีละช่อง แล้วกลับหน้ายืนยัน
  "ระบุวันที่" -> จบรอบนี้โดยไม่บันทึก ให้ผู้ใช้พูดวันในข้อความถัดไป (host._keep_context = True)
ข้อมูลที่ถูกเขียนมาจากโค้ดเท่านั้น AI แค่แปลคำพูดเป็นพารามิเตอร์ (ดู finance_tools.py)
callback ทั้งหมดเป็น bound method และเปิดป๊อปอัปถัดไปด้วย ui.delay(เมธอด, 0.3) ตามบทเรียนกันล่ม
"""
import datetime
import re

import ui
import console
import ai_client
import finance_db as fdb
import finance_tools as ft
import finance_write as fw
import finance_files
import finance_summary
import finance_listing
from overlays import ChoiceOverlay
from finance_overlays import FinanceConfirmOverlay, ListPickOverlay, TextInputOverlay
from debug_log import log as debug_log

_PSEUDO_NOTE = 'ขออภัยครับ ประมวลผลคำสั่งนี้ไม่สำเร็จ ลองพิมพ์ใหม่อีกครั้ง'
_TEXT_FIELDS = {
    'date': ('วันที่ (เช่น เมื่อวาน, 5 ตุลา, 5/10/2026)', 'default'),
    'detail': ('ชื่อรายการ', 'default'),
    'amount': ('จำนวนเงิน (บาท)', 'decimal'),
    'note': ('หมายเหตุ (เว้นว่างได้)', 'default'),
}


def _note(text):
    return {'id': None, 'name': '_note', 'local_note': text, 'arguments': {}}


# ---------- ไฟล์ฐานข้อมูล + รายการอ้างอิง ----------
def open_db(info, folder):
    """info = dict จาก finance_db.list_db_files -> {'folder','db','lists'} หรือ raise FinanceDBError"""
    problems = fdb.check_schema(info['path'])
    if any('locked' in p or 'busy' in p for p in problems):
        raise fdb.FinanceDBError('ไฟล์ %s กำลังถูกใช้งานอยู่ (ถูกล็อก) ลองใหม่อีกครั้งสักครู่' % info['name'])
    if problems:
        raise fdb.FinanceDBError('ไฟล์ %s โครงสร้างไม่ครบ ไม่เขียนข้อมูลลงไฟล์นี้: %s'
                                 % (info['name'], problems[0]))
    return {'folder': folder, 'db': info, 'lists': fdb.read_lists(info['path'])}


def load_context():
    folder = fdb.find_finance_folder()
    info = fdb.guess_default_db(folder)
    if info is None:
        raise fdb.FinanceDBError('ไม่พบไฟล์ .db ในโฟลเดอร์ ChanaFinance')
    return open_db(info, folder)


# ---------- 1) ถาม AI ----------
def _system_prompt(ctx):
    """system prompt ทั้งก้อนของโหมดนี้ (ใช้แทนของโหมดเตือนความจำใน ai_client)"""
    now = datetime.datetime.now()
    head = ('คุณคือเลขาส่วนตัวของผู้ใช้ ตอบเป็นภาษาไทย กระชับ ตรงประเด็น\n'
            'ปฏิทิน 14 วันข้างหน้า (ใช้แปลงชื่อวันเป็นวันที่จริง ห้ามคำนวณเอง):\n%s\n'
            % ai_client._calendar_lines(now))
    return head + ft.system_message(ctx['lists'], ctx['db']['name'], now.date())['content']


_DATE_WORDS = ('วันนี้', 'เมื่อวาน', 'เมื่อวานนี้', 'เมื่อวานซืน', 'พรุ่งนี้', 'มะรืน',
               'เดือนนี้', 'เดือนก่อน', 'เดือนหน้า')
_FINANCE_ACTION_WORDS = ('จ่าย', 'ชำระ', 'ซื้อ', 'เสียค่า', 'ค่าเช่า', 'ค่าไฟ', 'ค่าน้ำ',
                         'ได้รับ', 'รับเงิน', 'เงินเดือน', 'รายรับ', 'ขาย', 'ปันผล', 'ดอกเบี้ย')

def _has_date_mention(text):
    value = str(text or '').translate(ft._DIGITS)
    if any(word in value for word in _DATE_WORDS):
        return True
    if re.search(r'\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b', value):
        return True
    if re.search(r'(?<!\d)\d{1,2}[-/.]\d{1,2}(?:[-/.]\d{2,4})?(?!\d)', value):
        return True
    if re.search(r'(?<!\d)\d{1,2}\s*(?:มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม|ม\.?ค\.?|ก\.?พ\.?|มี\.?ค\.?|เม\.?ย\.?|พ\.?ค\.?|มิ\.?ย\.?|ก\.?ค\.?|ส\.?ค\.?|ก\.?ย\.?|ต\.?ค\.?|พ\.?ย\.?|ธ\.?ค\.?)(?:\s*\d{2,4})?', value):
        return True
    return False

def _looks_like_undated_transaction(text):
    value = str(text or '').translate(ft._DIGITS).lower()
    has_amount = bool(re.search(r'(?<![\w])\d[\d,]*(?:\.\d+)?\s*(?:บาท|พัน|หมื่น|แสน|ล้าน|k)?', value))
    has_action = any(word in value for word in _FINANCE_ACTION_WORDS)
    return has_amount and has_action and not _has_date_mention(value)

def ask_date_first(host, text):
    """ถามวันที่ในแอปก่อนเรียก AI สำหรับคำสั่งรับ/จ่ายเงินที่ยังไม่มีวันที่."""
    if finance_files.is_switch_request(text):  # "เปลี่ยนไฟล์" -> ขึ้นรายการไฟล์ ไม่เรียก AI
        finance_files.FileSwitcher(host, text).show()
        return True
    summary_req = finance_summary.parse_request(text)  # "สรุปเดือนนี้" / "สรุปรายปี" -> รายงานของ ChanaFinance
    if summary_req is not None:
        finance_summary.Summarizer(host, text, summary_req).show()
        return True
    listing_req = finance_listing.parse_request(text)  # "ขอดูรายรับเดือนนี้" -> หน้ารายการของเดือน (อ่านอย่างเดียว)
    if listing_req is not None:
        finance_listing.Lister(host, text, listing_req).show()
        return True
    if not _looks_like_undated_transaction(text):
        return False
    FinanceDatePreflight(host, text).show()
    return True

class FinanceDatePreflight:
    def __init__(self, host, text):
        self.host = host
        self.text = text
        self.value = ''

    def show(self):
        today = datetime.date.today()
        title = 'ไม่ได้บอกวันที่ ใช้วันนี้ใช่ไหม?\n(%s)' % ft.format_day_text(today)
        self.host.show_overlay(ChoiceOverlay(
            title, [('ใช่ วันนี้', 'today'), ('ระบุวันที่', 'set')],
            self.on_pick, lambda: None))

    def on_pick(self, value):
        self.value = value
        ui.delay(self.do_pick, 0.3)

    def do_pick(self):
        if self.value == 'today':
            self._start(datetime.date.today())
            return
        self._show_date_input('')

    def _show_date_input(self, initial):
        self.host.show_overlay(TextInputOverlay(
            'พิมพ์วันที่ เช่น เมื่อวาน หรือ 5 ต.ค. 2569', initial,
            self.on_date_text, lambda: None))

    def on_date_text(self, value):
        self.value = value
        ui.delay(self.do_date_text, 0.3)

    def do_date_text(self):
        day = ft.parse_date_text(self.value)
        if day is None:
            self._show_date_input(self.value)
            return
        try:
            ft.check_date(day)
        except ft.FinanceToolError:
            self._show_date_input(self.value)
            return
        self._start(day)

    def _start(self, day):
        sent_text = '%s (วันที่ %s)' % (self.text, day.isoformat())
        self.host.start_request(self.text, sent_text)

def ask_ai(sent_text, on_chunk, token, model, history):
    """คืน (text, tool_calls); ปัญหาของไฟล์/โครงสร้างคืนเป็นข้อความแจ้ง (_note) ไม่ raise"""
    try:
        ctx = load_context()
    except fdb.FinanceDBError as e:
        return '', [_note('โหมดรายรับรายจ่ายใช้ไม่ได้: %s' % e)]
    msgs = [m for m in (history or []) if m.get('role') != 'system']  # ตัดสแนปช็อตรายการเตือนออก
    source = ' '.join([str(m.get('content') or '') for m in msgs if m.get('role') == 'user']
                      + [sent_text])
    text, calls = ai_client.stream_chat_with_tools(
        sent_text, on_chunk, token, ft.schemas(ctx['lists']),
        model=model, history=msgs, system_prompt=_system_prompt(ctx))
    if not calls:
        if not (text or '').strip():
            debug_log('finance: AI returned no text or tool call')
            return '', [_note('AI ยังไม่ได้ส่งคำสั่งกลับมา กรุณาส่งคำสั่งเดิมอีกครั้ง')]
        if text and ('record_' in text or 'default_api' in text) and '(' in text:
            debug_log('finance: pseudo tool-call text')
            return '', [_note(_PSEUDO_NOTE)]
        return text, []  # AI ถามกลับ (เช่น ขาดจำนวนเงิน) หรือบอกว่าเป็นเรื่องของโหมดอื่น
    for call in calls:
        call['finance_ctx'] = ctx
        call['source_text'] = source
    return text, calls


# ---------- 2) ตรวจค่า ----------
def prepare_actions(tool_calls, host=None):
    actions = []
    for call in tool_calls:
        if call.get('local_note'):
            actions.append({'kind': 'note', 'text': call['local_note']})
            continue
        name = call.get('name')
        ctx = call.get('finance_ctx')
        if name not in ft.TOOL_NAMES or ctx is None:
            actions.append({'kind': 'note',
                            'text': '(AI เรียกเครื่องมือที่ไม่รู้จัก: %s ข้ามไป)' % name})
            continue
        try:
            rec = ft.validate_record(call.get('arguments'), ft.KIND_BY_TOOL[name], ctx['lists'])
        except ft.FinanceToolError as e:
            actions.append({'kind': 'note', 'text': 'ตรวจค่าไม่ผ่าน: %s' % e})
            continue
        actions.append({'kind': 'finance', 'rec': rec, 'db': ctx['db'], 'lists': ctx['lists'],
                        'folder': ctx['folder'], 'source': call.get('source_text', '')})
    return actions


# ---------- 3) ป๊อปอัป + บันทึก ----------
def _guarded(method):
    """กันข้อผิดพลาดไม่คาดคิดในขั้นตอนป๊อปอัปจนแอปค้างกลางทาง: แจ้งแล้วจบรอบ"""
    def wrapper(self, *args):
        if self.finished:
            return
        try:
            method(self, *args)
        except Exception as e:
            debug_log('finance: error in %s: %r' % (method.__name__, e))
            self.lines.append('เกิดข้อผิดพลาดภายใน ยังไม่ได้บันทึกรายการที่ค้างอยู่: %s' % e)
            self.queue = []
            self.finish()
    wrapper.__name__ = method.__name__
    return wrapper


class FinanceRunner:
    def __init__(self, host, actions, on_done):
        self.host = host
        self.queue = list(actions)
        self.lines = []
        self.saved = False
        self.on_done = on_done
        self.finished = False
        self.rec = None
        self.db = None
        self.lists = None
        self.folder = None
        self.source = ''
        self.amount_warn = ''
        self.notice = ''
        self.editing = False
        self.edit_field = None
        self._pick = None
        self._text = None

    # ----- คิว -----
    def start(self):
        debug_log('finance: run_actions start, %d action(s)' % len(self.queue))
        self.step()

    def finish(self, redo=False):
        if self.finished:
            return
        self.finished = True
        debug_log('finance: finish redo=%s saved=%s' % (redo, self.saved))
        if getattr(self.host, '_action_runner', None) is self:
            self.host._action_runner = None
        self.on_done(list(self.lines), redo, self.saved)

    def skip_rest(self):
        for a in self.queue:
            if a['kind'] == 'note':
                self.lines.append(a['text'])
            else:
                self.lines.append('ยังไม่ได้บันทึก "%s" (รายการถัดไป) กรุณาสั่งใหม่' % a['rec']['detail'])
        self.queue = []

    @_guarded
    def step(self):
        if not self.queue:
            self.finish()
            return
        action = self.queue.pop(0)
        if action['kind'] == 'note':
            self.lines.append(action['text'])
            self.step()
            return
        self.rec = dict(action['rec'])
        self.db, self.lists, self.folder = action['db'], action['lists'], action['folder']
        self.source = action['source']
        self.amount_warn = ft.amount_warning(self.rec['amount'], self.source)
        self.notice = ''
        self.editing = False
        self.ask_next()

    # ----- ลำดับ: วันที่ -> หมวด -> ประเภทชำระ -> ยืนยัน -----
    def _cat_key(self):
        return 'category_expense' if self.rec['kind'] == ft.EXPENSE else 'category_income'

    @_guarded
    def ask_next(self):
        rec = self.rec
        if rec['date'] is None:
            self.show_date_ask()
        elif rec['category_id'] is None:
            self.show_list_pick('category')
        elif rec['kind'] == ft.EXPENSE and rec['payment_id'] is None:
            self.show_list_pick('payment')
        else:
            self.show_confirm()

    def show_date_ask(self):
        today = datetime.date.today()
        title = 'ไม่ได้บอกวันที่ ใช้วันนี้ใช่ไหม?\n(%s)' % ft.format_day_text(today)
        self.host.show_overlay(ChoiceOverlay(
            title, [('ใช่ วันนี้', 'today'), ('ระบุวันที่', 'set')],
            self.on_date_pick, self.on_cancel))

    def on_date_pick(self, value):
        self._pick = value
        ui.delay(self.do_date_pick, 0.3)

    @_guarded
    def do_date_pick(self):
        if self._pick == 'today':
            self.rec['date'] = datetime.date.today().isoformat()
            self.ask_next()
            return
        # ระบุวันที่: จบรอบนี้ (ยังไม่บันทึก) ให้ผู้ใช้พูดวันในข้อความถัดไป AI จำคำสั่งเดิมจากแชท
        self.lines.append('ยังไม่ได้บันทึก "%s": บอกวันที่ที่ต้องการได้เลยครับ (เช่น เมื่อวาน, 5 ตุลา)'
                          % self.rec['detail'])
        self.host._keep_context = True
        self.skip_rest()
        self.finish()

    def show_list_pick(self, which):
        if which == 'category':
            items = [(name, (cid, name)) for cid, name in self.lists[self._cat_key()]]
            title = 'เลือกหมวด%s' % ft.kind_text(self.rec['kind'])
            callback = self.on_category_pick
        else:
            items = [(name, (pid, name)) for pid, name in self.lists['payment_type']]
            title = 'เลือกประเภทการชำระ'
            callback = self.on_payment_pick
        if not items:
            self.lines.append('ไฟล์ %s ยังไม่มี%s ให้เพิ่มในแอป ChanaFinance ก่อน ยังไม่ได้บันทึก "%s"'
                              % (self.db['name'], title[5:] if which == 'category' else 'ประเภทการชำระ',
                                 self.rec['detail']))
            self.step()
            return
        self.host.show_overlay(ListPickOverlay(title, items, callback, self.on_cancel))

    @staticmethod
    def _name_of(items, item_id):
        for i, name in items:
            if i == item_id:
                return name
        return None

    def on_category_pick(self, value):
        self._pick = value
        ui.delay(self.do_category_pick, 0.3)

    @_guarded
    def do_category_pick(self):
        self.rec['category_id'], self.rec['category_name'] = self._pick
        self.ask_next()

    def on_payment_pick(self, value):
        self._pick = value
        ui.delay(self.do_payment_pick, 0.3)

    @_guarded
    def do_payment_pick(self):
        self.rec['payment_id'], self.rec['payment_name'] = self._pick
        self.ask_next()

    # ----- ยืนยันสุดท้าย -----
    def _warning_text(self):
        return '\n⚠ '.join(w for w in (self.amount_warn, self.notice) if w)

    def show_confirm(self):
        self.editing = False
        body = ft.format_confirm_text(self.rec, self.db['name'], self._warning_text())
        self.notice = ''
        self.host.show_overlay(FinanceConfirmOverlay(
            ft.confirm_title(self.rec['kind']), body,
            self.on_ok, self.on_edit, self.on_cancel, self.on_redo))

    def on_ok(self):
        debug_log('finance: confirm accepted; scheduling save')
        ui.delay(self.do_ok, 0.3)

    @_guarded
    def do_ok(self):
        debug_log('finance: do_ok start db=%s' % self.db.get('name'))
        ok, msg, row_id = fw.save_record(self.db['path'], self.rec)
        debug_log('finance: save_record returned ok=%s row_id=%s' % (ok, row_id))
        if ok:
            self.saved = True
            self.lines.append(ft.format_saved_line(self.rec, self.db['name']))
            fdb.set_last_db_name(self.db['name'])
        elif row_id is None:
            self.lines.append('ไม่ได้บันทึก "%s": %s' % (self.rec['detail'], msg))
        else:  # เขียนแล้วแต่ตรวจกลับไม่ได้/ไม่ตรง: ข้อความบอกให้ตรวจในแอป ChanaFinance
            self.lines.append('%s ("%s")' % (msg, self.rec['detail']))
        self.step()

    def on_cancel(self):
        ui.delay(self.do_cancel, 0.3)

    @_guarded
    def do_cancel(self):
        if self.editing:  # ยกเลิกในเมนู/ตัวเลือกของโหมดแก้ไข = กลับหน้ายืนยัน ไม่ใช่ยกเลิกรายการ
            self.show_confirm()
            return
        self.lines.append('ยกเลิก ไม่บันทึก: "%s"' % self.rec['detail'])
        self.step()

    def on_redo(self):
        ui.delay(self.do_redo, 0.3)

    @_guarded
    def do_redo(self):
        self.lines.append('ยกเลิก ไม่บันทึก: "%s" (ขอทำรายการใหม่)' % self.rec['detail'])
        self.skip_rest()
        self.finish(redo=True)

    # ----- แก้ไขทีละช่อง -----
    def on_edit(self):
        ui.delay(self.do_edit, 0.3)

    @_guarded
    def do_edit(self):
        rec = self.rec
        day = datetime.date.fromisoformat(rec['date'])
        items = [('วันที่: %s' % ft.format_day_text(day), 'date'),
                 ('รายการ: %s' % rec['detail'], 'detail'),
                 ('หมวด: %s' % (rec.get('category_name') or '-'), 'category')]
        if rec['kind'] == ft.EXPENSE:
            items.append(('ประเภทชำระ: %s' % (rec.get('payment_name') or '-'), 'payment'))
        items += [('จำนวนเงิน: %s บาท' % ft.format_amount(rec['amount']), 'amount'),
                  ('หมายเหตุ: %s' % (rec.get('note') or '-'), 'note'),
                  ('ไฟล์: %s' % self.db['name'], 'file')]
        self.editing = True
        self.host.show_overlay(ListPickOverlay('แก้ไขช่องไหน?', items, self.on_field_pick, self.on_cancel))

    def on_field_pick(self, value):
        self._pick = value
        ui.delay(self.do_field_pick, 0.3)

    @_guarded
    def do_field_pick(self):
        field = self._pick
        rec = self.rec
        if field in _TEXT_FIELDS:
            title, keyboard = _TEXT_FIELDS[field]
            initial = {'date': rec['date'], 'detail': rec['detail'], 'note': rec.get('note') or '',
                       'amount': '%.2f' % rec['amount']}[field]
            self.edit_field = field
            self.host.show_overlay(TextInputOverlay(title, initial, self.on_text_ok,
                                                    self.on_cancel, keyboard=keyboard))
        elif field == 'category':
            self.show_list_pick('category')
        elif field == 'payment':
            self.show_list_pick('payment')
        else:  # file
            items = [(f['name'] + (' (ใช้อยู่)' if f['name'] == self.db['name'] else ''), f['name'])
                     for f in fdb.list_db_files(self.folder)]
            self.host.show_overlay(ListPickOverlay('เลือกไฟล์ข้อมูล', items,
                                                   self.on_file_pick, self.on_cancel))

    def on_text_ok(self, text):
        self._text = text
        ui.delay(self.do_text_ok, 0.3)

    def _apply_text(self, field, text):
        text = ' '.join((text or '').split())
        rec = self.rec
        if field == 'date':
            day = ft.parse_date_text(text)
            if day is None:
                raise ft.FinanceToolError('อ่านวันที่ไม่ออก ลองพิมพ์ เช่น เมื่อวาน, 5 ตุลา, 5/10/2026')
            rec['date'] = ft.check_date(day).isoformat()
        elif field == 'detail':
            if not text:
                raise ft.FinanceToolError('ชื่อรายการว่างไม่ได้')
            rec['detail'] = text[:100]
        elif field == 'amount':
            rec['amount'] = ft.parse_amount(text)
            self.amount_warn = ''  # ผู้ใช้พิมพ์ตัวเลขเอง ไม่ต้องเทียบกับคำพูดอีก
        else:
            rec['note'] = text[:200]

    @_guarded
    def do_text_ok(self):
        try:
            self._apply_text(self.edit_field, self._text)
        except ft.FinanceToolError as e:
            console.hud_alert(str(e)[:80], 'error', 2.5)
        self.show_confirm()

    def on_file_pick(self, value):
        self._pick = value
        ui.delay(self.do_file_pick, 0.3)

    @_guarded
    def do_file_pick(self):
        info = next((f for f in fdb.list_db_files(self.folder) if f['name'] == self._pick), None)
        if info is None or info['name'] == self.db['name']:
            self.show_confirm()
            return
        try:
            ctx = open_db(info, self.folder)
        except fdb.FinanceDBError as e:
            self.notice = str(e)  # แสดงเป็นบรรทัด ⚠ ในหน้ายืนยัน (ยังใช้ไฟล์เดิม)
            self.show_confirm()
            return
        self.db, self.lists = ctx['db'], ctx['lists']
        rec = self.rec
        cat = fdb.find_by_name(self.lists[self._cat_key()], rec.get('category_name'))
        rec['category_id'], rec['category_name'] = (cat[0], cat[1]) if cat else (None, None)
        if rec['kind'] == ft.EXPENSE:
            pay = fdb.find_by_name(self.lists['payment_type'], rec.get('payment_name'))
            rec['payment_id'], rec['payment_name'] = (pay[0], pay[1]) if pay else (None, None)
        self.editing = False  # ถ้าหมวด/ชำระไม่มีในไฟล์ใหม่ ต้องเลือกใหม่ ยกเลิก = ยกเลิกรายการ
        self.ask_next()


def run_actions(host, actions, on_done):
    """รัน actions โดยเก็บ runner ไว้ที่ host ให้อยู่ได้นานพอ (เหมือน assistant_flow)"""
    runner = FinanceRunner(host, actions, on_done)
    host._action_runner = runner
    runner.start()
