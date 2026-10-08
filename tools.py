# tools.py
"""นิยามเครื่องมือ (tools) ที่ AI เรียกได้ และตัวตรวจค่าก่อนใช้งานจริง

ตามหลักการ handoff:
- ข้อ 1/8: AI แปลภาษาเท่านั้น เลือกเครื่องมือ+กรอกพารามิเตอร์ ไม่เขียนข้อมูลเอง
- ข้อ 5: โค้ดตรวจค่าที่ AI ส่งมาอีกชั้นก่อนใช้งานจริงเสมอ
- ข้อ 6: ส่งข้อความยืนยันที่แสดงวันที่ตีความแล้วชัดเจน
"""

import datetime

# ---- schema ที่ส่งให้ OpenRouter (รูปแบบ OpenAI function calling) ----

CREATE_REMINDER_SCHEMA = {
    'type': 'function',
    'function': {
        'name': 'create_reminder',
        'description': (
            'สร้างการเตือนความจำ/นัดหมายในแอป Reminders ของผู้ใช้ '
            'เรียกเมื่อผู้ใช้พูดถึงนัดหมาย งาน หรือสิ่งที่ต้องทำในอนาคต'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'title': {
                    'type': 'string',
                    'description': 'ชื่อเรื่องสั้น กระชับ บอกว่าต้องทำอะไร',
                },
                'due_date': {
                    'type': 'string',
                    'description': (
                        'วันเวลาที่ต้องทำ รูปแบบ YYYY-MM-DD HH:MM (24 ชม.) '
                        'ตีความจากวันที่ปัจจุบันที่ให้ไว้ใน system prompt เสมอ '
                        'เช่น "พุธนี้บ่ายโมง" ให้คำนวณเป็นวันที่จริง ห้ามเดาปีเอง'
                    ),
                },
                'notes': {
                    'type': 'string',
                    'description': 'รายละเอียดเพิ่มเติม ถ้ามี (ไม่บังคับ)',
                },
            },
            'required': ['title', 'due_date'],
        },
    },
}

ALL_TOOLS = [CREATE_REMINDER_SCHEMA]


class ToolValidationError(Exception):
    """ค่าที่ AI ส่งมาไม่ผ่านการตรวจสอบ ข้อความอธิบายเป็นภาษาไทยอ่านได้ตรง ๆ"""


def validate_create_reminder(arguments):
    """ตรวจค่าที่ AI ส่งมาสำหรับ create_reminder ก่อนนำไปสร้างจริง

    arguments: dict จาก AI ({'title':.., 'due_date':.., 'notes':..})
    คืนค่า: dict ที่ตรวจแล้ว {'title':.., 'due_date': datetime, 'notes':..}
    ถ้าไม่ผ่าน raise ToolValidationError
    """
    title = (arguments.get('title') or '').strip()
    if not title:
        raise ToolValidationError(
            'AI ไม่ได้ระบุชื่อเรื่อง กรุณาพูดอีกครั้งให้ชัดว่าจะเตือนเรื่องอะไร')

    due_date_str = (arguments.get('due_date') or '').strip()
    if not due_date_str:
        raise ToolValidationError(
            'AI ไม่ได้ระบุวันเวลา กรุณาบอกวันและเวลาที่ต้องการให้เตือน')

    due_date = None
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S'):
        try:
            due_date = datetime.datetime.strptime(due_date_str, fmt)
            break
        except ValueError:
            continue
    if due_date is None:
        raise ToolValidationError(
            'AI ส่งรูปแบบวันเวลามาไม่ถูกต้อง (%s) กรุณาลองพูดใหม่อีกครั้ง'
            % due_date_str)

    now = datetime.datetime.now()
    # กันกรณี AI ตีความวันที่ผิดจนกลายเป็นอดีต
    # (เช่น "พุธนี้" เมื่อวันนี้เป็นพุธแล้ว แต่ AI ดันถอยไปสัปดาห์ก่อน)
    if due_date < now - datetime.timedelta(minutes=5):
        raise ToolValidationError(
            'วันเวลาที่ตีความได้ (%s) เป็นเวลาที่ผ่านมาแล้ว '
            'กรุณายืนยันวันที่อีกครั้ง หรือพูดให้ชัดเจนขึ้น'
            % due_date.strftime('%a %d/%m/%Y %H:%M'))

    # กันกรณีตีความไกลผิดปกติ (เกิน 2 ปีข้างหน้า) น่าจะเป็นปีผิด
    if due_date > now + datetime.timedelta(days=730):
        raise ToolValidationError(
            'วันเวลาที่ตีความได้ (%s) ไกลผิดปกติ กรุณาตรวจสอบอีกครั้ง'
            % due_date.strftime('%d/%m/%Y'))

    notes = (arguments.get('notes') or '').strip() or None
    return {'title': title, 'due_date': due_date, 'notes': notes}


def format_confirm_text(validated):
    """สร้างข้อความสำหรับหน้ายืนยัน (ConfirmOverlay) ตามหลักการข้อ 6
    แสดงวันที่ภาษาไทยที่ตีความแล้วให้ชัดเจน
    """
    weekdays_th = ['จันทร์', 'อังคาร', 'พุธ', 'พฤหัสบดี', 'ศุกร์', 'เสาร์', 'อาทิตย์']
    months_th = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
                 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
    d = validated['due_date']
    date_text = '%s %d %s %d %02d:%02d' % (
        weekdays_th[d.weekday()], d.day, months_th[d.month], d.year,
        d.hour, d.minute)
    text = 'จะสร้างการเตือน: "%s"\nกำหนด: %s' % (validated['title'], date_text)
    if validated.get('notes'):
        text += '\nบันทึกเพิ่มเติม: %s' % validated['notes']
    return text