# reminder_search.py
"""ค้น Reminder ด้วยข้อความ จากทุกลิสต์ (อ่านอย่างเดียว)

- ชุดคำพ้องมาจาก search_terms.json (ผ่าน search_terms.py) โค้ดเป็นผู้ขยายคำและค้นเอง
- ผลเรียงเป็นหมายเลข 1, 2, 3 พร้อมชื่อลิสต์ต้นทาง
- 3 โหมด (when): upcoming = ยังไม่เสร็จตั้งแต่วันนี้ (ค่าเริ่มต้น, ใกล้ไปไกล)
                 past = ผ่านมาแล้วหรือเสร็จแล้วเท่านั้น (ล่าสุดก่อน)
                 all = ทั้งหมด (เก่าไปใหม่)
- จำคำค้นล่าสุดไว้ชั่วคราว เพื่อให้ตอบต่อได้ เช่น "เฉพาะที่ยังไม่เสร็จ"
"""
import datetime
import re
import time

import search_terms
import tools

WHEN_VALUES = ('upcoming', 'past', 'all')


def search_schema():
    """schema ของเครื่องมือค้น: AI เห็นเฉพาะชื่อหัวข้อ ส่วนคำพ้องโค้ดขยายเอง"""
    names = search_terms.topic_names()
    topics_prop = {
        'type': 'array',
        'items': {'type': 'string'},
        'description': 'หัวข้อที่ตรงกับคำถาม เลือกจากรายการที่มี (ถ้ามี) '
                       'เช่น ถามหาหมอ = หาหมอ, ถามปันผล = ปันผล',
    }
    if names:
        topics_prop['items']['enum'] = names
    return {
        'type': 'function',
        'function': {
            'name': 'search_reminders',
            'description': (
                'ค้นนัดหมาย/การเตือนจากข้อความในทุกลิสต์ของ Reminders '
                'เรียกเมื่อผู้ใช้ถามว่านัดหรือเรื่องใดคือวันไหน/เมื่อไหร่ '
                'เช่น "นัดหมอวันไหน" "ไปกินข้าวกับเพื่อนวันไหน" "ปันผลวันไหน" '
                'หัวข้อที่มี: %s' % (', '.join(names) if names else '(ไม่มี)')),
            'parameters': {
                'type': 'object',
                'properties': {
                    'topics': topics_prop,
                    'keywords': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'คำค้นสั้น ๆ ใช้เมื่อไม่มีหัวข้อที่ตรง ห้ามใส่วันที่',
                    },
                },
                'required': [],
            },
        },
    }


# กันคำชนกัน เช่น หมอน, หมอสัตว์/คลินิกสัตว์ (ไม่ใช่หมอคน), อ.เมือง (อำเภอ)
_PATTERNS = {
    'หมอ': r'หมอ(?!น|สัตว)',
    'คลินิก': r'คลินิก(?!สัตว)',
    'หมา': r'หมา(?![ยก])',
    'แพทย์': r'(?<!สัตว)(?<!ทันต)แพทย์',
    'อ.': r'(?:นัด|พบ|กับ|หา|เจอ)\s*อ\.\s*[ก-๙A-Za-z]',
}

_QUESTION_WORDS = ('วันไหน', 'เมื่อไหร่', 'เมื่อไร', 'เมื่อใด', 'วันอะไร', 'ตอนไหน', 'กี่โมง')
def _time_words(key):
    return tuple(search_terms.load_when_words().get(key, []))

_LAST = {'topics': [], 'keywords': None, 'ts': 0.0}
_LAST_TTL = 20 * 60  # วินาที: ตอบต่อได้ภายใน 20 นาทีหลังค้นครั้งล่าสุด


def _match(keyword, text):
    pattern = _PATTERNS.get(keyword)
    if pattern:
        return re.search(pattern, text) is not None
    if keyword.isascii():  # DIV, XD, OPD: ต้องเป็นคำเดี่ยว ไม่ติดตัวอักษรอังกฤษ และไม่สนตัวพิมพ์
        pat = r'(?<![A-Za-z0-9])%s(?![A-Za-z0-9])' % re.escape(keyword)
        return re.search(pat, text, re.IGNORECASE) is not None
    return keyword in text


def _prune(names, topics):
    """ถ้าหัวข้อ A มีคำครอบคลุมหัวข้อ B ทั้งหมด (B เฉพาะเจาะจงกว่า) ให้เก็บแต่ B
    เช่น ถามว่า "หมอฟัน" ตรงทั้ง หาหมอ และ ทำฟัน -> เก็บ ทำฟัน"""
    sets = {n: set(w.lower() for w in topics[n]['terms']) for n in names}
    return [n for n in names
            if not any(m != n and sets[m] < sets[n] for m in names)]


def match_topics(text, topics=None):
    """หัวข้อที่ข้อความตรง (ตามคำ triggers) หลังเลือกหัวข้อเฉพาะเจาะจงที่สุด"""
    topics = topics if topics is not None else search_terms.load()
    hits = [n for n, t in topics.items() if any(_match(w, text) for w in t['triggers'])]
    return _prune(hits, topics)


def topic_terms(names, topics=None):
    topics = topics if topics is not None else search_terms.load()
    seen, out = set(), []
    for n in names:
        for w in topics.get(n, {}).get('terms', []):
            if w.lower() not in seen:
                seen.add(w.lower())
                out.append(w)
    return out


def expand_keywords(text):
    """คำค้นทั้งหมดจากประโยคผู้ใช้ (คืน [] ถ้าไม่ตรงหัวข้อใดเลย)"""
    return topic_terms(match_topics(text))


def _is_question(text):
    return any(w in text for w in _QUESTION_WORDS)


def _when_from_text(text):
    if any(w in text for w in _time_words('upcoming')):
        return 'upcoming'
    if _period_from_text(text):
        return 'past'
    if any(w in text for w in _time_words('past')):
        return 'all' if any(w in text for w in _time_words('all')) else 'past'
    return 'upcoming'


def _period_from_text(text):
    today = datetime.date.today()
    words = search_terms.load_when_words()
    if any(w in text for w in words.get('last_month', [])):
        first_this_month = today.replace(day=1)
        last_month_end = first_this_month
        last_month_start = (first_this_month - datetime.timedelta(days=1)).replace(day=1)
        return {'start': last_month_start.isoformat(), 'end': last_month_end.isoformat(),
                'label': last_month_start.strftime('%m/%Y')}
    if any(w in text for w in words.get('last_year', [])):
        start = datetime.date(today.year - 1, 1, 1)
        end = datetime.date(today.year, 1, 1)
        return {'start': start.isoformat(), 'end': end.isoformat(),
                'label': str(today.year - 1)}
    return None


def _remember(action):
    _LAST['topics'] = list(action.get('topics') or [])
    _LAST['keywords'] = list(action['keywords'])
    _LAST['ts'] = time.time()
    _LAST['period'] = action.get('period')


def _last_search(turns):
    if _LAST['keywords'] and time.time() - _LAST['ts'] <= _LAST_TTL:
        return list(_LAST['topics']), list(_LAST['keywords'])
    for turn in reversed(turns or []):
        prior = str(turn.get('user') or '')
        if _is_question(prior):
            names = match_topics(prior)
            terms = topic_terms(names)
            if terms:
                return names, terms
            break
    return None, None


def local_search_action(text, turns=None):
    """ตรวจเจตนาค้นด้วยโค้ด (ไม่พึ่ง AI) คืน action หรือ None"""
    only_open = any(w in text for w in _time_words('upcoming'))
    period = _period_from_text(text)
    past = (any(w in text for w in _time_words('past')) or period is not None)
    when = _when_from_text(text)
    names = match_topics(text)
    terms = topic_terms(names)
    if terms and (_is_question(text) or past or only_open):
        action = {'kind': 'search', 'topics': names, 'keywords': terms, 'when': when}
        if period:
            action['period'] = period
        return action
    # ตอบต่อสั้น ๆ เช่น "เฉพาะที่ยังไม่เสร็จ" / "ดูที่ผ่านมาแล้วด้วย"
    if not terms and len(text.strip()) <= 60 and (only_open or past):
        last_names, last_terms = _last_search(turns)
        if last_terms:
            action = {'kind': 'search', 'topics': last_names, 'keywords': last_terms,
                      'when': when}
            if period:
                action['period'] = period
            return action
    return None


def validate_search(arguments):
    """ตรวจค่าที่ได้รับ (จาก AI หรือจากโค้ดเอง) คืน action {'kind': 'search', ...}"""
    topics = search_terms.load()
    when = arguments.get('when')
    if when not in WHEN_VALUES:
        when = 'upcoming'

    names = [n for n in search_terms.clean_words(arguments.get('topics')) if n in topics]
    keywords = search_terms.clean_words(arguments.get('keywords'))

    if names:
        terms = topic_terms(names, topics)
    else:
        # คำค้นล้วน: แต่ละคำขยายเป็นหัวข้อของตัวเอง แล้วรวมกัน (ไม่ตัดกันข้ามคำ)
        hit = []
        for k in keywords:
            for n in match_topics(k, topics):
                if n not in hit:
                    hit.append(n)
        names = hit
        terms = topic_terms(names, topics) if names else keywords
    if not terms:
        raise tools.ToolValidationError(
            'AI ไม่ได้ระบุคำค้น กรุณาบอกว่าจะค้นนัดเรื่องอะไร')
    return {'kind': 'search', 'topics': names, 'keywords': terms[:60], 'when': when}


def _naive(d):
    if d.tzinfo is not None:
        d = d.astimezone().replace(tzinfo=None)
    return d


def search_reminders(keywords, when='upcoming', period=None):
    """คืน (มีวัน, ไม่มีวัน) เป็น list ของ dict จากทุกลิสต์ เรียงตามโหมด"""
    import reminders  # โมดูลของ Pythonista (import ตอนใช้ เพื่อทดสอบนอกเครื่องได้)
    today = datetime.date.today()
    dated, undated = [], []
    for r in reminders.get_reminders(completed=False if when == 'upcoming' else None):
        haystack = '%s %s' % (r.title or '', getattr(r, 'notes', None) or '')
        if not any(_match(k, haystack) for k in keywords):
            continue
        try:
            list_name = r.calendar.title
        except Exception:
            list_name = ''
        done = bool(getattr(r, 'completed', False))
        item = {'title': r.title or '(ไม่มีชื่อ)', 'list': list_name,
                'completed': done, 'due': None}
        if r.due_date is None:
            if not period and (when != 'past' or done):
                undated.append(item)
            continue
        due = _naive(r.due_date)
        if period and not (period['start'] <= due.date().isoformat() < period['end']):
            continue
        if when == 'upcoming' and due.date() < today:
            continue
        if when == 'past' and not (due.date() < today or done):
            continue
        item['due'] = due
        dated.append(item)
    dated.sort(key=lambda x: x['due'], reverse=(when == 'past'))
    return dated, undated


_SCOPE = {
    'upcoming': ('ที่ยังไม่เสร็จตั้งแต่วันนี้เป็นต้นไป', 'เรียงจากใกล้ไปไกล'),
    'past': ('ที่ผ่านมาแล้วหรือเสร็จแล้ว', 'เรียงจากล่าสุดไปเก่า'),
    'all': ('ทั้งหมด รวมที่ผ่านมาแล้วและเสร็จแล้ว', 'เรียงจากเก่าไปใหม่'),
}


def format_results(dated, undated, keywords, when='upcoming', topics=None):
    scope, order = _SCOPE[when]
    label = ('หัวข้อ "%s"' % ' + '.join(topics)) if topics else '"%s"' % ' / '.join(keywords[:4])
    if not dated and not undated:
        text = 'ไม่พบนัดใน%s (%s)' % (label, scope)
        if when == 'upcoming':
            text += '\nต้องการให้ดูที่ผ่านมาแล้วหรือที่เสร็จแล้วด้วยไหมครับ'
        return text
    lines = ['พบ %d รายการใน%s (%s) %s:' % (len(dated) + len(undated), label, scope, order)]
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
        lines.append('%d. (ไม่ได้กำหนดวัน) — %s%s%s' % (
            n, item['title'], ' [เสร็จแล้ว]' if item['completed'] else '',
            ' (ลิสต์: %s)' % item['list'] if item['list'] else ''))
    return '\n'.join(lines)


def run_search(action):
    """ทำการค้นแล้วคืนข้อความสำหรับแสดงในแชท (ไม่ throw)"""
    _remember(action)
    when = action.get('when', 'upcoming')
    try:
        dated, undated = search_reminders(action['keywords'], when, action.get('period'))
    except Exception as e:
        return 'ค้นรายการเตือนไม่สำเร็จ: %s' % e
    text = format_results(dated, undated, action['keywords'], when, action.get('topics'))
    if action.get('period'):
        period = action['period']
        text = text.replace(' (%s)' % _SCOPE[when][0],
                            ' (%s %s)' % (_SCOPE[when][0], period['label']))
    if search_terms.LOAD_ERROR:
        text += '\n(หมายเหตุ: %s)' % search_terms.LOAD_ERROR
    return text
