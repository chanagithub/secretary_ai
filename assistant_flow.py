"""assistant_flow.py - ลำดับงานของเลขา AI (เฟส 1: เตือนความจำ)
ย้ายลอจิกที่ทดสอบแล้วจาก test_ai_tools.py มาใช้กับหน้าจอจริง โดยเปลี่ยนการพิมพ์
ตอบเป็นปุ่มกด:
 1. ก่อนส่ง : date_guard ตรวจชื่อวันที่ตรงกับวันนี้ -> ป๊อปอัปเลือก "วันนี้ /
สัปดาห์หน้า"
 2. คุยกับ AI : ask_ai() (streaming + tool calling)
 3. หลังตอบ : prepare_actions() ตรวจค่าที่ AI ส่งมา -> run_actions() ขึ้น
ป๊อปอัปยืนยัน
 ตกลง / ไม่เอา / ทำรายการใหม่ แล้วบันทึกลง Reminders จริง
เมื่อกด "ตกลง"
ไฟล์นี้ไม่ผูกกับหน้าจอหลักโดยตรง: ใช้ host.show_overlay(overlay) เพื่อแสดงป๊อปอัป
เท่านั้น
"""
import ui
import ai_client
import date_guard
import reminders_tool
import tools
from overlays import ConfirmOverlay
from debug_log import log as debug_log

# ---------- 1) ความกำกวมของชื่อวัน ----------
def find_ambiguous_weekday(text):
    """คืน info ถ้าต้องถามผู้ใช้ก่อน ไม่งั้นคืน None"""
    return date_guard.find_ambiguous_weekday(text)

def weekday_choice(info):
    """คืน (หัวข้อ, [(ข้อความปุ่ม, ค่า), ...]) สำหรับ ChoiceOverlay"""
    title = 'วันนี้เป็น%s (%s)\nที่พูดถึงหมายถึงวันไหน' % (
        info['name'], date_guard.short_date(info['today']))
    options = [
        ('วันนี้ (%s)' % date_guard.short_date(info['today']), 'today'),
        ('%sหน้า (%s)' % (info['name'], date_guard.short_date(info['next_week'])),
         'next'),
    ]
    return title, options

def apply_choice(text, info, choice):
    """เติมวันที่จริงต่อท้ายคำสั่งก่อนส่งให้ AI"""
    return text + date_guard.clarify_text(info, choice)

# ---------- 2) คุยกับ AI ----------
def ask_ai(sent_text, on_chunk, token, model, history):
    """คืน (text, tool_calls) ถ้ามีปัญหาจะ raise ai_client.AIError"""
    return ai_client.stream_chat_with_tools(
        sent_text, on_chunk, token, tools.ALL_TOOLS,
        model=model, history=history)

# ---------- 3) ตรวจค่า + ยืนยัน + บันทึก ----------
def prepare_actions(tool_calls):
    """ตรวจค่าที่ AI ส่งมาทีละคำสั่ง (ข้อ 5: โค้ดตรวจซ้ำอีกชั้น)
    คืน list ของ
    {'kind': 'note', 'text': ...} = ข้อความแจ้ง (ไม่ต้องยืนยัน)
    {'kind': 'confirm', 'validated': ..., 'body': ...} = รอผู้ใช้กดยืนยัน
    """
    actions = []
    for call in tool_calls:
        if call['name'] != 'create_reminder':
            actions.append({'kind': 'note',
                             'text': '(AI เรียกเครื่องมือที่ไม่รู้จัก: %s ข้ามไป)'
                             % call['name']})
            continue
        try:
            validated = tools.validate_create_reminder(call['arguments'])
        except tools.ToolValidationError as e:
            actions.append({'kind': 'note', 'text': 'ตรวจค่าไม่ผ่าน: %s' % e})
            continue
        actions.append({'kind': 'confirm', 'validated': validated,
                         'body': tools.format_confirm_text(validated)})
    return actions

def _save(validated):
    debug_log('flow: _save start title=%s' % validated.get('title'))
    reminders_tool.create_reminder(
        title=validated['title'],
        due_date=validated['due_date'],
        notes=validated['notes'])
    debug_log('flow: _save done')

class _ActionRunner:
    """เก็บ state ของงานและส่ง bound methods ให้ ui.delay/ปุ่ม"""

    def __init__(self, host, actions, on_done):
        self.host = host
        self.queue = list(actions)
        self.lines = []
        self.saved = False
        self.on_done = on_done
        self.finished = False

    def start(self):
        debug_log('flow: run_actions start, %d action(s)' % len(self.queue))
        self.step()

    def finish(self, redo=False):
        if self.finished:
            return
        self.finished = True
        debug_log('flow: finish redo=%s saved=%s' % (redo, self.saved))
        if getattr(self.host, '_action_runner', None) is self:
            self.host._action_runner = None
        self.on_done(list(self.lines), redo, self.saved)

    def step(self):
        if self.finished:
            return
        if not self.queue:
            debug_log('flow: step - queue empty, calling finish')
            self.finish()
            return

        action = self.queue.pop(0)
        if action['kind'] == 'note':
            self.lines.append(action['text'])
            self.step()
            return

        validated = action['validated']
        self.current_validated = validated
        debug_log('flow: showing ConfirmOverlay title=%s' % validated.get('title'))
        self.host.show_overlay(ConfirmOverlay(
            'บันทึกการเตือนนี้ไหม?', action['body'],
            self.on_ok, self.on_cancel, self.on_redo))

    def on_ok(self):
        debug_log('flow: on_ok button pressed')
        ui.delay(self.do_ok, 0.3)

    def do_ok(self):
        if self.finished:
            return
        debug_log('flow: do_ok running (after delay)')
        # validated action is the item immediately before the next queue item;
        # keep it on the runner when the confirmation is shown.
        validated = self.current_validated
        try:
            _save(validated)
        except Exception as e:
            debug_log('flow: save failed: %s' % e)
            self.lines.append('บันทึกไม่สำเร็จ: %s' % e)
        else:
            self.saved = True
            self.lines.append('บันทึกการเตือนแล้ว: "%s" (ดูในแอป Reminders ลิสต์ "เลขา AI")'
                              % validated['title'])
        debug_log('flow: do_ok calling step()')
        self.step()

    def on_cancel(self):
        debug_log('flow: on_cancel button pressed')
        ui.delay(self.do_cancel, 0.3)

    def do_cancel(self):
        if self.finished:
            return
        debug_log('flow: do_cancel running (after delay)')
        self.lines.append('ยกเลิก ไม่บันทึก: "%s"' % self.current_validated['title'])
        debug_log('flow: do_cancel calling step()')
        self.step()

    def on_redo(self):
        debug_log('flow: on_redo button pressed')
        ui.delay(self.do_redo, 0.3)

    def do_redo(self):
        if self.finished:
            return
        debug_log('flow: do_redo running (after delay)')
        self.lines.append('ยกเลิก ไม่บันทึก: "%s" (ขอทำรายการใหม่)'
                          % self.current_validated['title'])
        debug_log('flow: do_redo calling finish(redo=True)')
        self.finish(redo=True)


def run_actions(host, actions, on_done):
    """รัน actions โดยเก็บ callback/state ไว้ใน object ที่อยู่ได้นานพอ"""
    runner = _ActionRunner(host, actions, on_done)
    host._action_runner = runner
    runner.start()
