"""notes_flow.py - ลำดับงานของโหมดโน้ต (API เหมือน finance_flow / assistant_flow ที่ app_ui เรียกใช้)

  ask_ai(sent_text, on_chunk, token, model, history) -> (text, calls)
  prepare_actions(calls, host=None)                  -> actions (ตรวจค่าที่ AI ส่งมาแล้ว)
  run_actions(host, actions, on_done)                -> เริ่มลำดับป๊อปอัป; on_done(lines, redo, saved)

ลำดับต่อหนึ่งคำสั่ง:
  ถาม "สร้างโน้ตใหม่ / ต่อโน้ตเดิม"
    ใหม่  -> "ใช้ชื่อที่เสนอไหม" (ใช้ชื่อนี้ / พิมพ์ชื่อเอง) -> ยืนยัน
    ต่อ   -> อ่านรายชื่อโน้ตผ่าน Shortcut -> ผู้ใช้เลือกโน้ตจากรายการ -> ตรวจชื่อซ้ำ/ซ้อน -> ยืนยัน
  ยืนยัน: ตกลง -> ส่งให้ Shortcut AI SaveToNote / ไม่เอา / ทำรายการใหม่
ชื่อโน้ตที่จะต่อท้ายมาจากรายการจริงเท่านั้น AI ไม่เกี่ยว; เนื้อหามาจากคำพูดผู้ใช้ (ดู notes_tools.py)
Python ยืนยันไม่ได้ว่าโน้ตถูกสร้างจริง ข้อความผลลัพธ์จึงเป็นกลาง ("ส่งคำสั่งไปยัง Shortcut แล้ว")
callback ทั้งหมดเป็น bound method และเปิดป๊อปอัปถัดไปด้วย ui.delay(เมธอด, 0.3) ตามบทเรียนกันล่ม
"""
import datetime

import ui
import ai_client
import notes_shortcut
import notes_tools as nt
from overlays import ChoiceOverlay, ConfirmOverlay
from finance_overlays import ListPickOverlay, TextInputOverlay
from debug_log import log as debug_log

_PSEUDO_NOTE = 'ขออภัยครับ ประมวลผลคำสั่งนี้ไม่สำเร็จ ลองพิมพ์ใหม่อีกครั้ง'
NOTES_DIAGNOSTIC_BUILD = 'notes-fake-names-1'
# ทดลองแยกสาเหตุล่ม: True = ไม่เรียก Shortcut อ่านรายชื่อ ใช้ชื่อสมมติ 3 ชื่อ และไม่ส่งคำสั่งบันทึกจริง
# ตั้งเป็น False เมื่อทดลองเสร็จ
DEBUG_FAKE_NAMES = True
debug_log('notes_flow BUILD=%s loaded' % NOTES_DIAGNOSTIC_BUILD)


def _note(text):
    return {'id': None, 'name': '_note', 'local_note': text, 'arguments': {}}


# ---------- 1) ถาม AI ----------
def ask_ai(sent_text, on_chunk, token, model, history):
    """คืน (text, tool_calls); ไม่ raise เรื่องเนื้อหา (ปัญหาคืนเป็น _note)"""
    msgs = [m for m in (history or []) if m.get('role') != 'system']  # ตัดสแนปช็อตรายการเตือนออก
    text, calls = ai_client.stream_chat_with_tools(
        sent_text, on_chunk, token, nt.schemas(),
        model=model, history=msgs,
        system_prompt=nt.system_prompt(datetime.date.today()))
    if not calls:
        inferred_note = nt.infer_explicit_body_request(sent_text)
        if inferred_note:
            return '', [{'name': nt.TOOL_NAME,
                         'arguments': inferred_note,
                         'source_text': sent_text}]
        inferred_title = nt.infer_title_only_request(sent_text)
        if inferred_title:
            # กรณีพิมพ์แค่ชื่อ AI อาจตอบเป็นข้อความแทนเรียกเครื่องมือ
            # ในโหมดโน้ตให้ตีความเป็นคำขอสร้างโน้ตเปล่าและให้ผู้ใช้ยืนยันก่อน
            return '', [{'name': nt.TOOL_NAME,
                         'arguments': {'content': '', 'title': inferred_title},
                         'source_text': sent_text}]
        if not (text or '').strip():
            debug_log('notes: AI returned no text or tool call')
            return '', [_note('AI ยังไม่ได้ส่งคำสั่งกลับมา กรุณาส่งคำสั่งเดิมอีกครั้ง')]
        if text and ('default_api' in text or (nt.TOOL_NAME in text and '(' in text)):
            debug_log('notes: pseudo tool-call text')
            return '', [_note(_PSEUDO_NOTE)]
        return text, []  # AI ตอบเป็นข้อความ (เช่น บอกว่าโหมดนี้ค้นโน้ตไม่ได้)
    for call in calls:
        call['source_text'] = sent_text
    return text, calls


# ---------- 2) ตรวจค่า ----------
def prepare_actions(tool_calls, host=None):
    actions = []
    saves = 0
    for call in tool_calls:
        if call.get('local_note'):
            actions.append({'kind': 'note', 'text': call['local_note']})
            continue
        if call.get('name') != nt.TOOL_NAME:
            actions.append({'kind': 'note',
                            'text': '(AI เรียกเครื่องมือที่ไม่รู้จัก: %s ข้ามไป)' % call.get('name')})
            continue
        if saves >= 1:  # ทำทีละโน้ต: ต้องเลือกโน้ตปลายทางด้วยป๊อปอัปของแต่ละโน้ต
            actions.append({'kind': 'note',
                            'text': 'ได้รับคำสั่งบันทึกหลายรายการพร้อมกัน บันทึกเฉพาะรายการแรก '
                                    'ที่เหลือกรุณาสั่งใหม่ทีละรายการ'})
            continue
        try:
            item = nt.validate_call(call.get('arguments'), call.get('source_text', ''))
        except nt.NotesToolNeedContent as e:
            if host is not None:
                host._keep_context = True
            actions.append({'kind': 'note', 'text': str(e)})
            continue
        except nt.NotesToolError as e:
            actions.append({'kind': 'note', 'text': 'ตรวจค่าไม่ผ่าน: %s' % e})
            continue
        saves += 1
        actions.append({'kind': 'save', 'content': item['content'], 'title': item['title'],
                        'used_fallback': item['used_fallback'],
                        'mode': nt.requested_mode(call.get('source_text', ''))})
    return actions


# ---------- 3) ป๊อปอัป + ส่งให้ Shortcut ----------
def _guarded(method):
    """กันข้อผิดพลาดไม่คาดคิดในขั้นตอนป๊อปอัปจนแอปค้างกลางทาง: แจ้งแล้วจบรอบ"""
    def wrapper(self, *args):
        if self.finished:
            return
        try:
            method(self, *args)
        except Exception as e:
            debug_log('notes: error in %s: %r' % (method.__name__, e))
            self.lines.append('เกิดข้อผิดพลาดภายใน ยังไม่ได้ส่งคำสั่งบันทึกโน้ต: %s' % e)
            self.queue = []
            self.finish()
    wrapper.__name__ = method.__name__
    return wrapper


class NotesRunner:
    def __init__(self, host, actions, on_done):
        self.host = host
        self.queue = list(actions)
        self.lines = []
        self.saved = False   # True = ส่งคำสั่งให้ Shortcut แล้ว (ยืนยันผลจริงไม่ได้)
        self.on_done = on_done
        self.finished = False
        self.item = None
        self.mode = None
        self.title = ''
        self.names = []
        self.append_target_title = ''
        self.reader = None
        self._pick = None
        self._text = None
        self.append_timestamp = None

    # ----- คิว -----
    def start(self):
        debug_log('notes: run_actions start, %d action(s)' % len(self.queue))
        self.step()

    def finish(self, redo=False):
        if self.finished:
            return
        self.finished = True
        debug_log('notes: finish redo=%s saved=%s' % (redo, self.saved))
        if getattr(self.host, '_action_runner', None) is self:
            self.host._action_runner = None
        self.on_done(list(self.lines), redo, self.saved)

    def skip_rest(self):
        for a in self.queue:
            self.lines.append(a['text'] if a['kind'] == 'note'
                              else 'ยังไม่ได้บันทึก "%s" (รายการถัดไป) กรุณาสั่งใหม่' % a['title'])
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
        self.item = action
        self.mode = action.get('mode') or 'new'
        self.title = action['title']
        debug_log('notes action: mode=%s empty_body=%s title_is_zero=%s' %
                  (self.mode, not bool(action['content'].strip()),
                   str(self.title or '').strip() == '0'))
        if self.mode == 'append':
            if not action['content'].strip():
                self.lines.append('ยังไม่มีเนื้อหาที่จะต่อท้าย กรุณาระบุข้อความก่อนครับ')
                self.step()
                return
            if DEBUG_FAKE_NAMES:
                debug_log('notes: DEBUG_FAKE_NAMES on, skipping NoteListReader')
                self.on_names(['Fake note 1', 'Fake note 2', 'Fake note 3'])
                return
            self.reader = notes_shortcut.NoteListReader(self.on_names, self.on_names_error)
            self.reader.start()
            return
        if not action['content'].strip():
            # ชื่ออย่างเดียวหมายถึงขอสร้างโน้ตเปล่า: แสดงยืนยันสร้างโดยตรง
            self.show_confirm()
            return
        self.show_title_ask()

    # ----- 1: สร้างใหม่ / ต่อโน้ตเดิม -----
    def show_mode_choice(self):
        preview = self.item['content'].replace('\n', ' ').strip()
        if not preview:
            preview = '(ไม่มีเนื้อหา)'
        if len(preview) > 40:
            preview = preview[:40] + '...'
        options = [('สร้างโน้ตใหม่', 'new')]
        if self.item['content'].strip():
            options.append(('ต่อโน้ตเดิม', 'append'))
        self.host.show_overlay(ChoiceOverlay(
            'บันทึกลงโน้ต\n"%s"' % preview,
            options, self.on_mode_pick, self.on_cancel))

    def on_mode_pick(self, value):
        self._pick = value
        ui.delay(self.do_mode_pick, 0.3)

    @_guarded
    def do_mode_pick(self):
        self.mode = self._pick
        if self.mode == 'append':
            self.reader = notes_shortcut.NoteListReader(self.on_names, self.on_names_error)
            self.reader.start()  # แอปจะสลับไป Shortcuts แล้วกลับมาเอง (ต้องกด Allow Paste)
        else:
            self.show_title_ask()

    # ----- 2ก: โน้ตใหม่ ยืนยันชื่อ -----
    def show_title_ask(self):
        self.host.show_overlay(ChoiceOverlay(
            'ใช้ชื่อโน้ตนี้ไหม?\n"%s"' % self.title,
            [('ใช้ชื่อนี้', 'use'), ('พิมพ์ชื่อเอง', 'type')],
            self.on_title_pick, self.on_cancel))

    def on_title_pick(self, value):
        self._pick = value
        ui.delay(self.do_title_pick, 0.3)

    @_guarded
    def do_title_pick(self):
        if self._pick == 'use':
            self.show_confirm()
        else:
            self.show_title_input(self.title)

    def show_title_input(self, initial):
        self.host.show_overlay(TextInputOverlay(
            'พิมพ์หรือพูดชื่อโน้ต', initial, self.on_title_text, self.on_cancel))

    def on_title_text(self, text):
        self._text = text
        ui.delay(self.do_title_text, 0.3)

    @_guarded
    def do_title_text(self):
        title = nt.clean_title(self._text)
        if not title:
            self.show_title_input('')
            return
        self.title = title
        self.show_confirm()

    # ----- 2ข: ต่อโน้ตเดิม เลือกจากรายการ -----
    def on_names(self, names):
        # ตรวจซ้ำที่ชั้น UI ด้วย เผื่อแหล่งรายชื่อหรือคลิปบอร์ดส่งค่า 0 ปะปนมา
        debug_log('notes list parsed: names=%d has_zero=%s' %
                  (len(names), any(str(name).strip() == '0' for name in names)))
        self.names = [str(name).strip() for name in names
                      if str(name).strip() and str(name).strip() != '0']
        ui.delay(self.do_names, 0.3)

    @_guarded
    def do_names(self):
        if not self.names:
            self.lines.append('ไม่พบโน้ตในโฟลเดอร์ "%s" (หรือไม่ได้กด Allow Paste) '
                              'ยังไม่ได้บันทึก "%s"' % (notes_shortcut.FOLDER_NAME, self.item['title']))
            self.step()
            return
        items = [(name, name) for name in self.names]
        self.host.show_overlay(ListPickOverlay(
            'เลือกโน้ตที่จะต่อท้าย (%d โน้ต)' % len(items), items,
            self.on_note_pick, self.on_cancel))

    def on_names_error(self, message):
        self._text = message
        ui.delay(self.do_names_error, 0.3)

    @_guarded
    def do_names_error(self):
        self.lines.append('%s ยังไม่ได้บันทึก "%s"' % (self._text, self.item['title']))
        self.step()

    def on_note_pick(self, value):
        debug_log('notes list callback: value_empty=%s value_is_zero=%s' %
                  (not bool(str(value or '').strip()),
                   str(value or '').strip() == '0'))
        self._pick = value
        ui.delay(self.do_note_pick, 0.3)

    @_guarded
    def do_note_pick(self):
        self.append_target_title = str(self._pick or '').strip()
        self.title = self.append_target_title
        debug_log('notes list selection: empty=%s is_zero=%s' %
                  (not bool(self.append_target_title), self.append_target_title == '0'))
        if not self.append_target_title:
            self.lines.append('ไม่ได้รับชื่อโน้ตจากรายการที่เลือก ยังไม่ได้ส่งคำสั่งต่อท้าย')
            self.step()
            return
        if str(self.title or '').strip() == '0':
            self.lines.append('รายชื่อโน้ตจาก Shortcut ไม่ถูกต้อง (ได้ค่า 0) ยังไม่ได้ส่งคำสั่งต่อท้าย')
            self.step()
            return
        warning = nt.conflict_text(self.title, self.names)
        debug_log('notes append target checked: conflict=%s' % bool(warning))
        if warning:  # ชื่อซ้ำ/ซ้อน: ไม่ส่ง กันต่อท้ายผิดโน้ต
            self.lines.append('ไม่ได้ส่ง: %s' % warning)
            self.step()
            return
        debug_log('notes append: opening timestamp choice')
        self.show_append_timestamp_choice()

    # ----- เลือกว่าจะใส่วันและเวลาในข้อความต่อท้ายหรือไม่ -----
    def show_append_timestamp_choice(self):
        self.host.show_overlay(ChoiceOverlay(
            'เพิ่มวันที่และเวลาปัจจุบันไหม?',
            [('เพิ่มวันที่และเวลา', 'with_timestamp'),
             ('ไม่เพิ่มวันที่และเวลา', 'without_timestamp')],
            self.on_append_timestamp_pick, self.on_cancel))

    def on_append_timestamp_pick(self, value):
        self._pick = value
        ui.delay(self.do_append_timestamp_pick, 0.3)

    @_guarded
    def do_append_timestamp_pick(self):
        self.append_timestamp = (datetime.datetime.now()
                                 if self._pick == 'with_timestamp' else None)
        # เก็บชื่อปลายทางแยกจาก _pick ซึ่งถูกใช้กับตัวเลือกวันเวลา
        if self.mode == 'append':
            self.title = self.append_target_title
        debug_log('notes after timestamp choice: title_empty=%s' %
                  (not bool(str(self.title or '').strip())))
        self.show_confirm()

    # ----- 3: ยืนยันสุดท้าย -----
    def _build_body(self):
        content = self.item['content']
        if self.mode == 'append':
            if self.append_timestamp is None:
                return content
            heading = nt.format_date_heading(self.append_timestamp.date())
            heading += self.append_timestamp.strftime(' %H:%M')
            return '%s\n%s' % (heading, content)
        return nt.build_body(self.mode, content, datetime.date.today())

    def show_confirm(self):
        if self.mode == 'append' and not str(self.title or '').strip():
            self.lines.append('ไม่มีชื่อโน้ตปลายทาง ยังไม่ได้ส่งคำสั่งต่อท้าย')
            self.step()
            return
        body = self._build_body()
        debug_log('notes confirmation: mode=%s title_empty=%s title_is_zero=%s' %
                  (self.mode, not bool(str(self.title or '').strip()),
                   str(self.title or '').strip() == '0'))
        warning = ('ไม่ได้ใช้เนื้อหาจาก AI (ไม่ตรงคำพูด) ใช้ข้อความที่คุณพูดตามเดิม'
                   if self.item['used_fallback'] else '')
        self.host.show_overlay(ConfirmOverlay(
            nt.confirm_title(self.mode),
            nt.format_confirm_body(self.mode, self.title, body, warning),
            self.on_ok, self.on_cancel, self.on_redo))

    def on_ok(self):
        ui.delay(self.do_ok, 0.3)

    @_guarded
    def do_ok(self):
        body = self._build_body()
        debug_log('notes send: mode=%s title_empty=%s title_is_zero=%s' %
                  (self.mode, not bool(str(self.title or '').strip()),
                   str(self.title or '').strip() == '0'))
        if DEBUG_FAKE_NAMES and self.mode == 'append':
            debug_log('notes send: skipped (DEBUG_FAKE_NAMES)')
            self.lines.append('(ทดลองรายชื่อสมมติ: ไม่ได้ส่งคำสั่งไปยัง Shortcut)')
            self.step()
            return
        try:
            notes_shortcut.send_save(self.mode, self.title, body)
        except notes_shortcut.NotesShortcutError as e:
            self.lines.append('ไม่ได้ส่งคำสั่ง: %s' % e)
        else:
            self.saved = True
            self.lines.append(nt.SENT_LINE)
        self.step()

    def on_cancel(self):
        ui.delay(self.do_cancel, 0.3)

    @_guarded
    def do_cancel(self):
        self.lines.append('ยกเลิก ไม่บันทึกโน้ต: "%s"' % self.title)
        self.skip_rest()
        self.finish()

    def on_redo(self):
        ui.delay(self.do_redo, 0.3)

    @_guarded
    def do_redo(self):
        self.lines.append('ยกเลิก ไม่บันทึกโน้ต: "%s" (ขอทำรายการใหม่)' % self.title)
        self.skip_rest()
        self.finish(redo=True)


def run_actions(host, actions, on_done):
    """รัน actions โดยเก็บ runner ไว้ที่ host ให้อยู่ได้นานพอ (เหมือน finance_flow)"""
    runner = NotesRunner(host, actions, on_done)
    host._action_runner = runner
    runner.start()
