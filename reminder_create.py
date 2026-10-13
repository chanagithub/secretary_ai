"""Recognize clear reminder-creation requests before the AI can classify them as searches."""
import re

import assistant_flow


_CREATE = re.compile(
    r'(?:ช่วย\s*)?(?:ตั้ง\s*)?(?:เตือน|แจ้งเตือน)(?:ฉัน|ผม|เรา)?\s*'
    r'(?:ว่า|ให้(?:จำ)?(?:ว่า)?|เรื่อง)\s*(.+)$')
_NEGATED = ('ไม่ต้องเตือน', 'ไม่ต้องช่วยเตือน', 'ไม่ต้องแจ้งเตือน', 'ยกเลิกเตือน')


def parse_request(text):
    """Return a validated-shape create_reminder call for explicit time-first requests."""
    raw = str(text or '').strip()
    if any(phrase in raw for phrase in _NEGATED):
        return None
    match = _CREATE.search(raw)
    if not match:
        return None
    title = match.group(1).strip()
    if not title:
        return None

    # Reuse the project's deterministic date/time parser, which supports today,
    # tomorrow, weekdays, noon, clock times, and the existing Thai time phrases.
    parsed = assistant_flow._local_wake_alarm_action('ตั้งปลุก ' + raw)
    if not parsed or parsed.get('kind') != 'tool':
        return None
    call = parsed['call']
    call['arguments']['title'] = title
    call['arguments']['urgent_alarm'] = False
    return call
