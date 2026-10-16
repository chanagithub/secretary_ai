"""Parse explicit relative-time urgent alarm requests before sending them to AI.

Keeps the requested reminder text verbatim and calculates the due time on-device.
"""
import datetime
import re


_ALARM_WORDS = ('ปลุก', 'นาฬิกาปลุก', 'alarm')
_NEGATED_WORDS = ('ไม่ต้องปลุก', 'ไม่ต้องตั้งปลุก', 'ยกเลิกปลุก')
_DIGITS = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')
_NUMBERS = {
    'หนึ่ง': 1, 'เอ็ด': 1, 'สอง': 2, 'สาม': 3, 'สี่': 4, 'ห้า': 5,
    'หก': 6, 'เจ็ด': 7, 'แปด': 8, 'เก้า': 9, 'สิบ': 10,
    'สิบเอ็ด': 11, 'สิบสอง': 12, 'สิบสาม': 13, 'สิบสี่': 14,
    'สิบห้า': 15, 'สิบหก': 16, 'สิบเจ็ด': 17, 'สิบแปด': 18,
    'สิบเก้า': 19, 'ยี่สิบ': 20, 'สามสิบ': 30, 'สี่สิบ': 40,
    'ห้าสิบ': 50, 'หกสิบ': 60, 'เจ็ดสิบ': 70, 'แปดสิบ': 80,
    'เก้าสิบ': 90, 'ครึ่ง': 0.5,
}
_NUM_TOKEN = r'(?:%s|\d+)' % '|'.join(
    re.escape(word) for word in sorted(_NUMBERS, key=len, reverse=True))
_DURATION = (r'(?:(?P<hours>%s)\s*(?:ชั่วโมง|ชม\.?))?\s*'
             r'(?:(?P<minutes>%s)\s*นาที)?') % (_NUM_TOKEN, _NUM_TOKEN)
_PREFIX = r'(?:หลังจากนี้|ต่อจากนี้(?:ไป)?|จากนี้(?:ไป)?|ใน(?:อีก)?|อีก|ภายใน)\s*(?:อีก\s*)?'


def _number(token):
    if token is None:
        return 0
    token = token.translate(_DIGITS)
    if token.isdigit():
        return int(token)
    return _NUMBERS.get(token, 0)


def _duration_minutes(text):
    patterns = (
        _PREFIX + _DURATION,
        _DURATION + r'\s*(?:จากนี้|ข้างหน้า|ต่อจากนี้)',
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match or not (match.group('hours') or match.group('minutes')):
            continue
        hours = _number(match.group('hours'))
        minutes = _number(match.group('minutes'))
        total = int(hours * 60 + minutes)
        if 0 < total <= 365 * 24 * 60:
            return total
    return None


def _requested_title(text):
    # รองรับการระบุชื่อรายการโดยตรง เช่น “ตั้งรายการว่า กินข้าวได้แล้ว ตั้งเป็นการปลุกหลังจากนี้ 30 นาที”
    explicit = re.search(
        r'(?:(?:ตั้งรายการ|ตั้งชื่อ|ชื่อรายการ)\s*(?:ว่า|เป็น)|ตั้งว่า)\s*(.+)$', text)
    if explicit:
        title = explicit.group(1).strip()
    else:
        match = re.search(
            r'(?:ใช้\s*)?(?:ข้อความแจ้งเตือน|ข้อความเตือน|ข้อความ|เนื้อหา)\s*ว่า\s*(.+)$',
            text)
        if not match:
            return 'AI ช่วยปลุกครับ'
        title = match.group(1).strip()
    # ตัดคำสั่งให้ใช้เป็นการปลุกออกจากชื่อรายการ
    title = re.split(
        r'(?:ตั้งเป็นการปลุก|ตั้งการปลุก|ตั้งปลุก|'
        r'ทำเป็น(?:เป็น)?การปลุก(?:ด้วย)?|เป็นการปลุก(?:ด้วย)?|'
        r'ปลุก(?:ฉัน|ผม|เรา)?\s*(?:หลังจากนี้|ต่อจากนี้|ในอีก|อีก|ภายใน))',
        title, maxsplit=1)[0].strip()
    # ตัดช่วงเวลาสัมพัทธ์ เช่น “หลังจากนี้ 1 ชั่วโมง” ออกจากชื่อ
    duration_tail = re.search(
        r'\s*(?:หลังจากนี้|ต่อจากนี้(?:ไป)?|จากนี้(?:ไป)?|ในอีก|อีก|ภายใน)\s*'
        r'(?:อีก\s*)?(?:%s)\s*(?:ชั่วโมง|ชม\.?|นาที)' % _NUM_TOKEN,
        title)
    if duration_tail:
        title = title[:duration_tail.start()].strip()
    # ตัดคำเชื่อมที่ผู้ใช้พูดก่อนตัวข้อความ เช่น “ใช้ข้อความว่าเตือนว่า กินข้าวได้แล้ว”
    title = re.sub(r'^(?:เตือน|แจ้งเตือน|เต็ม)\s*ว่า\s*', '', title).strip()
    return title or 'AI ช่วยปลุกครับ'


def parse_relative_wake(text, now=None):
    """Return a create_reminder tool call for a clear alarm plus relative duration."""
    raw = str(text or '')
    normalized = raw.translate(_DIGITS)
    lower = normalized.lower()
    if not any(word in lower for word in _ALARM_WORDS):
        return None
    if any(phrase in lower for phrase in _NEGATED_WORDS):
        return None
    minutes = _duration_minutes(normalized)
    if minutes is None:
        return None
    current = now or datetime.datetime.now()
    due = (current + datetime.timedelta(minutes=minutes)).replace(second=0, microsecond=0)
    arguments = {
        'title': _requested_title(normalized),
        'due_date': due.strftime('%Y-%m-%d %H:%M'),
        'urgent_alarm': True,
    }
    return {'id': None, 'name': 'create_reminder', 'arguments': arguments}
