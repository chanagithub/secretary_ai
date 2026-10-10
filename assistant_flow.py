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
import ast
import datetime
import ui
import re
import ai_client
import date_guard
import reminders_tool
import reminder_search
import tools
from overlays import ConfirmOverlay, ChoiceOverlay, NoTimeConfirmOverlay
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


def local_reminder_action(text, turns, snapshot):
    """จัดการคำสั่งสั้นที่ตามหลังคำถามหมายเลข โดยไม่ให้โมเดลตีความซ้ำ"""
    words = {'หนึ่ง': 1, 'ที่หนึ่ง': 1, 'แรก': 1, 'สอง': 2, 'ที่สอง': 2,
             'สาม': 3, 'ที่สาม': 3, 'สี่': 4, 'ที่สี่': 4, 'ห้า': 5,
             'ที่ห้า': 5, 'หก': 6, 'เจ็ด': 7, 'แปด': 8, 'เก้า': 9, 'สิบ': 10}
    number = None
    match = re.search(r'(?:ข้อ|รายการที่|รายการ)\s*(\d+|หนึ่ง|ที่หนึ่ง|แรก|สอง|ที่สอง|สาม|ที่สาม|สี่|ที่สี่|ห้า|ที่ห้า|หก|เจ็ด|แปด|เก้า|สิบ)', text)
    if match:
        value = match.group(1)
        number = int(value) if value.isdigit() else words[value]
    elif text.strip() in ('หนึ่ง', 'ข้อหนึ่ง', 'ที่หนึ่ง', 'ข้อ 1', '1'):
        number = 1
    if number is None or number < 1 or number > len(snapshot):
        return None

    context = text
    for turn in reversed(turns):
        prior = str(turn.get('user') or '')
        if any(word in prior for word in ('เลื่อน', 'เปลี่ยนเวลา', 'เปลี่ยนวัน', 'นัดใหม่', 'ทำเครื่องหมาย', 'ยกเลิก', 'ลบทิ้ง', 'ลบข้อ')):
            context = prior + ' ' + context
            break
    item = snapshot[number - 1]
    args = {'number': number}
    if any(word in context for word in ('เลื่อน', 'เปลี่ยนเวลา', 'เปลี่ยนวัน', 'นัดใหม่')):
        tm = re.search(r'(?<!\d)(\d{1,2})[.:](\d{2})(?!\d)', context)
        if tm:
            args['new_time'] = '%02d:%02d' % (int(tm.group(1)), int(tm.group(2)))
        else:
            thai_times = {'บ่ายโมง': '13:00', 'บ่ายหนึ่ง': '13:00', 'บ่ายสอง': '14:00',
                          'บ่ายสาม': '15:00', 'บ่ายสี่': '16:00', 'ห้าโมงเย็น': '17:00',
                          'หกโมงเย็น': '18:00', 'หนึ่งทุ่ม': '19:00', 'สองทุ่ม': '20:00'}
            for phrase, value in thai_times.items():
                if phrase in context:
                    args['new_time'] = value
                    break
        day = re.search(r'\b(20\d{2}-\d{2}-\d{2})\b', context)
        if day:
            args['new_date'] = day.group(1)
        try:
            validated = tools.validate_reschedule(args, snapshot)
        except tools.ToolValidationError as e:
            return {'kind': 'note', 'text': str(e)}
        return {'kind': 'reschedule', 'validated': validated}
    if any(word in context for word in ('ลบทิ้ง', 'ลบข้อ', 'ลบรายการ')):
        return {'kind': 'delete_reminder', 'item': item}
    if any(word in context for word in ('เสร็จ', 'ยกเลิก', 'ทำเครื่องหมาย')):
        return {'kind': 'complete_reminder', 'item': item}
    return None


def local_list_action(text, turns=None):
    """แปลงคำขอดูรายการรายวัน/รายเดือนด้วยโค้ด เพื่อกัน AI แปลงเดือนหรือปีผิด"""
    lower = text.lower()
    list_words = ('ลิสต์', 'รายการ', 'ต้องทำ', 'ทำอะไร', 'เตือน', 'งาน', 'reminder')
    month_words = ('มกราคม', 'ม.ค.', 'กุมภาพันธ์', 'ก.พ.', 'มีนาคม', 'มี.ค.', 'เมษายน', 'เม.ย.',
                   'พฤษภาคม', 'พ.ค.', 'มิถุนายน', 'มิ.ย.', 'กรกฎาคม', 'ก.ค.', 'สิงหาคม', 'ส.ค.',
                   'กันยายน', 'ก.ย.', 'ตุลาคม', 'ต.ค.', 'พฤศจิกายน', 'พ.ย.', 'ธันวาคม', 'ธ.ค.')
    weekday_words = ('จันทร์', 'อังคาร', 'พุธ', 'พฤหัส', 'ศุกร์', 'เสาร์', 'อาทิตย์')
    relative_period_words = ('เดือนนี้', 'เดือนหน้า', 'เดือนถัดไป', 'เดือนที่แล้ว', 'เดือนก่อน', 'เดือนที่ผ่าน')
    has_period = any(word in text for word in relative_period_words) or any(word in text for word in month_words) or any(word in text for word in weekday_words) or any(word in text for word in ('วันนี้', 'พรุ่งนี้', 'มะรืน'))
    has_list_request = any(word in lower for word in list_words)
    has_mutation_request = any(word in text for word in ('เลื่อน', 'เปลี่ยนเวลา', 'เปลี่ยนวัน', 'ยกเลิก', 'ลบทิ้ง', 'ลบข้อ'))
    if not has_list_request:
        prior_list_request = any(
            any(word in str(turn.get('user') or '').lower() for word in list_words)
            for turn in (turns or [])[-6:])
        if not (has_period and prior_list_request) or has_mutation_request:
            return None
    completed = any(word in lower for word in ('เสร็จ', 'ทำแล้ว', 'completed', 'ยกเลิก', 'ทำอะไรมาบ้าง', 'ทำอะไรไปบ้าง'))
    status = 'completed' if completed else ('all' if 'ทั้งหมด' in lower else 'incomplete')
    if not any(word in lower for word in ('เสร็จ', 'ทำแล้ว', 'completed', 'ยกเลิก', 'ทำอะไรมาบ้าง', 'ทำอะไรไปบ้าง', 'ทั้งหมด')):
        for turn in reversed(turns or []):
            prior = str(turn.get('user') or '').lower()
            if any(word in prior for word in list_words):
                if any(word in prior for word in ('เสร็จ', 'ทำแล้ว', 'completed', 'ยกเลิก', 'ทำอะไรมาบ้าง', 'ทำอะไรไปบ้าง')):
                    status = 'completed'
                elif 'ทั้งหมด' in prior:
                    status = 'all'
                break
    now = datetime.date.today()
    if 'เดือนนี้' in text or 'เดือนนี้' in lower:
        month = '%04d-%02d' % (now.year, now.month)
    elif 'เดือนหน้า' in text or 'เดือนถัดไป' in text:
        next_month = (now.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        month = '%04d-%02d' % (next_month.year, next_month.month)
    elif any(phrase in text for phrase in ('เดือนที่แล้ว', 'เดือนก่อน', 'เดือนที่ผ่าน')):
        prev_month = now.replace(day=1) - datetime.timedelta(days=1)
        month = '%04d-%02d' % (prev_month.year, prev_month.month)
    else:
        month_names = {
            'มกราคม': 1, 'ม.ค.': 1, 'ม.ค': 1,
            'กุมภาพันธ์': 2, 'ก.พ.': 2, 'ก.พ': 2,
            'มีนาคม': 3, 'มี.ค.': 3, 'มี.ค': 3,
            'เมษายน': 4, 'เม.ย.': 4, 'เม.ย': 4,
            'พฤษภาคม': 5, 'พ.ค.': 5, 'พ.ค': 5,
            'มิถุนายน': 6, 'มิ.ย.': 6, 'มิ.ย': 6,
            'กรกฎาคม': 7, 'ก.ค.': 7, 'ก.ค': 7,
            'สิงหาคม': 8, 'ส.ค.': 8, 'ส.ค': 8,
            'กันยายน': 9, 'ก.ย.': 9, 'ก.ย': 9,
            'ตุลาคม': 10, 'ต.ค.': 10, 'ต.ค': 10,
            'พฤศจิกายน': 11, 'พ.ย.': 11, 'พ.ย': 11,
            'ธันวาคม': 12, 'ธ.ค.': 12, 'ธ.ค': 12,
        }
        month_number = None
        for name in sorted(month_names, key=len, reverse=True):
            if name in text:
                month_number = month_names[name]
                after = text.split(name, 1)[1]
                year_match = re.search(r'\b(\d{4})\b', after)
                year = int(year_match.group(1)) if year_match else now.year
                if year >= 2400:
                    year -= 543
                month = '%04d-%02d' % (year, month_number)
                break
        else:
            month = None
    if any(phrase in text for phrase in relative_period_words) or month is not None:
        try:
            period = tools.validate_list_reminders({'month': month, 'status': status})
        except tools.ToolValidationError as e:
            return {'kind': 'note', 'text': str(e)}
        return {'kind': 'list', 'period': period}
    if any(word in text for word in ('วันนี้', 'พรุ่งนี้', 'มะรืน')):
        day = now
        if 'พรุ่งนี้' in text:
            day += datetime.timedelta(days=1)
        elif 'มะรืน' in text:
            day += datetime.timedelta(days=2)
        try:
            period = tools.validate_list_reminders({'date': day.strftime('%Y-%m-%d'), 'status': status})
        except tools.ToolValidationError as e:
            return {'kind': 'note', 'text': str(e)}
        return {'kind': 'list', 'period': period}
    weekdays = {'จันทร์': 0, 'อังคาร': 1, 'พุธ': 2, 'พฤหัส': 3,
                'ศุกร์': 4, 'เสาร์': 5, 'อาทิตย์': 6}
    for name, target in weekdays.items():
        if name in text:
            offset = (target - now.weekday()) % 7
            if offset == 0 and any(word in text for word in ('ที่จะถึง', 'หน้า', 'ถัดไป')):
                offset = 7
            day = now + datetime.timedelta(days=offset)
            try:
                period = tools.validate_list_reminders({'date': day.strftime('%Y-%m-%d'), 'status': status})
            except tools.ToolValidationError as e:
                return {'kind': 'note', 'text': str(e)}
            return {'kind': 'list', 'period': period}
    return None

# ---------- 2) คุยกับ AI ----------
_TOOL_NAMES = ('create_reminder', 'list_reminders', 'search_reminders',
               'reschedule_reminder', 'complete_reminder', 'delete_reminder')
_PSEUDO_FALLBACK = 'ขออภัยครับ ประมวลผลคำสั่งนี้ไม่สำเร็จ ลองพิมพ์ใหม่อีกครั้ง'


def _recover_pseudo_call(text):
    """โมเดลเล็กบางครั้งพิมพ์ tool call เป็นโค้ด เช่น print(default_api.list_reminders(...))
    แปลงกลับเป็น tool call จริง (ไม่รันโค้ด แค่อ่านค่าด้วย ast) แล้วให้ระบบตรวจค่าตามปกติ"""
    for name in _TOOL_NAMES:
        start = text.find(name + '(')
        if start < 0:
            continue
        for end in range(min(len(text), start + 600), start + len(name) + 1, -1):
            try:
                node = ast.parse(text[start:end], mode='eval').body
            except (SyntaxError, ValueError):
                continue
            if not isinstance(node, ast.Call):
                break
            try:
                args = {k.arg: ast.literal_eval(k.value) for k in node.keywords if k.arg}
            except ValueError:
                break
            return {'id': None, 'name': name, 'arguments': args}
    return None


_DATE_MARKERS = (
    'วันนี้', 'พรุ่งนี้', 'มะรืน', 'เมื่อวาน', 'คืนนี้', 'พรุ่งนี้', 'สัปดาห์หน้า',
    'เดือนหน้า', 'เดือนที่แล้ว', 'ปีหน้า', 'ปีที่แล้ว', 'วันจันทร์', 'วันอังคาร',
    'วันพุธ', 'วันพฤหัส', 'วันศุกร์', 'วันเสาร์', 'วันอาทิตย์', 'จันทร์หน้า',
    'อังคารหน้า', 'พุธหน้า', 'พฤหัสหน้', 'ศุกร์หน้า', 'เสาร์หน้า', 'อาทิตย์หน้า',
    'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน', 'กรกฎาคม',
    'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม', 'ม.ค.', 'ก.พ.',
    'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.',
)


def _has_explicit_date(text):
    if re.search(r'\b20\d{2}-\d{1,2}-\d{1,2}\b|\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b', text):
        return True
    if re.search(r'วันที่\s*\d{1,2}', text):
        return True
    return any(word in text for word in _DATE_MARKERS)


def _has_explicit_time(text):
    return bool(re.search(r'(?<!\d)\d{1,2}(?:[:.]\d{2})(?!\d)', text)
                or any(word in text for word in (
                    'โมง', 'ทุ่ม', 'ตี', 'เที่ยง', 'บ่าย', 'เช้า', 'เย็น', 'ค่ำ')))


def _correct_date_omitted_create(text, calls):
    """เวลาที่ระบุโดยไม่มีวันให้เป็นวันนี้ถ้ายังไม่ผ่าน; ถ้าผ่านแล้วถาม ไม่เลื่อนไปพรุ่งนี้เอง"""
    if _has_explicit_date(text) or not _has_explicit_time(text):
        return None
    for call in calls or []:
        if call.get('name') != 'create_reminder':
            continue
        args = call.get('arguments') or {}
        raw = str(args.get('due_date') or '').strip()
        due = None
        for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S'):
            try:
                due = datetime.datetime.strptime(raw, fmt)
                break
            except ValueError:
                pass
        if due is None:
            continue
        now = datetime.datetime.now()
        due_today = now.replace(hour=due.hour, minute=due.minute, second=0, microsecond=0)
        if due_today <= now:
            return 'เวลาที่ระบุวันนี้ผ่านไปแล้วครับ หมายถึงวันนี้หรือพรุ่งนี้ครับ?'
        args['due_date'] = due_today.strftime('%Y-%m-%d %H:%M')
    return None


def _local_wake_alarm_action(text):
    """จับคำสั่งปลุกที่ชัดเจนเอง เพื่อไม่ให้โมเดลเปลี่ยนเป็นคำสั่งค้นรายการ"""
    if not any(word in text.lower() for word in ('ปลุก', 'นาฬิกาปลุก', 'alarm')):
        return None
    if any(phrase in text for phrase in ('ไม่ต้องปลุก', 'ไม่ต้องตั้งปลุก', 'ยกเลิกปลุก')):
        return None

    normalized = text.translate(str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789'))
    number_words = {'หนึ่ง': 1, 'เอ็ด': 1, 'สอง': 2, 'สาม': 3, 'สี่': 4,
                    'ห้า': 5, 'หก': 6, 'เจ็ด': 7, 'แปด': 8, 'เก้า': 9, 'สิบ': 10}

    def number_value(value):
        return int(value) if value.isdigit() else number_words.get(value)

    hour = minute = None
    match = re.search(r'(?<!\d)(\d{1,2})\s*[:.]\s*(\d{2})(?!\d)', normalized)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            return {'kind': 'note', 'text': 'เวลาไม่ถูกต้องครับ กรุณาบอกเวลาอีกครั้ง'}
    elif 'เที่ยงคืน' in normalized:
        hour, minute = 0, 0
    elif 'เที่ยง' in normalized:
        hour, minute = 12, 0
    else:
        word_pattern = '|'.join(sorted(number_words, key=len, reverse=True))
        match = re.search(r'ตี\s*(\d{1,2}|%s)' % word_pattern, normalized)
        if match:
            hour, minute = number_value(match.group(1)), 0
            if hour is None or not 1 <= hour <= 6:
                return {'kind': 'note', 'text': 'เวลาตีต้องอยู่ระหว่างตี 1 ถึงตี 6 ครับ'}
        else:
            match = re.search(r'(\d{1,2}|%s)\s*ทุ่ม' % word_pattern, normalized)
            if match:
                n = number_value(match.group(1))
                if not 1 <= n <= 5:
                    return {'kind': 'note', 'text': 'เวลาไม่ถูกต้องครับ กรุณาบอกเวลาอีกครั้ง'}
                hour, minute = 18 + n, 0
            else:
                match = re.search(r'(?:บ่าย\s*)?(\d{1,2}|%s)\s*โมง\s*(เช้า|สาย|บ่าย|เย็น|ค่ำ|กลางคืน)?' % word_pattern, normalized)
                if match:
                    n = number_value(match.group(1))
                    part = match.group(2)
                    if part == 'บ่าย':
                        # เผื่อรูปแบบ "บ่าย 2 โมง"
                        pass
                    if part in ('เช้า', 'สาย'):
                        hour = n
                    elif part in ('เย็น', 'ค่ำ', 'กลางคืน'):
                        hour = n if n >= 6 else n + 12
                    elif 'บ่าย' in normalized[:match.start()]:
                        hour = n + 12 if n < 12 else n
                    elif n == 12:
                        hour = 12
                    else:
                        return {'kind': 'note', 'text': 'หมายถึงกี่โมงครับ เช่น 6 โมงเช้า หรือ 6 โมงเย็น'}
                    if not 0 <= hour <= 23:
                        return {'kind': 'note', 'text': 'เวลาไม่ถูกต้องครับ กรุณาบอกเวลาอีกครั้ง'}
                    minute = 0
                else:
                    # รองรับภาษาพูดที่ละคำว่า "โมง" เช่น "หกโมงเช้า" และ "เจ็ดโมงเช้า"
                    match = re.search(r'(%s)\s*(เช้า|สาย|เย็น|ค่ำ|กลางคืน)' % word_pattern, normalized)
                    if match:
                        n = number_value(match.group(1))
                        part = match.group(2)
                        if part in ('เช้า', 'สาย'):
                            hour = n
                        else:
                            hour = n if n >= 6 else n + 12
                        minute = 0

    if hour is None:
        return {'kind': 'note', 'text': 'จะให้ปลุกกี่โมงครับ'}

    today = datetime.date.today()
    if 'มะรืน' in normalized:
        day = today + datetime.timedelta(days=2)
    elif 'พรุ่งนี้' in normalized:
        day = today + datetime.timedelta(days=1)
    elif any(word in normalized for word in ('วันนี้', 'คืนนี้', 'เช้านี้', 'เย็นนี้')):
        day = today
    else:
        date_match = re.search(r'\b(20\d{2})-(\d{1,2})-(\d{1,2})\b', normalized)
        if date_match:
            try:
                day = datetime.date(*(int(part) for part in date_match.groups()))
            except ValueError:
                return {'kind': 'note', 'text': 'วันที่ไม่ถูกต้องครับ กรุณาบอกวันอีกครั้ง'}
        else:
            weekday_names = {'จันทร์': 0, 'อังคาร': 1, 'พุธ': 2, 'พฤหัส': 3,
                             'ศุกร์': 4, 'เสาร์': 5, 'อาทิตย์': 6}
            target = next((weekday for name, weekday in weekday_names.items()
                           if name in normalized), None)
            if target is None:
                return {'kind': 'note', 'text': 'จะให้ปลุกวันไหนครับ เช่น พรุ่งนี้'}
            offset = (target - today.weekday()) % 7
            if offset == 0 and hour is not None:
                proposed = datetime.datetime.combine(today, datetime.time(hour, minute))
                if proposed <= datetime.datetime.now():
                    offset = 7
            day = today + datetime.timedelta(days=offset)

    due = datetime.datetime.combine(day, datetime.time(hour, minute))
    args = {'title': 'ปลุกผม', 'due_date': due.strftime('%Y-%m-%d %H:%M'),
            'urgent_alarm': True}
    return {'kind': 'tool', 'call': {'id': None, 'name': 'create_reminder',
                                    'arguments': args}}


def ask_ai(sent_text, on_chunk, token, model, history):
    """คืน (text, tool_calls) ถ้ามีปัญหาจะ raise ai_client.AIError"""
    # คำถามค้นนัดและคำตอบต่อ ให้โค้ดตัดสินเอง ไม่พึ่งการเลือกเครื่องมือของโมเดลเล็ก
    turns = [{'user': str(m.get('content') or '')}
             for m in (history or []) if m.get('role') == 'user']
    wake = _local_wake_alarm_action(sent_text)
    if wake:
        if wake['kind'] == 'note':
            return '', [{'id': None, 'name': '_note',
                         'local_note': wake['text'], 'arguments': {}}]
        return '', [wake['call']]
    local = reminder_search.local_search_action(sent_text, turns)
    if local:
        return '', [{'id': None, 'name': 'search_reminders',
                     'arguments': {'topics': local['topics'],
                                   'keywords': local['keywords'],
                                   'when': local['when']}}]
    text, calls = ai_client.stream_chat_with_tools(
        sent_text, on_chunk, token,
        tools.ALL_TOOLS + [reminder_search.search_schema()],
        model=model, history=history)
    if not calls and text and ('default_api' in text
                               or any(n + '(' in text for n in _TOOL_NAMES)):
        recovered = _recover_pseudo_call(text)
        debug_log('flow: pseudo tool-call text, recovered=%s' % bool(recovered))
        if recovered:
            question = _correct_date_omitted_create(sent_text, [recovered])
            if question:
                on_chunk(question)
                return question, []
            return '', [recovered]
        # app_ui ใช้ข้อความที่สะสมจาก on_chunk เมื่อไม่มี tool call จึงส่งเป็น "ข้อความแจ้ง" แทน
        return '', [{'id': None, 'name': '_note', 'local_note': _PSEUDO_FALLBACK,
                     'arguments': {}}]
    question = _correct_date_omitted_create(sent_text, calls)
    if question:
        on_chunk(question)
        return question, []
    return text, calls

# ---------- 3) ตรวจค่า + ยืนยัน + บันทึก ----------
def prepare_actions(tool_calls, host=None):
    """ตรวจค่าที่ AI ส่งมาทีละคำสั่ง (ข้อ 5: โค้ดตรวจซ้ำอีกชั้น)
    คืน list ของ
    {'kind': 'note', 'text': ...} = ข้อความแจ้ง (ไม่ต้องยืนยัน)
    {'kind': 'confirm', 'validated': ..., 'body': ...} = รอผู้ใช้กดยืนยัน
    """
    actions = []
    for call in tool_calls:
        if call.get('local_note'):  # ข้อความแจ้งจากโค้ดเอง (ai_client ไม่เคยสร้างคีย์นี้)
            actions.append({'kind': 'note', 'text': call['local_note']})
            continue
        name = call['name']
        args = call['arguments']
        if name == 'list_reminders':
            try:
                actions.append({'kind': 'list', 'period': tools.validate_list_reminders(args)})
            except tools.ToolValidationError as e:
                actions.append({'kind': 'note', 'text': 'ตรวจค่าไม่ผ่าน: %s' % e})
            continue
        if name == 'search_reminders':
            try:
                actions.append(reminder_search.validate_search(args))
            except tools.ToolValidationError as e:
                actions.append({'kind': 'note', 'text': 'ตรวจค่าไม่ผ่าน: %s' % e})
            continue
        if name in ('reschedule_reminder', 'complete_reminder', 'delete_reminder'):
            snapshot = getattr(host, '_reminder_snapshot', []) if host else []
            try:
                item = tools.validate_reminder_number(args, snapshot)
                if name == 'reschedule_reminder':
                    validated = tools.validate_reschedule(args, snapshot)
                    actions.append({'kind': 'reschedule', 'validated': validated})
                else:
                    actions.append({'kind': name, 'item': item})
            except tools.ToolValidationError as e:
                actions.append({'kind': 'note', 'text': str(e)})
            continue
        if name != 'create_reminder':
            actions.append({'kind': 'note',
                             'text': '(AI เรียกเครื่องมือที่ไม่รู้จัก: %s ข้ามไป)'
                             % call['name']})
            continue
        try:
            validated = tools.validate_create_reminder(args)
        except tools.ToolValidationError as e:
            actions.append({'kind': 'note', 'text': 'ตรวจค่าไม่ผ่าน: %s' % e})
            continue
        actions.append({'kind': 'confirm', 'validated': validated,
                         'body': tools.format_confirm_text(validated)})
    return actions

def _save(validated):
    debug_log('flow: _save start title=%s' % validated.get('title'))
    result = reminders_tool.create_reminder(
        title=validated['title'],
        due_date=validated['due_date'],
        notes=validated['notes'],
        has_time=validated.get('has_time', True),
        urgent_alarm=validated.get('urgent_alarm', False))
    debug_log('flow: _save done')
    return result

class _ActionRunner:
    """เก็บ state ของงานและส่ง bound methods ให้ ui.delay/ปุ่ม"""

    def __init__(self, host, actions, on_done):
        self.host = host
        self.queue = list(actions)
        self.lines = []
        self.saved = False
        self.on_done = on_done
        self.finished = False
        self.current_validated = None
        self.current_body = ''
        self._time_value = None

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
        if action['kind'] == 'list':
            self.show_list(action['period'])
            return
        if action['kind'] == 'search':
            self.show_search(action)
            return
        if action['kind'] in ('reschedule', 'complete_reminder', 'delete_reminder'):
            self.current_action = action
            self.show_mutation_confirm(action)
            return
        if action['kind'] == 'note':
            self.lines.append(action['text'])
            self.step()
            return

        validated = action['validated']
        self.current_validated = validated
        self.current_body = action['body']
        if validated.get('has_time', True):
            self.show_confirm()
        else:
            self.show_time_choice()

    def show_search(self, action):
        """ค้นด้วยข้อความจากทุกลิสต์ (อ่านอย่างเดียว ไม่มีป๊อปอัป ไม่มีปุ่มแก้/ลบ)"""
        debug_log('flow: search keywords=%s' % ','.join(action['keywords'][:4]))
        # หมายเลขในผลค้นไม่ตรงกับ snapshot เดิม ล้างทิ้งเพื่อกันสั่งเลื่อน/ลบผิดรายการ
        self.host._reminder_snapshot = []
        self.lines.append(reminder_search.run_search(action))
        self.step()

    def show_list(self, period):
        try:
            rows = reminders_tool.list_reminders_between(
                period['start'], period['end'], period['status'])
        except Exception as e:
            self.lines.append('อ่านรายการเตือนไม่สำเร็จ: %s' % e)
            self.step()
            return
        snapshot = []
        for due, reminder in rows:
            snapshot.append({'due': due, 'reminder': reminder,
                             'title': reminder.title})
        self.host._reminder_snapshot = snapshot
        status_text = {'incomplete': 'ที่ยังไม่เสร็จ', 'completed': 'ที่เสร็จแล้ว', 'all': 'ทั้งหมด'}[period['status']]
        if not snapshot:
            self.lines.append('ไม่มีรายการเตือน%sในช่วง %s' % (status_text, period['label']))
        else:
            lines = ['รายการเตือน%s ช่วง %s:' % (status_text, period['label'])]
            for i, item in enumerate(snapshot, 1):
                clock = 'ไม่ระบุเวลา' if item['due'].hour == 0 and item['due'].minute == 0 else item['due'].strftime('%H:%M')
                date_part = item['due'].strftime('%d/%m/%Y ') if period.get('monthly') else ''
                lines.append('%d. %s%s — %s' % (i, date_part, clock, item['title']))
            lines.append('เลือกหมายเลขเพื่อเลื่อนนัด ทำเครื่องหมายว่าเสร็จ/ยกเลิก หรือลบทิ้งได้')
            self.lines.append('\n'.join(lines))
        self.step()

    def show_mutation_confirm(self, action):
        if action['kind'] == 'reschedule':
            data = action['validated']; item = data['item']
            body = 'เลื่อน "%s"\nจาก %s\nเป็น %s ใช่ไหม?' % (
                item['title'], item['due'].strftime('%d/%m/%Y %H:%M'),
                data['new_due'].strftime('%d/%m/%Y %H:%M'))
            title = 'ยืนยันการเลื่อนนัด'
        else:
            item = action['item']
            if action['kind'] == 'complete_reminder':
                title = 'ทำเครื่องหมายว่าเสร็จ/ยกเลิก?'
                body = '"%s"\nรายการจะย้ายไปหมวดเสร็จแล้ว และกู้คืนได้' % item['title']
            else:
                title = 'ยืนยันการลบถาวร'
                body = 'ลบ "%s" ออกจาก Reminders ถาวรไหม?\nกู้คืนไม่ได้' % item['title']
        self.host.show_overlay(ConfirmOverlay(title, body,
            self.on_mutation_ok, self.on_mutation_cancel, self.on_redo))

    def on_mutation_ok(self):
        ui.delay(self.do_mutation_ok, 0.3)

    def do_mutation_ok(self):
        action = self.current_action
        item = action.get('item') or action['validated']['item']
        try:
            if action['kind'] == 'reschedule':
                reminders_tool.reschedule_reminder(item['reminder'], action['validated']['new_due'])
                self.lines.append('เลื่อน "%s" เป็น %s แล้ว' % (item['title'], action['validated']['new_due'].strftime('%d/%m/%Y %H:%M')))
            elif action['kind'] == 'complete_reminder':
                reminders_tool.mark_done(item['reminder'])
                self.lines.append('ทำเครื่องหมายว่าเสร็จ/ยกเลิกแล้ว: "%s"' % item['title'])
            else:
                reminders_tool.delete_reminder(item['reminder'])
                self.lines.append('ลบถาวรแล้ว: "%s"' % item['title'])
            refresh_day = action['validated']['new_due'].date() if action['kind'] == 'reschedule' else item['due'].date()
            refreshed = reminders_tool.list_reminders_on(refresh_day)
            self.host._reminder_snapshot = [
                {'due': due, 'reminder': reminder, 'title': reminder.title}
                for due, reminder in refreshed]
            if refreshed:
                lines = ['รายการที่เหลือวันที่ %s:' % tools.format_day_text(refresh_day)]
                for i, (due, reminder) in enumerate(refreshed, 1):
                    clock = 'ไม่ระบุเวลา' if due.hour == 0 and due.minute == 0 else due.strftime('%H:%M')
                    lines.append('%d. %s — %s' % (i, clock, reminder.title))
                self.lines.append('\n'.join(lines))
            else:
                self.lines.append('วันที่ %s ไม่มีรายการค้างแล้ว' % tools.format_day_text(refresh_day))
        except Exception as e:
            self.lines.append('ทำรายการไม่สำเร็จ: %s' % e)
        self.step()

    def on_mutation_cancel(self):
        ui.delay(self.do_mutation_cancel, 0.3)

    def do_mutation_cancel(self):
        self.lines.append('ยกเลิกรายการ ไม่ได้เปลี่ยนแปลง Reminder')
        self.step()

    def show_confirm(self):
        debug_log('flow: showing ConfirmOverlay title=%s'
                  % self.current_validated.get('title'))
        self.host.show_overlay(ConfirmOverlay(
            'บันทึกการเตือนนี้ไหม?', self.current_body,
            self.on_ok, self.on_cancel, self.on_redo))

    # ----- ผู้ใช้ไม่ได้บอกเวลา: ป๊อปอัปเดียว ตกลง(ไม่ระบุเวลา) / ระบุเวลา / ไม่เอา / ทำรายการใหม่ -----
    def show_time_choice(self):
        debug_log('flow: showing NoTimeConfirmOverlay title=%s'
                  % self.current_validated.get('title'))
        self.host.show_overlay(NoTimeConfirmOverlay(
            'ยังไม่ได้ระบุเวลา บันทึกแบบไม่ระบุเวลาไหม?', self.current_body,
            self.on_ok, self.on_set_time, self.on_cancel, self.on_redo))

    def on_set_time(self):
        debug_log('flow: on_set_time button pressed')
        ui.delay(self.do_set_time, 0.3)

    def do_set_time(self):
        if self.finished:
            return
        debug_log('flow: do_set_time running')
        # ระบุเวลา: จบรอบนี้ (ยังไม่บันทึก) ให้ผู้ใช้บอกเวลาในข้อความถัดไป
        # host._keep_context = True ทำให้รอบนี้ยังเป็นความจำของแชท AI จึงรู้ว่าเป็นงานไหน
        self.lines.append('ยังไม่ได้บันทึก "%s": บอกเวลาที่ต้องการได้เลยครับ (เช่น บ่ายสอง)'
                          % self.current_validated['title'])
        self.host._keep_context = True
        self.finish()

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
            save_result = _save(validated)
        except Exception as e:
            debug_log('flow: save failed: %s' % e)
            self.lines.append('บันทึกไม่สำเร็จ: %s' % e)
        else:
            if save_result == 'shortcut':
                # การเปิด URL ไม่ได้ยืนยันว่า Shortcut สร้าง Reminder สำเร็จ
                self.lines.append('ส่งคำสั่งไปยัง Shortcut แล้ว แต่ยังยืนยันการสร้างไม่ได้: "%s" กรุณาตรวจในแอป Reminders'
                                  % validated['title'])
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
