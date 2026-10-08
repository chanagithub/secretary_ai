"""date_guard.py - ตรวจความกำกวมของ "ชื่อวันที่ตรงกับวันนี้" ด้วยโค้ด (ไม่พึ่ง AI)

ปัญหา: วันนี้เป็นวันศุกร์ แล้วผู้ใช้พูดว่า "วันศุกร์เวลา 5 โมงเย็น" อาจหมายถึงเย็นนี้
หรือศุกร์หน้า โมเดลเล็กมักเดาเอง จึงให้โค้ดตรวจและถามผู้ใช้ก่อนส่งให้ AI

ใช้งาน:
    info = find_ambiguous_weekday(text)
    if info:
        print(question_text(info))
        choice = classify_choice(คำตอบผู้ใช้)    # 'today' / 'next' / 'cancel' / None
        text += clarify_text(info, choice)       # เติมวันที่จริงต่อท้ายก่อนส่งให้ AI

ตรวจพลาดได้แค่ "ถามเกินจำเป็น" ไม่มีทางบันทึกผิดวัน เพราะหน้ายืนยันยังแสดงวันที่ที่ตีความแล้วเสมอ
"""
import datetime
import re

WEEKDAYS = ['จันทร์', 'อังคาร', 'พุธ', 'พฤหัสบดี', 'ศุกร์', 'เสาร์', 'อาทิตย์']
_MONTHS = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
           'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']

# คำที่ทำให้ไม่กำกวม (เจอที่ไหนในข้อความก็ไม่ต้องถาม)
_GLOBAL_WORDS = ('วันนี้', 'พรุ่งนี้', 'มะรืน', 'เมื่อวาน',
                 'สัปดาห์หน้า', 'อาทิตย์หน้า',
                 'สัปดาห์ที่แล้ว', 'อาทิตย์ที่แล้ว')
# คำที่ต่อท้ายชื่อวันโดยตรงแล้วไม่กำกวม เช่น ศุกร์หน้า / ศุกร์ที่ 16 / ศุกร์ที่จะถึง
_AFTER_NAME = r'(หน้า|ที่จะถึง|ที่แล้ว|ที่ผ่านมา|ถัดไป|ต่อไป|ที่[\d๐-๙])'


def _compact(text):
    return re.sub(r'\s+', '', text or '')


def short_date(d):
    return '%d %s' % (d.day, _MONTHS[d.month])


def find_ambiguous_weekday(text, now=None):
    """ถ้าข้อความพูดชื่อวันที่ตรงกับวันนี้โดยไม่มีคำกำกับ คืน dict ไม่งั้นคืน None

    คืนค่า: {'name': 'วันศุกร์', 'today': date, 'next_week': date}
    """
    today = (now or datetime.datetime.now()).date()
    name = WEEKDAYS[today.weekday()]
    # "อาทิตย์" ยังแปลว่า "สัปดาห์" ด้วย จึงนับเฉพาะเมื่อพูดว่า "วันอาทิตย์"
    key = 'วัน' + name if name == 'อาทิตย์' else name

    t = _compact(text)
    if key not in t:
        return None
    if any(w in t for w in _GLOBAL_WORDS):
        return None
    if re.search(re.escape(key) + _AFTER_NAME, t):
        return None
    return {'name': 'วัน' + name, 'today': today,
            'next_week': today + datetime.timedelta(days=7)}


def question_text(info):
    return ('วันนี้เป็น%s (%s) ที่พูดถึงหมายถึงอะไร\n'
            '  1) วันนี้ (%s)\n'
            '  2) %sหน้า (%s)'
            % (info['name'], short_date(info['today']),
               short_date(info['today']),
               info['name'], short_date(info['next_week'])))


def classify_choice(text):
    """แปลคำตอบเป็น 'today' / 'next' / 'cancel' หรือ None ถ้าไม่เข้าใจ"""
    t = _compact(text).lower()
    if not t:
        return None
    if 'ยกเลิก' in t:
        return 'cancel'
    n = t[len('ข้อ'):] if t.startswith('ข้อ') else t  # "ข้อหนึ่ง" / "ข้อ 2"
    if n in ('1', '๑', 'หนึ่ง'):
        return 'today'
    if n in ('2', '๒', 'สอง'):
        return 'next'
    today_hit = 'นี้' in t
    next_hit = any(w in t for w in ('หน้า', 'ถัดไป', 'ต่อไป', 'สัปดาห์', 'อาทิตย์'))
    if today_hit == next_hit:  # ไม่เจอเลย หรือเจอทั้งคู่
        return None
    if 'ไม่' in t:  # เช่น "ไม่ใช่วันนี้" = เลือกอีกข้อ
        return 'next' if today_hit else 'today'
    return 'today' if today_hit else 'next'


def clarify_text(info, choice):
    """ข้อความที่เติมต่อท้ายคำสั่ง บอก AI ว่าหมายถึงวันที่จริงวันไหน"""
    if choice == 'today':
        return ' (หมายถึงวันนี้ วันที่ %s)' % info['today'].isoformat()
    return ' (หมายถึงสัปดาห์หน้า วันที่ %s)' % info['next_week'].isoformat()