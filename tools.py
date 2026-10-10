# tools.py
"""นิยามเครื่องมือ (tools) ที่ AI เรียกได้ และตัวตรวจค่าก่อนใช้งานจริง

ตามหลักการ handoff:
- ข้อ 1/8: AI แปลภาษาเท่านั้น เลือกเครื่องมือ+กรอกพารามิเตอร์ ไม่เขียนข้อมูลเอง
- ข้อ 5: โค้ดตรวจค่าที่ AI ส่งมาอีกชั้นก่อนใช้งานจริงเสมอ
- ข้อ 6: ส่งข้อความยืนยันที่แสดงวันที่ตีความแล้วชัดเจน
"""

import datetime
import re

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
                        'ถ้าผู้ใช้ไม่ได้บอกเวลา ให้ใส่เฉพาะวัน YYYY-MM-DD (ห้ามเดาเวลา) '
                        'ตีความจากวันที่ปัจจุบันที่ให้ไว้ใน system prompt เสมอ '
                        'เช่น "พุธนี้บ่ายโมง" ให้คำนวณเป็นวันที่จริง ห้ามเดาปีเอง'
                    ),
                },
                'notes': {
                    'type': 'string',
                    'description': 'รายละเอียดเพิ่มเติม ถ้ามี (ไม่บังคับ)',
                },
                'urgent_alarm': {
                    'type': 'boolean',
                    'description': (
                        'ตั้งเป็นเสียงปลุกยาวแบบนาฬิกา เฉพาะเมื่อผู้ใช้สั่งให้ปลุกโดยตรง '
                        'เช่น "ช่วยปลุกผมตอน 7 โมงเช้า" หรือ "ตั้งปลุก"; '
                        'ถ้าเป็นนัดหมาย/งาน/เตือนทั่วไป ให้ false เสมอ'
                    ),
                },
            },
            'required': ['title', 'due_date'],
        },
    },
}

LIST_REMINDERS_SCHEMA = {
    'type': 'function',
    'function': {
        'name': 'list_reminders',
        'description': (
            'ดูรายการเตือนจากทุกลิสต์ใน Reminders ตามวันที่หรือเดือน และสถานะ '
            'เรียกเมื่อผู้ใช้ถามว่าวันนี้/พรุ่งนี้/เดือนใดมีงานหรือนัดอะไรบ้าง'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'date': {
                    'type': 'string',
                    'description': (
                        'วันที่ที่ต้องการดู รูปแบบ YYYY-MM-DD '
                        'ตีความจากปฏิทินใน system prompt เสมอ เช่น "พรุ่งนี้" ให้แปลงเป็นวันที่จริง'
                    ),
                },
                'month': {
                    'type': 'string',
                    'description': 'เดือนที่ต้องการดู รูปแบบ YYYY-MM ใช้เมื่อผู้ใช้ขอรายการทั้งเดือน',
                },
                'status': {
                    'type': 'string',
                    'enum': ['incomplete', 'completed', 'all'],
                    'description': 'สถานะรายการ: ยังไม่เสร็จ, เสร็จแล้ว หรือทั้งหมด',
                },
            },
            'required': [],
        },
    },
}

RESCHEDULE_REMINDER_SCHEMA = {
    'type': 'function', 'function': {
        'name': 'reschedule_reminder',
        'description': 'เลื่อนวันหรือเวลาของรายการที่แสดงในลิสต์ล่าสุด โดยอ้างอิงหมายเลขรายการ',
        'parameters': {'type': 'object', 'properties': {
            'number': {'type': 'integer', 'description': 'หมายเลขรายการจากลิสต์ล่าสุด'},
            'new_date': {'type': 'string', 'description': 'วันใหม่ YYYY-MM-DD (ไม่บังคับ)'},
            'new_time': {'type': 'string', 'description': 'เวลาใหม่ HH:MM (ไม่บังคับ)'},
        }, 'required': ['number']}
    }
}
COMPLETE_REMINDER_SCHEMA = {
    'type': 'function', 'function': {
        'name': 'complete_reminder',
        'description': 'ทำเครื่องหมายรายการจากลิสต์ล่าสุดว่าเสร็จหรือยกเลิกแล้ว (กู้คืนได้)',
        'parameters': {'type': 'object', 'properties': {
            'number': {'type': 'integer', 'description': 'หมายเลขรายการจากลิสต์ล่าสุด'}
        }, 'required': ['number']}
    }
}
DELETE_REMINDER_SCHEMA = {
    'type': 'function', 'function': {
        'name': 'delete_reminder',
        'description': 'ลบรายการจากลิสต์ล่าสุดอย่างถาวร ต้องยืนยันก่อนลบ',
        'parameters': {'type': 'object', 'properties': {
            'number': {'type': 'integer', 'description': 'หมายเลขรายการจากลิสต์ล่าสุด'}
        }, 'required': ['number']}
    }
}

ALL_TOOLS = [CREATE_REMINDER_SCHEMA, LIST_REMINDERS_SCHEMA,
             RESCHEDULE_REMINDER_SCHEMA, COMPLETE_REMINDER_SCHEMA,
             DELETE_REMINDER_SCHEMA]


class ToolValidationError(Exception):
    """ค่าที่ AI ส่งมาไม่ผ่านการตรวจสอบ ข้อความอธิบายเป็นภาษาไทยอ่านได้ตรง ๆ"""


def validate_create_reminder(arguments):
    """ตรวจค่าที่ AI ส่งมาสำหรับ create_reminder ก่อนนำไปสร้างจริง

    arguments: dict จาก AI ({'title':.., 'due_date':.., 'notes':..})
    คืนค่า: dict ที่ตรวจแล้ว มี urgent_alarm=True เฉพาะค่าบูลีน True ที่ AI ส่งมา
    due_date เป็น 'YYYY-MM-DD' (ไม่มีเวลา) ได้ -> has_time=False และ due_date เป็นเที่ยงคืนของวันนั้น
    ถ้าไม่ผ่าน raise ToolValidationError
    """
    title = (arguments.get('title') or '').strip()
    if not title:
        raise ToolValidationError(
            'AI ไม่ได้ระบุชื่อเรื่อง กรุณาพูดอีกครั้งให้ชัดว่าจะเตือนเรื่องอะไร')

    due_date_str = (arguments.get('due_date') or '').strip()
    if not due_date_str:
        raise ToolValidationError(
            'AI ไม่ได้ระบุวัน กรุณาบอกวันที่ต้องการให้เตือน')

    due_date = None
    has_time = True
    if re.match(r'^\d{4}-\d{2}-\d{2}$', due_date_str):  # มีแต่วัน ไม่มีเวลา
        try:
            due_date = datetime.datetime.strptime(due_date_str, '%Y-%m-%d')
            has_time = False
        except ValueError:
            pass
    if due_date is None:
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
    if has_time:
        too_old = due_date < now - datetime.timedelta(minutes=5)
    else:  # ไม่มีเวลา: วันนี้ยังใช้ได้ ผิดเฉพาะวันที่ผ่านไปแล้ว
        too_old = due_date.date() < now.date()
    if too_old:
        raise ToolValidationError(
            'วันเวลาที่ตีความได้ (%s) เป็นเวลาที่ผ่านมาแล้ว '
            'กรุณายืนยันวันที่อีกครั้ง หรือพูดให้ชัดเจนขึ้น'
            % due_date.strftime('%a %d/%m/%Y %H:%M' if has_time else '%a %d/%m/%Y'))

    # กันกรณีตีความไกลผิดปกติ (เกิน 2 ปีข้างหน้า) น่าจะเป็นปีผิด
    if due_date > now + datetime.timedelta(days=730):
        raise ToolValidationError(
            'วันเวลาที่ตีความได้ (%s) ไกลผิดปกติ กรุณาตรวจสอบอีกครั้ง'
            % due_date.strftime('%d/%m/%Y'))

    notes = (arguments.get('notes') or '').strip() or None
    return {'title': title, 'due_date': due_date, 'notes': notes,
            'has_time': has_time,
            'urgent_alarm': arguments.get('urgent_alarm') is True}


def format_confirm_text(validated):
    """สร้างข้อความสำหรับหน้ายืนยัน (ConfirmOverlay) ตามหลักการข้อ 6
    แสดงวันที่ภาษาไทยที่ตีความแล้วให้ชัดเจน
    """
    weekdays_th = ['จันทร์', 'อังคาร', 'พุธ', 'พฤหัสบดี', 'ศุกร์', 'เสาร์', 'อาทิตย์']
    months_th = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
                 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
    d = validated['due_date']
    date_text = '%s %d %s %d' % (
        weekdays_th[d.weekday()], d.day, months_th[d.month], d.year)
    if validated.get('has_time', True):
        date_text += ' %02d:%02d' % (d.hour, d.minute)
    else:
        date_text += ' (ไม่ระบุเวลา)'
    text = 'จะสร้างการเตือน: "%s"\nกำหนด: %s' % (validated['title'], date_text)
    if validated.get('urgent_alarm'):
        text += '\nชนิด: ปลุกด้วยเสียงฉุกเฉิน (Urgent)'
    if validated.get('notes'):
        text += '\nบันทึกเพิ่มเติม: %s' % validated['notes']
    return text

_WEEKDAYS_TH = ['จันทร์', 'อังคาร', 'พุธ', 'พฤหัสบดี', 'ศุกร์', 'เสาร์', 'อาทิตย์']
_MONTHS_TH = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
              'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']


def validate_list_reminders(arguments):
    """ตรวจช่วงวันที่และสถานะสำหรับ list_reminders"""
    month_text = (arguments.get('month') or '').strip()
    status = (arguments.get('status') or 'incomplete').strip().lower()
    if status not in ('incomplete', 'completed', 'all'):
        raise ToolValidationError('สถานะรายการไม่ถูกต้อง')
    if month_text:
        try:
            year, month = [int(part) for part in month_text.split('-', 1)]
            if year >= 2400:  # AI อาจส่งปี พ.ศ. มา แม้ system prompt ระบุ ค.ศ.
                year -= 543
            start = datetime.date(year, month, 1)
        except ValueError:
            raise ToolValidationError('เดือนต้องอยู่ในรูปแบบ YYYY-MM')
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        if abs((start - datetime.date.today().replace(day=1)).days) > 730:
            raise ToolValidationError('เดือนที่ขออยู่ไกลจากปัจจุบันเกินไป กรุณาตรวจสอบปี')
        month_names = ['', 'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
                       'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']
        return {'start': start, 'end': end, 'status': status,
                'label': '%s %d' % (month_names[start.month], start.year), 'monthly': True}

    text = (arguments.get('date') or '').strip()
    if not text:
        raise ToolValidationError('AI ไม่ได้ระบุวันที่ที่ต้องการดู กรุณาบอกว่าจะดูงานของวันไหน')
    try:
        day = datetime.datetime.strptime(text[:10], '%Y-%m-%d').date()
    except ValueError:
        raise ToolValidationError(
            'AI ส่งรูปแบบวันที่มาไม่ถูกต้อง (%s) กรุณาลองพูดใหม่อีกครั้ง' % text)
    today = datetime.date.today()
    if abs((day - today).days) > 730:
        raise ToolValidationError(
            'วันที่ที่ตีความได้ (%s) ห่างจากวันนี้ผิดปกติ กรุณาตรวจสอบอีกครั้ง'
            % day.strftime('%d/%m/%Y'))
    return {'start': day, 'end': day + datetime.timedelta(days=1),
            'status': status, 'label': format_day_text(day), 'monthly': False}


def format_day_text(day):
    """วันที่ภาษาไทยสั้น ๆ เช่น 'ศุกร์ 9 ต.ค. 2026'"""
    return '%s %d %s %d' % (_WEEKDAYS_TH[day.weekday()], day.day,
                            _MONTHS_TH[day.month], day.year)


def validate_reminder_number(arguments, snapshot):
    try:
        number = int(arguments.get('number'))
    except (TypeError, ValueError):
        raise ToolValidationError('ไม่พบหมายเลขรายการที่ถูกต้อง กรุณาแสดงรายการเตือนก่อน')
    if number < 1 or number > len(snapshot):
        raise ToolValidationError('หมายเลขรายการไม่อยู่ในลิสต์ล่าสุด กรุณาแสดงรายการเตือนใหม่')
    return snapshot[number - 1]


def validate_reschedule(arguments, snapshot):
    item = validate_reminder_number(arguments, snapshot)
    old_due = item['due']
    date_text = (arguments.get('new_date') or '').strip()
    time_text = (arguments.get('new_time') or '').strip()
    if not date_text and not time_text:
        raise ToolValidationError('กรุณาระบุวันใหม่หรือเวลาใหม่')
    day = old_due.date()
    if date_text:
        try:
            day = datetime.datetime.strptime(date_text, '%Y-%m-%d').date()
        except ValueError:
            raise ToolValidationError('วันใหม่ต้องอยู่ในรูปแบบ YYYY-MM-DD')
    if time_text:
        try:
            t = datetime.datetime.strptime(time_text, '%H:%M').time()
        except ValueError:
            raise ToolValidationError('เวลาใหม่ต้องอยู่ในรูปแบบ HH:MM เช่น 15:30')
        due = datetime.datetime.combine(day, t)
    else:
        due = datetime.datetime.combine(day, old_due.time())
    now = datetime.datetime.now()
    if due < now - datetime.timedelta(minutes=5):
        raise ToolValidationError('วันเวลาใหม่ผ่านไปแล้ว กรุณาระบุเวลาในอนาคต')
    if due > now + datetime.timedelta(days=730):
        raise ToolValidationError('วันเวลาใหม่ไกลเกินไป กรุณาตรวจสอบอีกครั้ง')
    return {'item': item, 'new_due': due}
