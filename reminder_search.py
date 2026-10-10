# reminder_search.py
"""ค้น Reminder ด้วยข้อความ จากทุกลิสต์ (อ่านอย่างเดียว)

- AI/โค้ดช่วยแปลงคำถามเป็นคำค้น ส่วนการค้นและวันที่มาจาก Reminders จริงเท่านั้น
- ผลเรียงวันที่ใกล้ไปไกล แสดงเป็นหมายเลข 1, 2, 3 พร้อมชื่อลิสต์ต้นทาง
- ค่าเริ่มต้น: เฉพาะที่ยังไม่เสร็จและตั้งแต่วันนี้เป็นต้นไป
"""
import datetime
import re

import tools

SEARCH_REMINDERS_SCHEMA = {
    'type': 'function',
    'function': {
        'name': 'search_reminders',
        'description': (
            'ค้นนัดหมาย/การเตือนจากข้อความในทุกลิสต์ของ Reminders '
            'เรียกเมื่อผู้ใช้ถามว่านัดหรือเรื่องใดคือวันไหน/เมื่อไหร่ '
            'เช่น "นัดหมอวันไหน" "ไปกินข้าวกับเพื่อนวันไหน"'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'keywords': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': (
                        'คำค้นสั้น ๆ ภาษาไทย พร้อมคำพ้อง 2-8 คำ เช่น หมอ ถามหาหมอ ให้ใส่ '
                        'หมอ, แพทย์, โรงพยาบาล, คลินิก ห้ามใส่วันที่'
                    ),
                },
                'include_past': {
                    'type': 'boolean',
                    'description': 'true เฉพาะเมื่อผู้ใช้ขอดูที่เสร็จแล้วหรือที่ผ่านมาแล้ว',
                },
            },
            'required': ['keywords'],
        },
    },
}

# (ชื่อกลุ่ม, คำที่ผู้ใช้พูดแล้วเรียกกลุ่มนี้, คำที่ใช้จับคู่ใน Reminder, เป็นกลุ่มเฉพาะทางไหม)
_GROUPS = [
    ('dental', ['ทำฟัน', 'หมอฟัน', 'ทันตแพทย์', 'ทันตกรรม', 'จัดฟัน', 'ขูดหินปูน', 'ฟัน'],
     ['ทำฟัน', 'หมอฟัน', 'ทันตแพทย์', 'ทันตกรรม', 'จัดฟัน', 'ขูดหินปูน', 'ฟัน'], True),
    ('vet', ['สัตวแพทย์', 'หมอสัตว์', 'วัคซีนหมา', 'วัคซีนสุนัข', 'วัคซีนแมว', 'หมา', 'แมว', 'สุนัข'],
     ['สัตวแพทย์', 'หมอสัตว์', 'คลินิกสัตว์', 'วัคซีนหมา', 'วัคซีนสุนัข', 'วัคซีนแมว',
      'หมา', 'แมว', 'สุนัข'], True),
    ('blood', ['ตรวจเลือด', 'เจาะเลือด', 'ผลเลือด'],
     ['ตรวจเลือด', 'เจาะเลือด', 'ผลเลือด'], True),
    ('doctor', ['หมอ', 'แพทย์', 'โรงพยาบาล', 'รพ.', 'คลินิก', 'ตรวจสุขภาพ'],
     ['หมอ', 'แพทย์', 'โรงพยาบาล', 'รพ.', 'คลินิก', 'ตรวจสุขภาพ'], False),
    ('friend', ['เพื่อน', 'แก๊ง'], ['เพื่อน', 'แก๊ง'], False),
    ('meal', ['กินข้าว', 'ทานข้าว', 'ข้าวเย็น', 'ข้าวเที่ยง', 'มื้อเย็น', 'มื้อเที่ยง',
              'อาหารเย็น', 'ดินเนอร์', 'ร้านอาหาร'],
     ['กินข้าว', 'ทานข้าว', 'ข้าวเย็น', 'ข้าวเที่ยง', 'มื้อเย็น', 'มื้อเที่ยง',
      'อาหารเย็น', 'ดินเนอร์', 'ร้านอาหาร'], False),
]
_HOSPITALS = ['ศิริราช', 'รามาธิบดี', 'จุฬา', 'บำรุงราษฎร์', 'รามา']

# กันคำชนกัน เช่น หมอน, นัดหมาย, สัตวแพทย์ ไม่ใช่หมอคน
_PATTERNS = {
    'หมอ': r'หมอ(?!น)',
    'หมา': r'หมา(?![ยก])',
    'แพทย์': r'(?<!สัตว)(?<!ทันต)แพทย์',
}

_QUESTION_WORDS = ('วันไหน', 'เมื่อไหร่', 'เมื่อไร', 'วันอะไร', 'ตอนไหน', 'กี่โมง')
_PAST_WORDS = ('ที่ผ่านมา', 'ที่ผ่านไปแล้ว', 'ย้อนหลัง', 'ที่เสร็จแล้ว')


def _match(keyword, text):
    pattern = _PATTERNS.get(keyword)
    if pattern:
        return re.search(pattern, text) is not None
    return keyword in text


def expand_keywords(text):
    """คำค้นจากประโยคผู้ใช้ด้วยกลุ่มคำพ้องที่รู้จัก (คืน [] ถ้าไม่รู้จักเลย)"""
    found = []
    specific_hit = False
    for _name, triggers, terms, specific in _GROUPS:
        if specific_hit and _name == 'doctor':
            continue
        if any(_match(t, text) for t in triggers):
            found.extend(terms)
            if specific:
                specific_hit = True
    found.extend(h for h in _HOSPITALS if h in text)
    seen, out = set(), []
    for k in found:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _is_question(text):
    return any(w in text for w in _QUESTION_WORDS)


def local_search_action(text, turns=None):
    """ตรวจเจตนาค้นด้วยโค้ด (ไม่พึ่ง AI) คืน action หรือ None"""
    include_past = any(w in text for w in _PAST_WORDS)
    if _is_question(text):
        keywords = expand_keywords(text)
        if keywords:
            return {'kind': 'search', 'keywords': keywords,
                    'include_past': include_past}
        return None
    if include_past:  # ตอบต่อ เช่น "ดูที่ผ่านมาแล้วด้วย" ใช้คำค้นจากคำถามก่อนหน้า
        for turn in reversed(turns or []):
            prior = str(turn.get('user') or '')
            if _is_question(prior):
                keywords = expand_keywords(prior)
                if keywords:
                    return {'kind': 'search', 'keywords': keywords,
                            'include_past': True}
                break
    return None


def validate_search(arguments):
    """ตรวจค่าจาก AI คืน action {'kind': 'search', ...}"""
    raw = arguments.get('keywords')
    if isinstance(raw, str):
        raw = re.split(r'[,،、\n]', raw)
    if not isinstance(raw, list):
        raw = []
    seen, keywords = set(), []
    for k in raw:
        k = str(k).strip()
        if 1 <= len(k) <= 30 and k not in seen:
            seen.add(k)
            keywords.append(k)
    if not keywords:
        raise tools.ToolValidationError(
            'AI ไม่ได้ระบุคำค้น กรุณาบอกว่าจะค้นนัดเรื่องอะไร')
    return {'kind': 'search', 'keywords': keywords[:12],
            'include_past': bool(arguments.get('include_past'))}


def _naive(d):
    if d.tzinfo is not None:
        d = d.astimezone().replace(tzinfo=None)
    return d


def search_reminders(keywords, include_past=False):
    """คืน (มีวัน เรียงใกล้ไปไกล, ไม่มีวัน) เป็น list ของ dict จากทุกลิสต์"""
    import reminders  # โมดูลของ Pythonista (import ตอนใช้ เพื่อทดสอบนอกเครื่องได้)
    today = datetime.date.today()
    dated, undated = [], []
    for r in reminders.get_reminders(completed=None if include_past else False):
        haystack = '%s %s' % (r.title or '', getattr(r, 'notes', None) or '')
        if not any(_match(k, haystack) for k in keywords):
            continue
        try:
            list_name = r.calendar.title
        except Exception:
            list_name = ''
        item = {'title': r.title or '(ไม่มีชื่อ)', 'list': list_name,
                'completed': bool(getattr(r, 'completed', False)), 'due': None}
        if r.due_date is None:
            undated.append(item)
            continue
        due = _naive(r.due_date)
        if not include_past and due.date() < today:
            continue
        item['due'] = due
        dated.append(item)
    dated.sort(key=lambda x: x['due'])
    return dated, undated


def format_results(dated, undated, keywords, include_past):
    scope = 'ทั้งที่ผ่านมาแล้วและเสร็จแล้ว' if include_past else 'ที่ยังไม่เสร็จตั้งแต่วันนี้เป็นต้นไป'
    if not dated and not undated:
        text = 'ไม่พบนัดที่ตรงกับ "%s" (%s)' % (' / '.join(keywords[:4]), scope)
        if not include_past:
            text += '\nต้องการให้ดูที่ผ่านมาแล้วหรือที่เสร็จแล้วด้วยไหมครับ'
        return text
    lines = ['พบ %d รายการ (%s) เรียงจากใกล้ไปไกล:' % (len(dated) + len(undated), scope)]
    n = 0
    for item in dated:
        n += 1
        due = item['due']
        clock = '' if (due.hour == 0 and due.minute == 0) else ' ' + due.strftime('%H:%M')
        lines.append('%d. %s%s — %s%s%s' % (
            n, tools.format_day_text(due.date()), clock, item['title'],
            ' [เสร็จแล้ว]' if item['completed'] else '',
            ' (ลิสต์: %s)' % item['list'] if item['list'] else ''))
    for item in undated:
        n += 1
        lines.append('%d. (ไม่ได้กำหนดวัน) — %s%s' % (
            n, item['title'],
            ' (ลิสต์: %s)' % item['list'] if item['list'] else ''))
    return '\n'.join(lines)


def run_search(action):
    """ทำการค้นแล้วคืนข้อความสำหรับแสดงในแชท (ไม่ throw)"""
    try:
        dated, undated = search_reminders(action['keywords'], action['include_past'])
    except Exception as e:
        return 'ค้นรายการเตือนไม่สำเร็จ: %s' % e
    return format_results(dated, undated, action['keywords'], action['include_past'])
