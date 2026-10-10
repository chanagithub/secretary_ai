# search_terms.py
"""ชุดคำค้นของหัวข้อต่าง ๆ (เก็บในไฟล์ search_terms.json ข้างโค้ด)

หัวข้อหนึ่งมี 2 รายการ:
- triggers = คำที่ผู้ใช้พูดแล้วให้เข้าใจว่าถามหัวข้อนี้ (เช่น "หมอ", "ปันผล")
- terms    = คำที่ใช้ค้นใน Reminder จริง (เช่น "ตรวจเลือด", "ศิริราช", "DIV")

ไฟล์นี้เป็นแหล่งเดียวของคำพ้อง ทั้งทางที่โค้ดตัดสินเองและทางที่ AI เลือก
AI เห็นแค่ชื่อหัวข้อ ส่วนโค้ดเป็นผู้ขยายเป็นคำทั้งหมดและค้นเอง
ถ้าไฟล์หายจะสร้างจากค่าเริ่มต้น ถ้าไฟล์เสียจะใช้ค่าเริ่มต้นโดยไม่ทับไฟล์เดิม
"""
import copy
import json
import os
import re
import shutil

FILE_NAME = 'search_terms.json'
MAX_WORD = 30
MAX_TOPIC_NAME = 30

_MEDICAL_TERMS = [
    'หมอ', 'แพทย์', 'โรงพยาบาล', 'รพ.', 'คลินิก', 'ตรวจสุขภาพ', 'ตรวจร่างกาย',
    'ตรวจเลือด', 'เจาะเลือด', 'ผลเลือด', 'เอกซเรย์', 'อัลตราซาวด์', 'OPD',
    'ผู้ป่วยนอก', 'อายุรกรรม', 'โรคหัวใจ', 'ศิริราช', 'สยามมินทร์',
    'นพ.', 'พญ.', 'ทพ.', 'ทพญ.', 'อ.',
    'ทำฟัน', 'หมอฟัน', 'ทันตแพทย์', 'ทันตกรรม', 'จัดฟัน', 'ขูดหินปูน', 'ฟัน',
    'รามาธิบดี', 'บำรุงราษฎร์', 'สมิติเวช', 'พญาไท', 'บางปะกอก', 'จุฬาลงกรณ์',
]

_SOCIAL = ['เพื่อน', 'แก๊ง', 'กินข้าว', 'ทานข้าว', 'ข้าวเย็น', 'ข้าวเที่ยง',
           'มื้อเย็น', 'มื้อเที่ยง', 'อาหารเย็น', 'ดินเนอร์', 'ร้านอาหาร',
           'สังสรรค์', 'เลี้ยงสังสรรค์', 'โต๊ะจีน', 'เลี้ยงส่ง', 'เกษียณ']

# หัวข้อที่ terms เป็นส่วนย่อยของอีกหัวข้อ (เช่น ทำฟัน อยู่ใน หาหมอ) จะถูกเลือกก่อนเมื่อถามเฉพาะเจาะจง
DEFAULT_TOPICS = {
    'หาหมอ': {
        'triggers': ['หมอ', 'แพทย์', 'โรงพยาบาล', 'รพ.', 'คลินิก', 'ตรวจสุขภาพ', 'ตรวจร่างกาย',
                     'ศิริราช', 'สยามมินทร์', 'รามาธิบดี', 'บำรุงราษฎร์', 'สมิติเวช',
                     'พญาไท', 'บางปะกอก', 'จุฬาลงกรณ์'],
        'terms': list(_MEDICAL_TERMS),
    },
    'ทำฟัน': {
        'triggers': ['ทำฟัน', 'หมอฟัน', 'ทันตแพทย์', 'ทันตกรรม', 'จัดฟัน', 'ขูดหินปูน', 'ฟัน'],
        'terms': ['ทำฟัน', 'หมอฟัน', 'ทันตแพทย์', 'ทันตกรรม', 'จัดฟัน', 'ขูดหินปูน', 'ฟัน'],
    },
    'ตรวจเลือด': {
        'triggers': ['ตรวจเลือด', 'เจาะเลือด', 'ผลเลือด'],
        'terms': ['ตรวจเลือด', 'เจาะเลือด', 'ผลเลือด'],
    },
    'ศิริราช': {
        'triggers': ['ศิริราช', 'สยามมินทร์'],
        'terms': ['ศิริราช', 'สยามมินทร์', 'โรคหัวใจ'],
    },
    'สัตวแพทย์': {
        'triggers': ['สัตวแพทย์', 'หมอสัตว์', 'วัคซีนหมา', 'วัคซีนสุนัข', 'วัคซีนแมว',
                     'หมา', 'แมว', 'สุนัข'],
        'terms': ['สัตวแพทย์', 'หมอสัตว์', 'คลินิกสัตว์', 'วัคซีนหมา', 'วัคซีนสุนัข',
                  'วัคซีนแมว', 'หมา', 'แมว', 'สุนัข'],
    },
    'ปันผล': {
        'triggers': ['ปันผล', 'dividend', 'div', 'xd'],
        'terms': ['ปันผล', 'เงินปันผล', 'dividend', 'dividends', 'div', 'xd'],
    },
    'สังสรรค์': {
        'triggers': list(_SOCIAL),
        'terms': _SOCIAL + ['meeting'],
    },
}

DEFAULT_WHEN_WORDS = {
    'past': ['ที่ผ่านมา', 'ที่ผ่านไปแล้ว', 'ย้อนหลัง', 'ที่เสร็จแล้ว', 'ได้รับแล้ว',
             'ที่ได้รับ', 'จ่ายแล้ว', 'ไปแล้ว', 'ในอดีต', 'ครั้งที่แล้ว', 'ครั้งก่อน'],
    'last_month': ['เดือนที่แล้ว', 'เดือนก่อน'],
    'last_year': ['ปีที่แล้ว', 'ปีก่อน'],
    'all': ['ด้วย', 'ทั้งหมด', 'รวม'],
    'upcoming': ['ยังไม่เสร็จ', 'ไม่เอาที่ผ่านมา', 'ไม่รวมที่ผ่านมา', 'ไม่เอาที่เสร็จ',
                 'เฉพาะอนาคต', 'เฉพาะที่จะถึง', 'ที่ยังไม่ถึง'],
}

LOAD_ERROR = None  # ข้อความเมื่อไฟล์เสียหาย (ใช้ค่าเริ่มต้นแทน) ไม่เสียหาย = None


def path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), FILE_NAME)


def defaults():
    return copy.deepcopy(DEFAULT_TOPICS)


def default_when_words():
    return copy.deepcopy(DEFAULT_WHEN_WORDS)


def clean_words(raw):
    """รับ list หรือข้อความคั่นด้วย , ، 、 ขึ้นบรรทัด คืน list คำที่สะอาด ไม่ซ้ำ ยาวไม่เกิน MAX_WORD"""
    if isinstance(raw, str):
        raw = re.split(r'[,，;；،、\n]', raw)
    if not isinstance(raw, (list, tuple)):
        return []
    seen, out = set(), []
    for item in raw:
        word = str(item).strip()
        if 1 <= len(word) <= MAX_WORD and word.lower() not in seen:
            seen.add(word.lower())
            out.append(word)
    return out


def validate(topics):
    """ตรวจและทำความสะอาดทั้งชุด คืน dict ใหม่ ถ้าไม่ผ่านจะ raise ValueError ข้อความภาษาไทย"""
    if not isinstance(topics, dict):
        raise ValueError('รูปแบบไฟล์ไม่ถูกต้อง')
    result = {}
    for name, body in topics.items():
        name = str(name).strip()
        if not (1 <= len(name) <= MAX_TOPIC_NAME):
            raise ValueError('ชื่อหัวข้อต้องยาว 1-%d ตัวอักษร' % MAX_TOPIC_NAME)
        if name in result:
            raise ValueError('ชื่อหัวข้อซ้ำ: %s' % name)
        if not isinstance(body, dict):
            raise ValueError('หัวข้อ "%s" รูปแบบไม่ถูกต้อง' % name)
        # รองรับทั้งชื่อฟิลด์เดิมและรูปแบบภาษาไทยที่จัดการจากเมนู
        terms = clean_words(body.get('terms', body.get('ค้นหา')))
        if not terms:
            raise ValueError('หัวข้อ "%s" ต้องมีคำค้นอย่างน้อย 1 คำ' % name)
        triggers = clean_words(body.get('triggers', body.get('ถามว่า')))
        result[name] = {'triggers': triggers, 'terms': terms}
    return result


def save(topics, when_words=None):
    """บันทึกลงไฟล์ (สำรองไฟล์เดิมเป็น .bak ก่อน เขียนผ่านไฟล์ชั่วคราวกันไฟล์เสีย) คืนชุดที่ตรวจแล้ว"""
    global LOAD_ERROR
    clean = validate(topics)
    target = path()
    if os.path.exists(target):
        try:
            shutil.copyfile(target, target + '.bak')
        except OSError:
            pass
    tmp = target + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        thai_topics = {name: {'ถามว่า': body['triggers'], 'ค้นหา': body['terms']}
                       for name, body in clean.items()}
        data = {'version': 2, 'topics': thai_topics,
                'ช่วงเวลา': validate_when_words(
                    when_words if when_words is not None else _WHEN_WORDS)}
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, target)
    LOAD_ERROR = None
    return clean


def load():
    """อ่านชุดคำปัจจุบัน (อ่านจากไฟล์ทุกครั้ง แก้แล้วมีผลทันที)"""
    global LOAD_ERROR
    target = path()
    if not os.path.exists(target):
        _set_when_words(default_when_words())
        topics = defaults()
        try:
            save(topics)
        except (OSError, ValueError):
            pass
        return topics
    try:
        with open(target, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and 'topics' in data:
            raw = data.get('topics')
        else:
            raw = data  # รองรับ JSON แบบหัวข้ออยู่ชั้นบนสุด
        topics = validate(raw)
        if isinstance(data, dict) and 'ช่วงเวลา' in data:
            _set_when_words(validate_when_words(data['ช่วงเวลา']))
    except (OSError, ValueError, AttributeError) as e:
        LOAD_ERROR = 'อ่านไฟล์ search_terms.json ไม่ได้ จึงใช้ชุดคำเริ่มต้นแทน (%s)' % e
        _set_when_words(default_when_words())
        return defaults()
    LOAD_ERROR = None
    return topics


def reset_defaults():
    """คืนค่าเริ่มต้นทั้งไฟล์ (ไฟล์เดิมถูกสำรองเป็น .bak)"""
    return save(defaults())


def topic_names():
    return list(load().keys())


_WHEN_WORDS = copy.deepcopy(DEFAULT_WHEN_WORDS)


def _set_when_words(words):
    global _WHEN_WORDS
    _WHEN_WORDS = copy.deepcopy(words)


def validate_when_words(words):
    if not isinstance(words, dict):
        raise ValueError('รูปแบบคำบอกช่วงเวลาไม่ถูกต้อง')
    result = {}
    for key in DEFAULT_WHEN_WORDS:
        result[key] = clean_words(words.get(key, DEFAULT_WHEN_WORDS[key]))
    return result


def load_when_words():
    load()
    return copy.deepcopy(_WHEN_WORDS)
