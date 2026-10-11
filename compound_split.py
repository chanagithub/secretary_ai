"""compound_split.py - แยกคำสั่งที่มี "ปลุก" ปนกับเรื่องอื่นในประโยคเดียว (กฎตายตัว ไม่เรียก AI)

ตัวอย่าง: "พรุ่งนี้ประชุมบ่ายสองและปลุกตอน 7 โมงเช้า"
  -> wake = "ปลุกตอน 7 โมงเช้า", rest = "พรุ่งนี้ประชุมบ่ายสอง", wake_first = False

split_wake(text) คืน dict {'wake', 'rest', 'wake_first'} หรือ None (ไม่ใช่ประโยคผสม)
ไม่แน่ใจ = คืน None (ให้ทำตามเดิม) ตัวคั่นที่ใช้: และ / แล้วก็ / , / ; (ไม่ใช้ "กับ"
เพราะเป็นส่วนของ "นัดกับหมอ")
วันที่ของส่วนปลุกไม่ยืมจากส่วนอื่น: ไม่บอกวัน = เวลาที่ใกล้ที่สุดที่จะถึง (ตามที่ตกลงไว้)
"""
import re

_CONNECTORS = re.compile(r'\s*(?:แล้วก็|และ|[,;，；])\s*')
# คำที่ถ้าเหลือแต่คำพวกนี้ แสดงว่าไม่ใช่เรื่องใหม่ (เช่น "ปลุก 7 โมงเช้า และ 8 โมงเช้า")
_FILLER = ('โมง', 'เช้า', 'สาย', 'บ่าย', 'เย็น', 'ค่ำ', 'ทุ่ม', 'ตี', 'เที่ยง', 'คืน',
           'นาที', 'ครึ่ง', 'พรุ่งนี้', 'วันนี้', 'มะรืน', 'ตอน', 'เวลา', 'น.', 'ด้วย',
           'ให้', 'ผม', 'ฉัน', 'หน่อย', 'ครับ', 'ค่ะ', 'คะ', 'นะ', 'ปลุก')
_DIGITS = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')
_NUM_WORDS = ('หนึ่ง', 'สอง', 'สาม', 'สี่', 'ห้า', 'หก', 'เจ็ด', 'แปด', 'เก้า', 'สิบ', 'เอ็ด')


def _meaningful(clause):
    """ส่วนที่เหลือมีเนื้อเรื่องจริง (ไม่ใช่แค่เวลา/วัน/คำสุภาพ)"""
    t = clause.translate(_DIGITS)
    for w in sorted(_FILLER + _NUM_WORDS, key=len, reverse=True):
        t = t.replace(w, ' ')
    t = re.sub(r'[\d\s:.\-/]+', '', t)
    return len(t) >= 3


def split_wake(text):
    text = (text or '').strip()
    if 'ปลุก' not in text:
        return None
    parts = [p.strip() for p in _CONNECTORS.split(text) if p.strip()]
    wake_idx = [i for i, p in enumerate(parts) if 'ปลุก' in p]
    if len(wake_idx) != 1:
        return None
    if len(parts) == 1:
        # ไม่มีตัวคั่น: "พรุ่งนี้ประชุมบ่ายสอง ปลุกตอน 7 โมงเช้า" แยกที่ช่องว่างก่อนคำว่า ปลุก
        m = re.search(r'\s+ปลุก', text)
        if not m or not _meaningful(text[:m.start()]):
            return None
        return {'wake': text[m.start():].strip(), 'rest': text[:m.start()].strip(),
                'wake_first': False}
    i = wake_idx[0]
    wake = parts[i]
    rest_parts = [p for j, p in enumerate(parts) if j != i]
    rest = ' '.join(rest_parts)
    if not _meaningful(rest):
        return None
    return {'wake': wake, 'rest': rest, 'wake_first': i == 0}
