"""Recognize clear reminder-creation requests before AI can classify them as searches."""
# ===== BUILD MARKER =====
BUILD = "v28"
print(">>> reminder_create BUILD=%s file=%s" % (BUILD, __file__))

import datetime
import re

import wake_duration
from debug_log import log as debug_log


_CREATE = re.compile(
    r'(?:ช่วย\s*)?(?:ตั้ง\s*)?(?:เตือน|แจ้งเตือน)(?:ฉัน|ผม|เรา)?\s*'
    r'(?:ว่า|ให้(?:จำ)?(?:ว่า)?|เรื่อง)\s*(.+)$')
# รูปแบบที่คำว่า "เตือน" อยู่ท้ายหรือกลางประโยค เช่น "พรุ่งนี้เที่ยงช่วยเตือนฉันว่าไปกินข้าว"
_CREATE_FLEX = re.compile(
    r'(?:ช่วย\s*)?(?:ตั้ง\s*)?(?:เตือน|แจ้งเตือน)(?:ฉัน|ผม|เรา)?\s*'
    r'(?:ว่า|ให้(?:จำ)?(?:ว่า)?|เรื่อง)\s*(.+)')
_USE_MESSAGE = re.compile(
    r'(?:ช่วย\s*)?ใช้\s*(?:ข้อความ(?:แจ้งเตือน|เตือน)?|เนื้อหา)\s*ว่า\s*(.+)$')
_NEGATED = ('ไม่ต้องเตือน', 'ไม่ต้องช่วยเตือน', 'ไม่ต้องแจ้งเตือน', 'ยกเลิกเตือน')
_RELATIVE_NOW = re.compile(r'(?:ต่อจากเวลาในขณะนี้|ต่อจากเวลานี้|จากเวลานี้|'
                           r'นับจากตอนนี้|หลังจากเวลานี้|จากตอนนี้|'
                           r'ตอนนี้อีก|ต่อจากนี้|หลังจากนี้|ในขณะนี้)')
_TIME_TAIL = re.compile(
    r'\s*(?:ใน\s*)?(?:วันนี้|พรุ่งนี้|มะรืน(?:นี้)?|เมื่อคืนนี้|คืนนี้|เช้าวันนี้|'
    r'วันจันทร์|วันอังคาร|วันพุธ|วันพฤหัส(?:บดี)?|วันศุกร์|วันเสาร์|วันอาทิตย์|'
    r'\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[:.]\d{2}|'
    r'(?:ตอน)?(?:เที่ยงคืน|เที่ยง|บ่าย\s*\d{1,2}\s*โมง|'
    r'\d{1,2}\s*โมง(?:\s*(?:เช้า|สาย|บ่าย|เย็น|ค่ำ|กลางคืน))?|'
    r'\d{1,2}\s*ทุ่ม|ตี\s*\d{1,2})(?:ตรง)?).*$')

_NUMBER_WORDS = {
    'หนึ่ง': 1, 'เอ็ด': 1, 'สอง': 2, 'สาม': 3, 'สี่': 4,
    'ห้า': 5, 'หก': 6, 'เจ็ด': 7, 'แปด': 8, 'เก้า': 9, 'สิบ': 10,
}

_TIME_HINT = re.compile(
    r'(?:วันนี้|พรุ่งนี้|มะรืน(?:นี้)?|คืนนี้|เช้านี้|เย็นนี้|'
    r'วัน(?:จันทร์|อังคาร|พุธ|พฤหัส(?:บดี)?|ศุกร์|เสาร์|อาทิตย์)|'
    r'\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[:.]\d{2}|'
    r'เที่ยงคืน|เที่ยง|โมง|ทุ่ม|ตี\s*[\dก-๙]+)')


def has_create_intent(text):
    """True for an explicit create-reminder phrase, even if its details are incomplete."""
    raw = str(text or '')
    if any(phrase in raw for phrase in _NEGATED):
        return False
    return bool(_CREATE.search(raw) or _CREATE_FLEX.search(raw)
                or _USE_MESSAGE.search(raw))


def _number_value(value):
    return int(value) if value.isdigit() else _NUMBER_WORDS.get(value)


def _title_from(text):
    match = _USE_MESSAGE.search(text) or _CREATE.search(text) or _CREATE_FLEX.search(text)
    if not match:
        return None
    body = match.group(1).strip()
    # In phrases such as "เตือนฉันว่าวันนี้ตอนสามทุ่มครึ่งว่าสถานะ...",
    # the date/time appears between two clauses. Use the clause after the
    # second "ว่า" as the reminder title.
    clauses = body.split('ว่า')
    if len(clauses) > 1:
        for index in range(1, len(clauses)):
            prefix = 'ว่า'.join(clauses[:index])
            suffix = 'ว่า'.join(clauses[index:]).strip()
            if _TIME_HINT.search(prefix) and suffix:
                body = suffix
                break
    title = _TIME_TAIL.sub('', body).strip()
    title = re.sub(r'^(?:(?:ให้)?(?:เต็ม)?ว่า|ให้)\s*', '', title).strip(' ,.!?ฯ')
    # A relative duration is part of the due time, not part of the reminder title.
    title = _RELATIVE_NOW.split(title, maxsplit=1)[0].strip(' ,.!?ฯ')
    duration = wake_duration._duration_minutes(
        _RELATIVE_NOW.sub('ต่อจากนี้', text.translate(wake_duration._DIGITS)))
    if duration is not None:
        title = re.sub(r'(?:ต่อจากนี้|หลังจากนี้|ในอีก|อีก)\s*'
                       r'(?:\d+|[ก-๙]+)\s*(?:ชั่วโมง|ชม\.?|นาที)\s*$', '', title).strip()
    return title or None


def _relative_due(text, now=None):
    normalized = text.translate(wake_duration._DIGITS)
    normalized = _RELATIVE_NOW.sub('ต่อจากนี้', normalized)
    minutes = wake_duration._duration_minutes(normalized)
    if minutes is None:
        return None
    current = now or datetime.datetime.now()
    return (current + datetime.timedelta(minutes=minutes)).replace(
        second=0, microsecond=0)


def _parse_clock(normalized):
    """คืน (hour, minute, ambiguous_hour) หรือ (None, None, None) ถ้าไม่พบเวลา."""
    hour = minute = None
    ambiguous_hour = None

    match = re.search(r'(?<!\d)(\d{1,2})\s*[:.]\s*(\d{2})(?!\d)', normalized)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            return None, None, None
        return hour, minute, None

    if 'เที่ยงคืน' in normalized:
        return 0, 0, None
    if 'เที่ยง' in normalized:
        return 12, 0, None

    word_pattern = '|'.join(sorted(_NUMBER_WORDS, key=len, reverse=True))

    match = re.search(r'ตี\s*(\d{1,2}|%s)' % word_pattern, normalized)
    if match:
        hour = _number_value(match.group(1))
        if hour is None or not 1 <= hour <= 6:
            return None, None, None
        return hour, 0, None

    match = re.search(r'(\d{1,2}|%s)\s*ทุ่ม\s*(ครึ่ง)?' % word_pattern, normalized)
    if match:
        n = _number_value(match.group(1))
        if n is None or not 1 <= n <= 5:
            return None, None, None
        return 18 + n, (30 if match.group(2) else 0), None

    match = re.search(
        r'(?:บ่าย\s*)?(\d{1,2}|%s)\s*โมง\s*(เช้า|สาย|บ่าย|เย็น|ค่ำ|กลางคืน)?'
        % word_pattern, normalized)
    if match:
        n = _number_value(match.group(1))
        part = match.group(2)
        if part in ('เช้า', 'สาย'):
            hour = n
        elif part in ('เย็น', 'ค่ำ', 'กลางคืน'):
            hour = n + 12 if n is not None and n < 12 else n
        elif match.group(0).startswith('บ่าย') or 'บ่าย' in normalized[:match.start()]:
            hour = n + 12 if n is not None and n < 12 else n
        elif n == 12:
            hour = 12
        elif n is not None and 13 <= n <= 23:
            hour = n
        elif n is not None and 1 <= n <= 11:
            hour = n
            ambiguous_hour = n
        else:
            return None, None, None
        if hour is None or not 0 <= hour <= 23:
            return None, None, None
        return hour, 0, ambiguous_hour

    match = re.search(r'(%s)\s*(เช้า|สาย|เย็น|ค่ำ|กลางคืน)' % word_pattern, normalized)
    if match:
        n = _number_value(match.group(1))
        part = match.group(2)
        if part in ('เช้า', 'สาย'):
            hour = n
        else:
            hour = n + 12 if n is not None and n < 12 else n
        if hour is None:
            return None, None, None
        return hour, 0, None

    return None, None, None


def _parse_day(normalized, hour, minute, now=None):
    """คืน date object จากคำบอกวันในข้อความ."""
    current = now or datetime.datetime.now()
    today = current.date()

    if 'มะรืน' in normalized:
        return today + datetime.timedelta(days=2)
    if 'พรุ่งนี้' in normalized:
        return today + datetime.timedelta(days=1)
    if any(word in normalized for word in ('วันนี้', 'คืนนี้', 'เช้านี้', 'เย็นนี้')):
        return today

    date_match = re.search(r'\b(20\d{2})-(\d{1,2})-(\d{1,2})\b', normalized)
    if date_match:
        try:
            return datetime.date(*(int(part) for part in date_match.groups()))
        except ValueError:
            return None

    weekday_names = {
        'จันทร์': 0, 'อังคาร': 1, 'พุธ': 2, 'พฤหัส': 3,
        'ศุกร์': 4, 'เสาร์': 5, 'อาทิตย์': 6,
    }
    target = next((wd for name, wd in weekday_names.items() if name in normalized), None)
    if target is not None:
        offset = (target - today.weekday()) % 7
        if offset == 0 and hour is not None:
            proposed = datetime.datetime.combine(today, datetime.time(hour, minute or 0))
            if proposed <= current:
                offset = 7
        return today + datetime.timedelta(days=offset)

    # ไม่บอกวัน: ใช้วันนี้ถ้าเวลายังไม่ผ่าน ไม่งั้นพรุ่งนี้
    if hour is not None:
        proposed = datetime.datetime.combine(today, datetime.time(hour, minute or 0))
        if proposed > current:
            return today
        return today + datetime.timedelta(days=1)
    return None


def _absolute_due(text, now=None):
    """แปลงวัน+เวลาแบบสัมบูรณ์ (พรุ่งนี้เที่ยง, 14:30 ฯลฯ) เป็น datetime."""
    normalized = str(text or '').translate(str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789'))
    hour, minute, ambiguous = _parse_clock(normalized)
    if hour is None:
        return None

    current = now or datetime.datetime.now()
    today = current.date()

    if ambiguous is not None:
        has_day = (
            any(w in normalized for w in (
                'มะรืน', 'พรุ่งนี้', 'วันนี้', 'คืนนี้', 'เช้านี้', 'เย็นนี้'))
            or re.search(r'\b20\d{2}-\d{1,2}-\d{1,2}\b', normalized)
            or any(w in normalized for w in (
                'จันทร์', 'อังคาร', 'พุธ', 'พฤหัส', 'ศุกร์', 'เสาร์', 'อาทิตย์')))
        if has_day:
            # มีวันแล้วแต่ไม่บอกเช้า/บ่าย → ยังกำกวม ปล่อยให้ AI/guided flow ถาม
            return None
        for h in (ambiguous, ambiguous + 12):
            if datetime.datetime.combine(today, datetime.time(h, 0)) > current:
                hour = h
                break
        else:
            hour = ambiguous

    day = _parse_day(normalized, hour, minute, current)
    if day is None:
        return None
    return datetime.datetime.combine(day, datetime.time(hour, minute or 0))


def parse_request(text, now=None):
    """Return a create_reminder tool call for an explicit reminder request.

    รองรับประโยคเช่น:
      - วันพรุ่งนี้เวลาเที่ยงช่วยเตือนฉันว่าไปกินข้าว
      - ใช้ข้อความเตือนว่า กินข้าวได้แล้ว พรุ่งนี้เวลาเที่ยง
      - เตือนฉันว่าประชุม วันจันทร์ 10:00
    """
    raw = str(text or '').strip()
    if not raw:
        debug_log('reminder_create BUILD=%s empty_input' % BUILD)
        return None
    if any(phrase in raw for phrase in _NEGATED):
        debug_log('reminder_create BUILD=%s rejected=negated' % BUILD)
        return None
    intent = has_create_intent(raw)
    if not intent:
        debug_log('reminder_create BUILD=%s intent=False' % BUILD)
        return None

    title = _title_from(raw)
    if not title:
        debug_log('reminder_create BUILD=%s intent=True title=False' % BUILD)
        return None

    due = _relative_due(raw, now)
    relative_found = due is not None
    if due is None:
        due = _absolute_due(raw, now)
    debug_log('reminder_create BUILD=%s intent=True title=True relative=%s absolute=%s'
              % (BUILD, relative_found, due is not None))
    if due is None:
        # มี intent สร้างชัดเจนแต่ยังไม่มีวัน/เวลาครบ → ไม่ส่งไป list/search
        # คืน None เพื่อให้ flow ถัดไป (guided / AI) ถามช่องที่ขาด
        return None

    return {
        'id': None,
        'name': 'create_reminder',
        'arguments': {
            'title': title,
            'due_date': due.strftime('%Y-%m-%d %H:%M'),
            'urgent_alarm': False,
        },
    }
