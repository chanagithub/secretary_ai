"""ค้น Reminder ด้วยข้อความ จากทุกลิสต์ (อ่านอย่างเดียว)

- ชุดคำพ้องมาจาก search_terms.json (ผ่าน search_terms.py) โค้ดเป็นผู้ขยายคำและค้นเอง
- ผลเรียงเป็นหมายเลข 1, 2, 3 พร้อมชื่อลิสต์ต้นทาง
- 3 โหมด (when): upcoming = ยังไม่เสร็จตั้งแต่วันนี้ (ค่าเริ่มต้น, ใกล้ไปไกล)
                 past = ผ่านมาแล้วหรือเสร็จแล้วเท่านั้น (ล่าสุดก่อน)
                 all = ทั้งหมด (เก่าไปใหม่)
- จำคำค้นล่าสุดไว้ชั่วคราว เพื่อให้ตอบต่อได้ เช่น "เฉพาะที่ยังไม่เสร็จ"
- v12: โค้ดอ่านทิศทางเวลาเอง ("ก่อนหน้านี้", "ได้...มา", "ก่อนวันที่ 11 เดือน 10 2569")
       และชนิดคำถาม (ask: list/count/amount) แล้วทับค่าที่ AI เลือก
"""
import datetime
import re
import time

import search_terms
import tools

WHEN_VALUES = ('upcoming', 'past', 'all')
ASK_VALUES = ('list', 'count', 'amount')


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
                'เรียกเมื่อผู้ใช้ถามว่านัดหรือเรื่องใดคือวันไหน/เมื่อไหร่ หรือถามย้อนหลังว่าได้อะไรมาบ้าง '
                'เช่น "นัดหมอวันไหน" "ไปกินข้าวกับเพื่อนวันไหน" "ปันผลวันไหน" "ที่ผ่านมาได้ปันผลกี่รายการ" '
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
                    'when': {
                        'type': 'string',
                        'enum': list(WHEN_VALUES),
                        'description': 'upcoming = ที่จะถึง/ยังไม่เสร็จ (ค่าเริ่มต้น), '
                                       'past = ที่ผ่านมา/ก่อนหน้านี้/ได้มาแล้ว, '
                                       'all = ทั้งอดีตและอนาคต',
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

_QUESTION_WORDS = ('วันไหน', 'เมื่อไหร่', 'เมื่อไร', 'เมื่อใด', 'วันอะไร', 'ตอนไหน', 'กี่โมง',
                   'เท่าไหร่', 'เท่าไร', 'กี่รายการ', 'กี่ครั้ง', 'กี่บาท', 'กี่งวด')

# คำบอกอดีตที่ฝังในโค้ด (เสริมจาก search_terms.json ไม่แทนที่)
_PAST_PHRASES = ('ก่อนหน้านี้', 'ก่อนหน้าวันนี้', 'ก่อนวันนี้', 'ในอดีต', 'ที่ผ่านมา',
                 'ย้อนหลัง', 'จนถึงวันนี้', 'ถึงวันนี้', 'จนถึงตอนนี้', 'ถึงตอนนี้', 'เคยได้')
# "ได้ปันผลมา", "ได้มา" (ไม่นับ "ได้มากกว่า", "ได้มาตรฐาน")
_PAST_RE = re.compile(r'ได้.{0,15}?มา(?!กกว่า|กขึ้น|กที่สุด|ตร)')


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


def _has_strong_past(text):
    """คำบอกอดีตที่ฝังในโค้ด (ไม่นับ "จะได้...มา" ซึ่งเป็นอนาคต)"""
    if any(w in text for w in _PAST_PHRASES):
        return True
    return 'จะได้' not in text and _PAST_RE.search(text) is not None


def _has_past(text):
    return _has_strong_past(text) or any(w in text for w in _time_words('past'))


def question_kind(text):
    """'amount' = ถามยอดเงิน, 'count' = ถามจำนวนรายการ, 'list' = ขอดูรายการ"""
    t = text.translate(_THAI_DIGITS)
    if re.search(r'เท่า(?:ไหร่|ไร)|ยอดรวม|รวมเป็นเงิน|กี่บาท|รวมยอด', t):
        return 'amount'
    if re.search(r'กี่(?:รายการ|ครั้ง|ตัว|หุ้น|อัน|งวด)', t):
        return 'count'
    return 'list'


def _when_hint(text):
    """ทิศทางเวลาที่อ่านได้จากประโยค คืน None ถ้าประโยคไม่บอก (ให้ใช้ค่าอื่นแทน)"""
    period = _period_from_text(text)
    if period and period.get('before'):
        # "ก่อนวันที่ X" = ทุกอย่างที่กำหนดวันก่อน X (ทั้งเสร็จแล้วและยังไม่เสร็จ)
        return 'all'
    if any(w in text for w in _time_words('upcoming')):
        return 'upcoming'
    if period:
        # เดือนที่ระบุชัด (เช่น กย 2569) อาจเป็นอดีตหรืออนาคตก็ได้ จึงดูทั้งเดือน ไม่กรองเฉพาะอดีต
        return 'all' if period.get('explicit') else 'past'
    if _has_strong_past(text):
        # "ก่อนหน้านี้ทั้งหมด" = อดีตทั้งหมด ไม่ใช่รวมอนาคต
        return 'past'
    if any(w in text for w in _time_words('past')):
        return 'all' if any(w in text for w in _time_words('all')) else 'past'
    return None


def _when_from_text(text):
    return _when_hint(text) or 'upcoming'


_THAI_DIGITS = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')
_MONTH_WORDS = (  # ยาวก่อนสั้น กันจับ "สิบ" ก่อน "สิบสอง"
    ('มกราคม', 1), ('กุมภาพันธ์', 2), ('มีนาคม', 3), ('เมษายน', 4), ('พฤษภาคม', 5),
    ('มิถุนายน', 6), ('กรกฎาคม', 7), ('สิงหาคม', 8), ('กันยายน', 9), ('ตุลาคม', 10),
    ('พฤศจิกายน', 11), ('ธันวาคม', 12),
    ('มีค', 3), ('มิย', 6), ('มค', 1), ('กพ', 2), ('เมย', 4), ('พค', 5), ('กค', 7),
    ('สค', 8), ('กย', 9), ('ตค', 10), ('พย', 11), ('ธค', 12),
)
_NUMBER_WORD_MONTHS = (
    ('สิบสอง', 12), ('สิบเอ็ด', 11), ('สิบ', 10), ('เก้า', 9), ('แปด', 8), ('เจ็ด', 7),
    ('หก', 6), ('ห้า', 5), ('สี่', 4), ('สาม', 3), ('สอง', 2), ('หนึ่ง', 1),
)
_MONTH_ALT = '|'.join(re.escape(w) for w, _ in
                      sorted(_MONTH_WORDS, key=lambda x: len(x[0]), reverse=True))
# "ก่อนวันที่ 11 เดือน 10 2569", "ก่อน 15/9/69", "ก่อน 1 ตค 2569" (จุดถูกลบก่อนจับ)
_BEFORE_DATE_RE = re.compile(
    r'ก่อน\s*(?:วันที่\s*)?(\d{1,2})\s*(?:[/\-]|เดือน(?:ที่)?)?\s*'
    r'(\d{1,2}|' + _MONTH_ALT + r')(?!\d)'
    r'\s*(?:[/\-]|ปี)?\s*(?:พศ|คศ)?\s*(\d{4}|\d{2})?(?!\d)')


def _norm(text):
    return (text or '').translate(_THAI_DIGITS).replace('.', '')


def _before_date_period(text, today=None):
    """"ก่อน <วันที่>" -> ช่วงตั้งแต่ต้นจนถึงก่อนวันนั้น (ไม่รวมวันนั้น) ถ้าไม่มีคืน None"""
    today = today or datetime.date.today()
    months = dict(_MONTH_WORDS)
    for m in _BEFORE_DATE_RE.finditer(_norm(text)):
        day, mon, yr = m.group(1), m.group(2), m.group(3)
        month = int(mon) if mon.isdigit() else months.get(mon)
        year = today.year
        if yr:
            year = int(yr)
            if year < 100:                 # 69 -> 2569 (พ.ศ.), 26 -> 2026
                year += 2500 if year >= 50 else 2000
            if year >= 2400:               # พ.ศ. -> ค.ศ.
                year -= 543
        try:
            end = datetime.date(year, month, int(day))
        except (TypeError, ValueError):
            continue
        return {'start': '1900-01-01', 'end': end.isoformat(),
                'label': 'ก่อน %s' % end.strftime('%d/%m/%Y'),
                'explicit': True, 'before': True}
    return None


def _explicit_period(text):
    """เดือน+ปีที่ระบุชัดในประโยค เช่น "เดือนเก้าปี 2026", "กย 2569", "ก.ย. 69"->ไม่รองรับ, "9/2026"
    ต้องมีทั้งเดือนและปี (พ.ศ. 2400 ขึ้นไป แปลงเป็น ค.ศ.) ถ้าไม่ครบคืน None"""
    t = text.translate(_THAI_DIGITS).replace('.', '')
    month = None
    m = re.search(r'(?<![\d/])(\d{1,2})/(\d{4})(?![\d/])', t)
    year = None
    if m:
        month, year = int(m.group(1)), int(m.group(2))
    else:
        m = re.search(r'เดือน(?:ที่)?\s*(\d{1,2})(?!\d)', t)
        if m:
            month = int(m.group(1))
        if month is None:
            m = re.search(r'เดือน\s*(%s)' % '|'.join(w for w, _ in _NUMBER_WORD_MONTHS), t)
            if m:
                month = dict(_NUMBER_WORD_MONTHS)[m.group(1)]
        if month is None:
            for w, n in _MONTH_WORDS:
                if w in t:
                    month = n
                    break
        ym = re.search(r'(?<![\d/])(\d{4})(?![\d/])', t)
        if ym:
            year = int(ym.group(1))
    if month is None or year is None or not 1 <= month <= 12:
        return None
    if year >= 2400:
        year -= 543
    if not 1900 <= year <= 2200:
        return None
    start = datetime.date(year, month, 1)
    end = datetime.date(year + (month == 12), month % 12 + 1, 1)
    return {'start': start.isoformat(), 'end': end.isoformat(),
            'label': '%02d/%d' % (month, year), 'explicit': True}


def _period_from_text(text):
    today = datetime.date.today()
    before = _before_date_period(text, today)   # ต้องมาก่อน ไม่งั้นได้ "ทั้งเดือน" แทน "ก่อนวันที่"
    if before:
        return before
    explicit = _explicit_period(text)
    if explicit:
        return explicit
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


def _search_signal(text):
    """ประโยคมีลักษณะคำถามค้น/บอกช่วงเวลาไหม"""
    return (_is_question(text) or _has_past(text) or _period_from_text(text) is not None
            or any(w in text for w in _time_words('upcoming')))


def wants_search(text):
    """ประโยคนี้เป็นคำถามค้นตามหัวข้อ (เช่น ปันผล) ไหม: ใช้กันไม่ให้ตัวดูรายการรายวันแย่งไป"""
    return bool(topic_terms(match_topics(text))) and _search_signal(text)


def apply_text_hints(arguments, text):
    """ทับค่าที่ AI ส่งมาด้วยสิ่งที่โค้ดอ่านได้จากประโยค (ช่วงเวลา/ทิศทาง/ชนิดคำถาม)"""
    period = _period_from_text(text)
    if period:
        arguments['period'] = period
    when = _when_hint(text)
    if when:
        arguments['when'] = when
    arguments['ask'] = question_kind(text)
    return arguments


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
    past = _has_past(text) or period is not None
    when = _when_from_text(text)
    ask = question_kind(text)
    names = match_topics(text)
    terms = topic_terms(names)
    if terms and (_is_question(text) or past or only_open):
        action = {'kind': 'search', 'topics': names, 'keywords': terms,
                  'when': when, 'ask': ask}
        if period:
            action['period'] = period
        return action
    # ตอบต่อสั้น ๆ เช่น "เฉพาะที่ยังไม่เสร็จ" / "ดูที่ผ่านมาแล้วด้วย"
    if not terms and len(text.strip()) <= 60 and (only_open or past):
        last_names, last_terms = _last_search(turns)
        if last_terms:
            action = {'kind': 'search', 'topics': last_names, 'keywords': last_terms,
                      'when': when, 'ask': ask}
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
    action = {'kind': 'search', 'topics': names, 'keywords': terms[:60], 'when': when}
    ask = arguments.get('ask')
    action['ask'] = ask if ask in ASK_VALUES else 'list'
    period = arguments.get('period')
    if (isinstance(period, dict) and isinstance(period.get('start'), str)
            and isinstance(period.get('end'), str)):
        action['period'] = {'start': period['start'], 'end': period['end'],
                            'label': str(period.get('label', ''))}
        if period.get('start') and arguments.get('when') not in WHEN_VALUES:
            action['when'] = 'all'
    return action


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


def ask_note(action, total):
    """ข้อความเพิ่มตามชนิดคำถาม: ถามยอดเงิน -> บอกตรง ๆ ว่ายังรวมยอดไม่ได้ (ไม่อ้างว่าทำได้)"""
    if action.get('ask') == 'amount' and total:
        return ('หมายเหตุ: ตอนนี้ยังรวมยอดเงินให้ไม่ได้ เพราะยอดเงินเขียนอยู่ในชื่อรายการแบบข้อความอิสระ '
                'จึงแสดงรายการให้ดูก่อน')
    return ''


def run_search(action):
    """ทำการค้นแล้วคืนข้อความสำหรับแสดงในแชท (ไม่ throw)"""
    return run_search_full(action)[0]


def run_search_full(action):
    """เหมือน run_search แต่คืน (ข้อความ, dated, undated) เพื่อให้หน้าตารางใช้แถวชุดเดียวกัน (ไม่ throw)"""
    _remember(action)
    when = action.get('when', 'upcoming')
    try:
        dated, undated = search_reminders(action['keywords'], when, action.get('period'))
    except Exception as e:
        return 'ค้นรายการเตือนไม่สำเร็จ: %s' % e, [], []
    text = format_results(dated, undated, action['keywords'], when, action.get('topics'))
    if action.get('period') and not dated and not undated:
        topics = action.get('topics')
        label = ' + '.join(topics) if topics else ' / '.join(action['keywords'][:4])
        return 'ไม่พบข้อมูล "%s" ในช่วง %s' % (label, action['period']['label']), [], []
    if action.get('period'):
        period = action['period']
        text = text.replace(' (%s)' % _SCOPE[when][0],
                            ' (%s %s)' % (_SCOPE[when][0], period['label']))
    if search_terms.LOAD_ERROR:
        text += '\n(หมายเหตุ: %s)' % search_terms.LOAD_ERROR
    return text, dated, undated


if __name__ == '__main__':
    # รันไฟล์นี้ตรง ๆ ใน Pythonista เพื่อดูว่าโค้ดอ่านประโยคตัวอย่างอย่างไร
    samples = [
        'ก่อนหน้าวันนี้  คือก่อนวันที่ 11 เดือน 10 2569 ฉันได้ปันผลมากี่รายการ',
        'ก่อนหน้านี้ทั้งหมดฉันได้ปันผลมาเท่าไหร่',
        'ช่วยหาเงินเงินปันผล ในอดีต',
        'ปันผล กย 2569',
        'ปันผลก่อน 15/9/69',
        'ปันผลวันไหน',
    ]
    for s in samples:
        a = local_search_action(s)
        got = None if a is None else (a['when'], (a.get('period') or {}).get('label'), a['ask'])
        print('-', s, '\n   ->', got, '| wants_search =', wants_search(s))