"""notes_tools.py - เครื่องมือ (tool calling) + กฎตรวจค่าของโหมดโน้ต ไม่มีหน้าจอ ไม่เรียกเครือข่าย

AI มีเครื่องมือเดียว save_note(content, title): แค่แยก "เนื้อหา" ออกจากคำพูดผู้ใช้ และเสนอชื่อโน้ต
  - ใหม่ หรือ ต่อท้าย ผู้ใช้เลือกเองด้วยป๊อปอัป (AI ไม่ถาม ไม่ตัดสิน)
  - ชื่อโน้ตที่จะต่อท้ายมาจากรายการโน้ตจริงให้ผู้ใช้เลือกเท่านั้น (AI ไม่มีส่วนกำหนด)
  - เนื้อหาต้องมาจากคำพูดผู้ใช้: ตรวจเทียบกับข้อความที่ผู้ใช้พูด ไม่ผ่านใช้ข้อความที่ผู้ใช้พูด
    (ตัดคำสั่งนำหน้า เช่น "บันทึก") แทน ผู้ใช้เห็นเนื้อหาเต็มในหน้ายืนยันก่อนส่งเสมอ

ฟังก์ชันหลัก
  schemas() / system_prompt(today)        ส่งให้ ai_client.stream_chat_with_tools
  validate_call(arguments, source_text)   -> {'content','title','used_fallback'} หรือ raise NotesToolError
  build_body(mode, content, today)        ต่อท้าย = หัวข้อวันที่ + เนื้อหา, ใหม่ = เนื้อหาล้วน
  find_conflicts / conflict_text          ตรวจชื่อโน้ตซ้ำ/ซ้อนกัน (Shortcut ต่อท้ายด้วย Name contains)
  confirm_title / format_confirm_body     ข้อความหน้ายืนยันสุดท้าย
"""
import re

import notes_shortcut

TOOL_NAME = 'save_note'
MAX_CONTENT = 4000   # เพดานความปลอดภัย (ค่าประมาณ ไม่ใช่ขีดจำกัดที่ทดสอบแล้วของ Shortcuts)
MAX_TITLE = 60
SENT_LINE = ('ส่งคำสั่งไปยัง Shortcut แล้ว (แอปยืนยันผลไม่ได้ '
             'ตรวจโน้ตในโฟลเดอร์ "%s" ได้เลย)' % notes_shortcut.FOLDER_NAME)

_MONTHS = ('ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
           'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.')
# คำสั่งนำหน้า: "บันทึก ...", "ช่วยจดโน้ตว่า ...", "จดบันทึก ..." ("จด" เดี่ยวต้องตามด้วยช่องว่าง/โน้ต/ว่า/ลง
# กันไปตัดคำอย่าง "จดทะเบียน")
_CMD_RE = re.compile(
    r'^\s*(?:ช่วย)?(?:จดบันทึก|บันทึก|จด(?=\s|โน้ต|โน๊ต|ว่า|ลง))'
    r'(?:ลง)?(?:โน้ต|โน๊ต)?\s*(?:ให้)?(?:หน่อย)?(?:นะ)?(?:ครับ|ค่ะ|คะ)?\s*(?:ว่า)?[\s:：,，]*')


class NotesToolError(Exception):
    """ข้อผิดพลาดที่มีข้อความภาษาไทยพร้อมแสดงให้ผู้ใช้อ่าน"""


# ---------- ส่งให้ AI ----------
def schemas():
    return [{
        'type': 'function',
        'function': {
            'name': TOOL_NAME,
            'description': ('จดบันทึกข้อความที่ผู้ใช้พูดลงโน้ต เรียกเมื่อผู้ใช้สั่งให้บันทึก/จดเรื่องใดเรื่องหนึ่ง '
                            'ระบบจะถามผู้ใช้เองว่าสร้างโน้ตใหม่หรือต่อโน้ตเดิม'),
            'parameters': {
                'type': 'object',
                'properties': {
                    'content': {
                        'type': 'string',
                        'description': ('เนื้อหาที่จะบันทึก ต้องเป็นคำพูดของผู้ใช้ตามเดิมทุกคำ '
                                        'ตัดได้เฉพาะคำสั่งนำหน้า เช่น "บันทึก" "ช่วยจดว่า" '
                                        'ห้ามแต่งเพิ่ม สรุป แปล หรือแก้คำ'),
                    },
                    'title': {
                        'type': 'string',
                        'description': 'ชื่อโน้ตที่เสนอ สั้น ๆ (ไม่เกิน 40 ตัวอักษร) ตั้งจากเรื่องที่ผู้ใช้พูด',
                    },
                },
                'required': ['content'],
            },
        },
    }]


def system_prompt(today):
    """today = datetime.date ของวันนี้ (ใช้บอกวันที่ให้ AI รู้เฉย ๆ)"""
    return (
        'คุณคือเลขาส่วนตัวของผู้ใช้ ตอบเป็นภาษาไทย กระชับ ตรงประเด็น\n'
        'วันนี้คือ %s\n'
        'โหมดนี้ใช้จดบันทึกลงแอป Notes เท่านั้น คุณมีเครื่องมือ %s\n'
        'กติกา:\n'
        '1. เมื่อผู้ใช้สั่งให้บันทึก/จดเรื่องใด ให้เรียก %s ทันที '
        'ห้ามพิมพ์สรุปเป็นข้อความแทนการเรียกเครื่องมือ\n'
        '2. content ต้องเป็นคำพูดของผู้ใช้ตามเดิมทุกคำ ตัดได้เฉพาะคำสั่งนำหน้า เช่น "บันทึก" "ช่วยจดว่า" '
        'ห้ามแต่งเพิ่ม ห้ามสรุป ห้ามแปล ห้ามแก้คำหรือเติมวันที่\n'
        '3. title เสนอชื่อโน้ตสั้น ๆ จากเรื่องที่ผู้ใช้พูด\n'
        '4. ห้ามถามว่าจะสร้างโน้ตใหม่หรือต่อโน้ตเดิม และห้ามระบุชื่อโน้ตเดิม ระบบจะให้ผู้ใช้เลือกเอง\n'
        '5. ห้ามบอกว่าบันทึกให้แล้ว ผู้ใช้จะเห็นหน้ายืนยันก่อนเสมอ\n'
        '6. ถ้าผู้ใช้ไม่ได้สั่งให้บันทึก (เช่น ถามเรื่องอื่น หรือขอให้ค้น/อ่านโน้ต) '
        'ให้ตอบสั้น ๆ ว่าโหมดนี้ใช้จดบันทึกลงโน้ตเท่านั้น ยังค้นหรืออ่านโน้ตไม่ได้ '
        'ห้ามแต่งเนื้อหาโน้ตขึ้นเอง'
        % (format_date_heading(today), TOOL_NAME, TOOL_NAME)
    )


# ---------- ตรวจค่าที่ AI ส่งมา ----------
def _norm(text):
    return ' '.join(str(text or '').split())


def strip_command(text):
    """ตัดคำสั่งนำหน้า (บันทึก/จดโน้ต/...) ออกจากคำพูดของผู้ใช้ ที่เหลือคือเนื้อหา"""
    return _CMD_RE.sub('', str(text or ''), count=1).strip()


def suggest_title(content):
    first = _norm(str(content or '').strip().split('\n')[0])
    return first[:30].strip()


def validate_call(arguments, source_text):
    """คืน {'content','title','used_fallback'}

    content ของ AI ใช้ได้ต่อเมื่อ (1) เป็นส่วนหนึ่งของคำพูดผู้ใช้จริง (เทียบหลังรวมช่องว่าง ไม่สนตัวพิมพ์)
    และ (2) ครอบคลุมเนื้อหาไม่ต่ำกว่า 70% ของคำพูดที่ตัดคำสั่งนำหน้าแล้ว (กัน AI ตัดเนื้อหาทิ้ง)
    ไม่ผ่านข้อใดข้อหนึ่ง -> ใช้คำพูดผู้ใช้ที่ตัดคำสั่งนำหน้าแทน (used_fallback=True)
    """
    args = arguments if isinstance(arguments, dict) else {}
    source = str(source_text or '')
    fallback = strip_command(source)
    ai_content = args.get('content')
    content = fallback
    used_fallback = True
    if isinstance(ai_content, str) and ai_content.strip():
        a, s, f = _norm(ai_content).casefold(), _norm(source).casefold(), _norm(fallback)
        if a in s and len(a) >= 0.7 * len(f):
            content = ai_content.strip()
            used_fallback = False
    if not content.strip():
        raise NotesToolError('ไม่พบเนื้อหาที่จะบันทึก บอกเนื้อหาต่อจากคำว่า "บันทึก" ได้เลยครับ')
    if len(content) > MAX_CONTENT:
        raise NotesToolError('เนื้อหายาวเกินไป (%d ตัวอักษร เกิน %d) แบ่งบันทึกเป็นหลายครั้งครับ'
                             % (len(content), MAX_CONTENT))
    title = _norm(args.get('title'))[:MAX_TITLE].strip() or suggest_title(content)
    if not title:
        raise NotesToolError('ตั้งชื่อโน้ตไม่ได้ กรุณาพูดใหม่อีกครั้ง')
    return {'content': content, 'title': title, 'used_fallback': used_fallback}


def clean_title(text):
    """ชื่อโน้ตที่ผู้ใช้พิมพ์เอง: รวมช่องว่าง ตัดความยาว คืนค่าว่างถ้าไม่มีชื่อ"""
    return _norm(text)[:MAX_TITLE].strip()


# ---------- เนื้อหาที่ส่งให้ Shortcut ----------
def format_date_heading(day):
    return '%d %s %d' % (day.day, _MONTHS[day.month - 1], day.year)


def build_body(mode, content, today):
    """ต่อท้าย (append) = หัวข้อวันที่ขึ้นบรรทัดใหม่ แล้วเนื้อหา; สร้างใหม่ (new) = เนื้อหาล้วน"""
    if mode == 'append':
        return '%s\n%s' % (format_date_heading(today), content)
    return content


# ---------- ชื่อโน้ตซ้ำ/ซ้อนกัน ----------
def find_conflicts(chosen, names):
    """Shortcut หาโน้ตเพื่อต่อท้ายด้วย Name contains (ใช้ is ไม่ได้) จึงเสี่ยงต่อผิดตัวเมื่อ
    - มีโน้ตชื่อเดียวกันมากกว่าหนึ่งโน้ต (same > 1)
    - ชื่อที่เลือกเป็นส่วนหนึ่งของชื่ออื่น (overlaps) เทียบแบบไม่สนตัวพิมพ์ (ระมัดระวังไว้ก่อน)"""
    key = _norm(chosen).casefold()
    same = 0
    overlaps = []
    for n in names:
        k = _norm(n).casefold()
        if k == key:
            same += 1
        elif key and key in k:
            overlaps.append(n)
    return {'same': same, 'overlaps': overlaps}


def conflict_text(chosen, names):
    """ข้อความเตือน (ว่าง = ปลอดภัย ส่งต่อได้)"""
    info = find_conflicts(chosen, names)
    if info['same'] > 1:
        return ('มีโน้ตชื่อ "%s" ซ้ำกัน %d โน้ต ต่อท้ายไม่ได้เพราะ Shortcut แยกไม่ออก '
                'เปลี่ยนชื่อโน้ตใดโน้ตหนึ่งในแอป Notes ก่อนครับ' % (chosen, info['same']))
    if info['overlaps']:
        shown = ', '.join('"%s"' % n for n in info['overlaps'][:3])
        more = ' ...' if len(info['overlaps']) > 3 else ''
        return ('ชื่อ "%s" ซ้อนอยู่ในชื่อโน้ตอื่น: %s%s อาจต่อท้ายผิดโน้ต ไม่ส่งให้ '
                'เปลี่ยนชื่อโน้ตในแอป Notes ก่อนครับ' % (chosen, shown, more))
    return ''


# ---------- หน้ายืนยัน ----------
def confirm_title(mode):
    return 'ยืนยันต่อท้ายโน้ตเดิม' if mode == 'append' else 'ยืนยันสร้างโน้ตใหม่'


def format_confirm_body(mode, title, body, warning=''):
    lines = ['โฟลเดอร์: %s' % notes_shortcut.FOLDER_NAME,
             'ชื่อโน้ต: %s' % title,
             'วิธี: %s' % ('ต่อท้ายโน้ตเดิม' if mode == 'append' else 'สร้างโน้ตใหม่'),
             'เนื้อหาที่จะบันทึก:', body]
    if warning:
        lines.append('⚠ %s' % warning)
    return '\n'.join(lines)
