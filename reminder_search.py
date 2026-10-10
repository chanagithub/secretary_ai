# reminder_search.py
"""ค้น Reminder ด้วยข้อความ จากทุกลิสต์ (อ่านอย่างเดียว)

- โค้ดเป็นผู้ขยายคำค้น (คำพ้อง/ชื่อสถานที่/คำย่อ) และเป็นผู้ค้น ไม่ใช่ AI
- ผลเรียงวันที่ใกล้ไปไกล แสดงเป็นหมายเลข 1, 2, 3 พร้อมชื่อลิสต์ต้นทาง
- ค่าเริ่มต้น: เฉพาะที่ยังไม่เสร็จและตั้งแต่วันนี้เป็นต้นไป
- จำคำค้นล่าสุดไว้ชั่วคราว เพื่อให้ตอบต่อได้ เช่น "เฉพาะที่ยังไม่เสร็จ"
"""
import datetime
import re
import time

import tools

SEARCH_REMINDERS_SCHEMA = {
    'type': 'function',
    'function': {
        'name': 'search_reminders',
        'description': (
            'ค้นนัดหมาย/การเตือนจากข้อความในทุกลิสต์ของ Reminders '
            'เรียกเมื่อผู้ใช้ถามว่านัดหรือเรื่องใดคือวันไหน/เมื่อไหร่ '
            'เช่น "นัดหมอวันไหน" "ไปกินข้าวกับเพื่อนวันไหน" "ปันผลวันไหน"'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'keywords': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': (
                        'คำค้นสั้น ๆ จากสิ่งที่ผู้ใช้ถาม เช่น หมอ, ปันผล, เพื่อน '
                        '(ระบบขยายคำพ้องให้เอง) ห้ามใส่วันที่'
                    ),
                },
            },
            'required': ['keywords'],
        },
    },
}

_MEDICAL_TERMS = [
    'หมอ', 'แพทย์', 'โรงพยาบาล', 'รพ.', 'คลินิก', 'ตรวจสุขภาพ', 'ตรวจร่างกาย',
    'ตรวจเลือด', 'เจาะเลือด', 'ผลเลือด', 'เอกซเรย์', 'อัลตราซาวด์', 'OPD',
    'ผู้ป่วยนอก', 'อายุรกรรม', 'โรคหัวใจ', 'ศิริราช', 'สยามมินทร์',
    'นพ.', 'พญ.', 'ทพ.', 'ทพญ.', 'อ.',
    'ทำฟัน', 'หมอฟัน', 'ทันตแพทย์', 'ทันตกรรม', 'จัดฟัน', 'ขูดหินปูน',
    'รามาธิบดี', 'บำรุงราษฎร์', 'สมิติเวช', 'พญาไท', 'บางปะกอก', 'จุฬาลงกรณ์',
]

# (ชื่อกลุ่ม, คำที่ผู้ใช้พูดแล้วเรียกกลุ่มนี้, คำที่ใช้จับคู่ใน Reminder, เป็นกลุ่มเฉพาะทางไหม)
# กลุ่มเฉพาะทางที่ถูกเรียก จะไม่ขยายเป็นกลุ่มหมอทั่วไป
_GROUPS = [
    ('dental', ['ทำฟัน', 'หมอฟัน', 'ทันตแพทย์', 'ทันตกรรม', 'จัดฟัน', 'ขูดหินปูน', 'ฟัน'],
     ['ทำฟัน', 'หมอฟัน', 'ทันตแพทย์', 'ทันตกรรม', 'จัดฟัน', 'ขูดหินปูน', 'ฟัน'], True),
    ('vet', ['สัตวแพทย์', 'หมอสัตว์', 'วัคซีนหมา', 'วัคซีนสุนัข', 'วัคซีนแมว', 'หมา', 'แมว', 'สุนัข'],
     ['สัตวแพทย์', 'หมอสัตว์', 'คลินิกสัตว์', 'วัคซีนหมา', 'วัคซีนสุนัข', 'วัคซีนแมว',
      'หมา', 'แมว', 'สุนัข'], True),
    ('blood', ['ตรวจเลือด', 'เจาะเลือด', 'ผลเลือด'],
     ['ตรวจเลือด', 'เจาะเลือด', 'ผลเลือด'], True),
    ('siriraj', ['ศิริราช', 'สยามมินทร์'],
     ['ศิริราช', 'สยามมินทร์', 'โรคหัวใจ'], True),
    ('dividend', ['ปันผล', 'dividend', 'div', 'xd'],
     ['ปันผล', 'เงินปันผล', 'dividend', 'dividends', 'div', 'xd'], True),
    ('doctor', ['หมอ', 'แพทย์', 'โรงพยาบาล', 'รพ.', 'คลินิก', 'ตรวจสุขภาพ', 'ตรวจร่างกาย'],
     _MEDICAL_TERMS, False),
    ('friend', ['เพื่อน', 'แก๊ง'], ['เพื่อน', 'แก๊ง'], False),
    ('meal', ['กินข้าว', 'ทานข้าว', 'ข้าวเย็น', 'ข้าวเที่ยง', 'มื้อเย็น', 'มื้อเที่ยง',
              'อาหารเย็น', 'ดินเนอร์', 'ร้านอาหาร'],
     ['กินข้าว', 'ทานข้าว', 'ข้าวเย็น', 'ข้าวเที่ยง', 'มื้อเย็น', 'มื้อเที่ยง',
      'อาหารเย็น', 'ดินเนอร์', 'ร้านอาหาร'], False),
]
_HOSPITALS = ['รามาธิบดี', 'บำรุงราษฎร์', 'สมิติเวช', 'พญาไท', 'บางปะกอก', 'จุฬาลงกรณ์']

# กันคำชนกัน เช่น หมอน, นัดหมาย, หมอสัตว์/คลินิกสัตว์ (ไม่ใช่หมอคน), อ.เมือง (อำเภอ)
_PATTERNS = {
    'หมอ': r'หมอ(?!น|สัตว)',
    'คลินิก': r'คลินิก(?!สัตว)',
    'หมา': r'หมา(?![ยก])',
    'แพทย์': r'(?<!สัตว)(?<!ทันต)แพทย์',
    'อ.': r'(?:นัด|พบ|กับ|หา|เจอ)\s*อ\.\s*[ก-๙A-Za-z]',
}

_QUESTION_WORDS = ('วันไหน', 'เมื่อไหร่', 'เมื่อไร', 'เมื่อใด', 'วันอะไร', 'ตอนไหน', 'กี่โมง')
_PAST_WORDS = ('ที่ผ่านมา', 'ที่ผ่านไปแล้ว', 'ย้อนหลัง', 'ที่เสร็จแล้ว')
_OPEN_WORDS = ('ยังไม่เสร็จ', 'ไม่เอาที่ผ่านมา', 'ไม่รวมที่ผ่านมา', 'ไม่เอาที่เสร็จ',
               'เฉพาะอนาคต', 'เฉพาะที่จะถึง', 'ที่ยังไม่ถึง')

_LAST = {'keywords': None, 'ts': 0.0}
_LAST_TTL = 20 * 60  # วินาที: ตอบต่อได้ภายใน 20 นาทีหลังค้นครั้งล่าสุด


def _match(keyword, text):
    pattern = _PATTERNS.get(keyword)
    if pattern:
        return re.search(pattern, text) is not None
    if keyword.isascii():  # DIV, XD, OPD: ต้องเป็นคำเดี่ยว ไม่ติดตัวอักษรอังกฤษ และไม่สนตัวพิมพ์
        pat = r'(?<![A-Za-z0-9])%s(?![A-Za-z0-9])' % re.escape(keyword)
        return re.search(pat, text, re.IGNORECASE) is not None
    return keyword in text


def expand_keywords(text):
    """คำค้นจากประโยค/คำค้นด้วยกลุ่มคำพ้องที่รู้จัก (คืน [] ถ้าไม่รู้จักเลย)"""
    found = []
    specific_hit = False
    for name, triggers, terms, specific in _GROUPS:
        if specific_hit and name == 'doctor':
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


def _remember(keywords):
    _LAST['keywords'] = list(keywords)
    _LAST['ts'] = time.time()


def _last_keywords(turns):
    if _LAST['keywords'] and time.time() - _LAST['ts'] <= _LAST_TTL:
        return _LAST['keywords']
    for turn in reversed(turns or []):
        prior = str(turn.get('user') or '')
        if _is_question(prior):
            return expand_keywords(prior) or None
    return None


def local_search_action(text, turns=None):
    """ตรวจเจตนาค้นด้วยโค้ด (ไม่พึ่ง AI) คืน action หรือ None"""
    only_open = any(w in text for w in _OPEN_WORDS)
    include_past = any(w in text for w in _PAST_WORDS) and not only_open
    if _is_question(text):
        keywords = expand_keywords(text)
        if keywords:
            return {'kind': 'search', 'keywords': keywords,
                    'include_past': include_past}
        return None
    # ตอบต่อสั้น ๆ เช่น "เฉพาะที่ยังไม่เสร็จ" / "ดูที่ผ่านมาแล้วด้วย"
    if len(text.strip()) <= 60 and (only_open or include_past):
        keywords = _last_keywords(turns)
        if keywords:
            return {'kind': 'search', 'keywords': keywords,
                    'include_past': include_past}
    return None


def validate_search(arguments):
    """ตรวจค่าจาก AI คืน action {'kind': 'search', ...} และให้โค้ดขยายคำพ้องเพิ่มเอง"""
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
    for k in expand_keywords(' '.join(keywords)):
        if k not in seen:
            seen.add(k)
            keywords.append(k)
    return {'kind': 'search', 'keywords': keywords[:40],
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
    _remember(action['keywords'])
    try:
        dated, undated = search_reminders(action['keywords'], action['include_past'])
    except Exception as e:
        return 'ค้นรายการเตือนไม่สำเร็จ: %s' % e
    return format_results(dated, undated, action['keywords'], action['include_past'])
