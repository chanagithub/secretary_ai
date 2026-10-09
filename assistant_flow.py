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

def run_actions(host, actions, on_done):
    """ไล่ทำทีละรายการ แต่ละรายการที่ต้องยืนยันจะขึ้นป๊อปอัปปุ่มกด
    host = view ที่มี show_overlay(overlay)
    on_done(lines, redo, saved) เรียกเมื่อจบทั้งหมด
    lines = ข้อความผลลัพธ์แต่ละรายการ, redo = ผู้ใช้กด "ทำรายการใหม่"
(ข้ามรายการที่เหลือ),
    saved = มีการบันทึกลง Reminders สำเร็จอย่างน้อยหนึ่งรายการ
    """
    debug_log('flow: run_actions start, %d action(s)' % len(actions))
    queue = list(actions)
    lines = []
    state = {'saved': False}

    def finish(redo=False):
        debug_log('flow: finish redo=%s saved=%s' % (redo, state['saved']))
        finished_lines = list(lines)
        saved = state['saved']

        def notify_done():
            debug_log('flow: calling on_done (delayed)')
            on_done(finished_lines, redo, saved)

        ui.delay(notify_done, 0.2)

    def step():
        if not queue:
            debug_log('flow: step - queue empty, calling finish')
            finish()
            return
        action = queue.pop(0)
        if action['kind'] == 'note':
            lines.append(action['text'])
            step()
            return

        validated = action['validated']

        def on_ok():
            debug_log('flow: on_ok button pressed')

            def do_ok():
                debug_log('flow: do_ok running (after delay)')
                try:
                    _save(validated)
                except Exception as e:
                    debug_log('flow: save failed: %s' % e)
                    lines.append('บันทึกไม่สำเร็จ: %s' % e)
                else:
                    state['saved'] = True
                    lines.append('บันทึกการเตือนแล้ว: "%s" (ดูในแอป Reminders '
                                  'ลิสต์ "เลขา AI")' % validated['title'])
                debug_log('flow: do_ok calling step()')
                step()

            ui.delay(do_ok, 0.3)

        def on_cancel():
            debug_log('flow: on_cancel button pressed')

            def do_cancel():
                debug_log('flow: do_cancel running (after delay)')
                lines.append('ยกเลิก ไม่บันทึก: "%s"' % validated['title'])
                debug_log('flow: do_cancel calling step()')
                step()

            ui.delay(do_cancel, 0.3)

        def on_redo():
            debug_log('flow: on_redo button pressed')

            def do_redo():
                debug_log('flow: do_redo running (after delay)')
                lines.append('ยกเลิก ไม่บันทึก: "%s" (ขอทำรายการใหม่)'
                              % validated['title'])
                debug_log('flow: do_redo calling finish(redo=True)')
                finish(redo=True)

            ui.delay(do_redo, 0.3)

        debug_log('flow: showing ConfirmOverlay title=%s' % validated.get('title'))
        host.show_overlay(ConfirmOverlay(
            'บันทึกการเตือนนี้ไหม?', action['body'], on_ok, on_cancel, on_redo))

    step()