"""Recognize clear reminder-creation requests before AI can classify them as searches."""
import datetime
import re

import assistant_flow
import wake_duration


_CREATE = re.compile(
    r'(?:ช่วย\s*)?(?:ตั้ง\s*)?(?:เตือน|แจ้งเตือน)(?:ฉัน|ผม|เรา)?\s*'
    r'(?:ว่า|ให้(?:จำ)?(?:ว่า)?|เรื่อง)\s*(.+)$')
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


def _title_from(text):
    match = _USE_MESSAGE.search(text) or _CREATE.search(text)
    if not match:
        return None
    title = _TIME_TAIL.sub('', match.group(1)).strip()
    title = re.sub(r'^(?:ให้|ว่า)\s*', '', title).strip(' ,.!?ฯ')
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


def parse_request(text, now=None):
    """Return a create_reminder tool call for an explicit reminder request."""
    raw = str(text or '').strip()
    if any(phrase in raw for phrase in _NEGATED):
        return None
    if not (_CREATE.search(raw) or _USE_MESSAGE.search(raw)):
        return None
    title = _title_from(raw)
    if not title:
        return None

    due = _relative_due(raw, now)
    if due is None:
        # Reuse the app's date/time parser for absolute dates and clock phrases.
        parsed = assistant_flow._local_wake_alarm_action('ตั้งปลุก ' + raw)
        if not parsed or parsed.get('kind') != 'tool':
            return None
        due_text = parsed['call']['arguments']['due_date']
    else:
        due_text = due.strftime('%Y-%m-%d %H:%M')

    return {'id': None, 'name': 'create_reminder',
            'arguments': {'title': title, 'due_date': due_text,
                          'urgent_alarm': False}}
