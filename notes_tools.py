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
_NEW_NOTE_RE = re.compile(r'(?:สร้าง|ทำ)\s*โน[้๊]ต\s*ใหม่')
_NO_BODY_RE = re.compile(
    r'(?:ไม่ต้อง(?:มี|ใส่)|ไม่มี|ไม่เอา|เว้นว่าง)\s*(?:เนื้อหา|body|ข้อความ)'
    r'|(?:เนื้อหา|body|ข้อความ)\s*(?:ไม่ต้อง(?:มี|ใส่)|ไม่มี|ไม่เอา|ว่าง|เว้นว่าง)', re.I)
_BODY_CUE_RE = re.compile(r'(?:มีเนื้อหา|เนื้อหาว่า|ข้อความว่า|บันทึกว่า|จดว่า|ให้บันทึกว่า|คือ)', re.I)
SENT_LINE = ('ส่งคำสั่งไปยัง Shortcut แล้ว (แอปยืนยันผลไม่ได้ '
             'ตรวจโน้ตในโฟลเดอร์ "%s" ได้เลย)' % notes_shortcut.FOLDER_NAME)

_MONTHS = ('ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
           'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.')
# คำสั่งนำหน้า: "บันทึก ...", "ช่วยจดโน้ตว่า ...", "จดบันทึก ..." ("จด" เดี่ยวต้องตามด้วยช่องว่าง/โน้ต/ว่า/ลง
# กันไปตัดคำอย่าง "จดทะเบียน")
_CMD_RE = re.compile(
    r'^\s*(?:ช่วย)?(?:จดบันทึก|บันทึก|จด(?=\s|โน้ต|โน๊ต|ว่า|ลง))'
    r'(?:ลง)?(?:โน้ต|โน๊ต)?\s*(?:ให้)?(?:หน่อย)?(?:นะ)?(?:ครับ|ค่ะ|คะ)?\s*(?:ว่า)?[\s:：,，]*')
# วลี "ต่อจากโน้ตเดิม" (รับทั้ง โน้ต/โน๊ต) = สั่งต่อท้ายโน้ตเดิม เช่นเดียวกับคำว่า ต่อท้าย
_CONTINUE_RE = re.compile(r'ต่อจาก\s*โน[้๊]ต\s*เดิม')


class NotesToolError(Exception):
    """ข้อผิดพลาดที่มีข้อความภาษาไทยพร้อมแสดงให้ผู้ใช้อ่าน"""


class NotesToolNeedContent(NotesToolError):
    """ต้องถามเนื้อหาเพิ่มก่อนสร้างโน้ต"""


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
                                        'ห้ามแต่งเพิ่ม สรุป แปล หรือแก้คำ; เว้นว่างได้เฉพาะเมื่อผู้ใช้สั่งสร้างโน้ตว่างชัดเจน'),
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
        '1. ถ้าผู้ใช้พิมพ์เพียงชื่อโน้ต หรือพูดว่า "บันทึกชื่อ [ชื่อ]" โดยไม่ระบุเนื้อหา '
        'ให้เรียก %s ด้วย title เป็นชื่อนั้นและ content ว่าง ระบบจะแสดงหน้ายืนยันสร้างโน้ตเปล่า\n'
        '2. ถ้าผู้ใช้สั่งสร้างโน้ตใหม่และระบุว่าไม่ต้องมีเนื้อหา ให้เรียก %s ด้วย title และ content ว่าง\n'
        '3. ถ้าผู้ใช้ระบุเนื้อหา เช่น "บันทึกชื่อ [ชื่อ] มีเนื้อหาว่า [ข้อความ]" '
        'ให้เรียก %s ด้วย title ตามชื่อ และ content เป็นเฉพาะ [ข้อความ]\n'
        '4. เมื่อผู้ใช้บอกเนื้อหาที่ต้องการบันทึกแล้ว ให้เรียกเครื่องมือทันที ห้ามบอกว่าสำเร็จเอง\n'
        '5. content ต้องเป็นคำพูดของผู้ใช้ตามเดิมทุกคำ ตัดได้เฉพาะคำสั่งนำหน้า เช่น "บันทึก" "ช่วยจดว่า" '
        'ห้ามแต่งเพิ่ม ห้ามสรุป ห้ามแปล ห้ามแก้คำหรือเติมวันที่; ห้ามใช้ชื่อโน้ตแทนเนื้อหา\n'
        '6. title ใช้ชื่อโน้ตที่ผู้ใช้ระบุ หรือเสนอชื่อสั้น ๆ จากเนื้อหา\n'
        '7. ห้ามถามว่าจะสร้างโน้ตใหม่หรือต่อโน้ตเดิม ระบบจะให้ผู้ใช้เลือกเองเมื่อมีเนื้อหา\n'
        '8. ถ้าผู้ใช้ไม่ได้สั่งบันทึก ไม่ได้ระบุชื่อโน้ต และไม่ได้ให้เนื้อหา '
        '(เช่น ถามเรื่องอื่น หรือขอให้ค้น/อ่านโน้ต) '
        'ให้ตอบสั้น ๆ ว่าโหมดนี้ใช้จดบันทึกลงโน้ตเท่านั้น ยังค้นหรืออ่านโน้ตไม่ได้ '
        'ห้ามแต่งเนื้อหาโน้ตขึ้นเอง'
        % (format_date_heading(today), TOOL_NAME, TOOL_NAME, TOOL_NAME, TOOL_NAME)
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


def _requests_empty_new_note(source):
    return bool(_NEW_NOTE_RE.search(source) and _NO_BODY_RE.search(source))


def _has_explicit_title_command(source):
    return bool(re.search(
        r'^\s*(?:(?:สร้าง|ทำ)\s*โน[้๊]ต\s*ใหม่\s*)?(?:บันทึก\s*)?(?:โน[้๊]ต\s*)?ชื่อ(?:ว่า)?\s*[:：]?',
        str(source or ''), re.I))


def _title_from_request(source):
    prefix = re.split(
        r'\s*(?:มี)?(?:เนื้อหา|ข้อความ)(?:\s*ว่า)?|\s*(?:บันทึก|จด)\s*ว่า|\s*ให้บันทึก\s*ว่า',
        source, maxsplit=1, flags=re.I)[0]
    prefix = re.split(
        r'\s*(?:body|เนื้อหา|ข้อความ)\s*(?:ไม่ต้อง|ไม่เอา|ไม่มี|ว่าง|เว้นว่าง)'
        r'|\s*(?:ไม่ต้องมี|ไม่ต้องใส่|ไม่มี|ไม่เอา|เว้นว่าง)\s*(?:body|เนื้อหา|ข้อความ)',
        prefix, maxsplit=1, flags=re.I)[0]
    match = re.search(r'(?:โน[้๊]ต\s*)?ชื่อ(?:ว่า)?\s*[:：]?\s*(.+)$', prefix, re.I)
    if match:
        title = match.group(1)
    else:
        title = strip_command(prefix)
        title = re.sub(r'^(?:สร้าง|ทำ)\s*โน[้๊]ต\s*ใหม่\s*', '', title, flags=re.I)
    title = re.sub(r'^(?:โน[้๊]ต\s*)?ชื่อ(?:ว่า)?\s*', '', title, flags=re.I)
    return title.strip().strip('"“”\'')[:MAX_TITLE].strip()


def _has_explicit_body(source):
    return bool(_BODY_CUE_RE.search(source))


def _body_from_request(source):
    match = re.search(
        r'(?:มี)?(?:เนื้อหา|ข้อความ)\s*ว่า|(?:บันทึก|จด)\s*ว่า|ให้บันทึก\s*ว่า',
        source, flags=re.I)
    return source[match.end():].strip(' \t:：-') if match else ''


def infer_title_only_request(source):
    """คืนชื่อ เมื่อข้อความในโหมดโน้ตเป็นเพียงคำขอชื่อโน้ต ไม่ใช่คำถาม/ค้นหา"""
    text = str(source or '').strip()
    if not text or _has_explicit_body(text):
        return ''
    if continue_body(text) is not None:  # สั่งต่อจากโน้ตเดิม ไม่ใช่คำขอสร้างโน้ตเปล่า
        return ''
    if re.search(r'(?:ค้น|หา|อ่าน|เปิด|แสดง|มีโน้ต|โน้ตไหน|อะไร|อย่างไร|ทำไม|ไหม|หรือไม่|\?)', text, re.I):
        return ''
    if _requests_empty_new_note(text):
        return _title_from_request(text)
    # "บันทึก [ข้อความ]" คือให้บันทึกข้อความ; ต้องมีคำว่า "ชื่อ" จึงเป็นคำสั่งตั้งชื่อโน้ตเปล่า
    if re.match(r'^\s*(?:ช่วย\s*)?(?:บันทึก|จดบันทึก|จด)\s+', text, re.I):
        return _title_from_request(text) if _has_explicit_title_command(text) else ''
    return _title_from_request(text)


def infer_explicit_body_request(source):
    """แยกคำสั่งที่มีตัวบอกเนื้อหาชัดเจนไว้สำรองเมื่อ AI ไม่เรียกเครื่องมือ"""
    text = str(source or '').strip()
    cont = continue_body(text)
    if cont is not None:  # ต่อจากโน้ตเดิม: เนื้อหาว่างได้ (แอปจะถามหลังเลือกโน้ต)
        return {'title': suggest_title(cont) or 'ข้อความต่อท้าย', 'content': cont}
    if not _has_explicit_body(text):
        if re.match(r'^\s*(?:ช่วย\s*)?(?:บันทึก|จดบันทึก|จด)\s+', text, re.I):
            content = strip_command(text)
            if content and not _has_explicit_title_command(text):
                return {'title': suggest_title(content), 'content': content}
        return None
    content = _body_from_request(text)
    if not content:
        return None
    title = _title_from_request(text) or suggest_title(content)
    return {'title': title, 'content': content}


def continue_body(source):
    """คำสั่งที่มีวลี "ต่อจากโน้ตเดิม": คืนข้อความที่เหลือ (ตัดวลีและคำสั่งนำหน้าออก, ว่างได้)
    คืน None ถ้าไม่มีวลีนี้ (ใช้กับคำสั่งอื่นไม่ได้เปลี่ยนพฤติกรรมเดิม)"""
    text = str(source or '')
    match = _CONTINUE_RE.search(text)
    if not match:
        return None
    return strip_command(text[:match.start()] + ' ' + text[match.end():]).strip()


def requested_mode(source):
    """ใช้ต่อท้ายเมื่อคำสั่งมีคำว่า ต่อท้าย หรือ ต่อจากโน้ตเดิม; กรณีอื่นสร้างโน้ตใหม่"""
    text = str(source or '')
    return 'append' if ('ต่อท้าย' in text or _CONTINUE_RE.search(text)) else 'new'


def validate_call(arguments, source_text):
    """คืน {'content','title','used_fallback'}; รองรับโน้ตว่างเมื่อผู้ใช้ระบุชัดเจน"""
    args = arguments if isinstance(arguments, dict) else {}
    source = str(source_text or '')
    fallback = strip_command(source)
    raw_title = _norm(args.get('title'))[:MAX_TITLE].strip()
    ai_content = args.get('content')

    cont = continue_body(source)
    if cont is not None:
        # ต่อจากโน้ตเดิม: เนื้อหามาจากคำพูดผู้ใช้เท่านั้น (ว่างได้ = แอปถามหลังเลือกโน้ต)
        # ชื่อโน้ตปลายทางมาจากรายการที่เลือก ชื่อนี้ใช้แค่ในข้อความแจ้งเตือน
        if len(cont) > MAX_CONTENT:
            raise NotesToolError('เนื้อหายาวเกินไป (%d ตัวอักษร เกิน %d) แบ่งบันทึกเป็นหลายครั้งครับ'
                                 % (len(cont), MAX_CONTENT))
        return {'content': cont, 'title': suggest_title(cont) or 'ข้อความต่อท้าย',
                'used_fallback': False}

    if _requests_empty_new_note(source):
        title = raw_title or _title_from_request(source)
        if not title:
            raise NotesToolError('ไม่พบชื่อโน้ต กรุณาระบุชื่อโน้ตใหม่ครับ')
        return {'content': '', 'title': title, 'used_fallback': False}

    if _has_explicit_body(source):
        explicit_body = _body_from_request(source)
        if explicit_body:
            fallback = explicit_body

    if not _has_explicit_body(source) and (
            not re.match(r'^\s*(?:ช่วย\s*)?(?:บันทึก|จดบันทึก|จด)\s+', source, re.I)
            or _has_explicit_title_command(source)):
        title = raw_title or _title_from_request(source)
        if title:
            return {'content': '', 'title': title, 'used_fallback': False}

    content = fallback
    used_fallback = True
    if isinstance(ai_content, str) and ai_content.strip():
        a, s, f = _norm(ai_content).casefold(), _norm(source).casefold(), _norm(fallback)
        if a in s and len(a) >= 0.7 * len(f):
            content = ai_content.strip()
            used_fallback = False
    if not content.strip():
        raise NotesToolNeedContent('ต้องการบันทึกข้อความอะไรลงในโน้ตครับ?')
    if len(content) > MAX_CONTENT:
        raise NotesToolError('เนื้อหายาวเกินไป (%d ตัวอักษร เกิน %d) แบ่งบันทึกเป็นหลายครั้งครับ'
                             % (len(content), MAX_CONTENT))
    title = raw_title or suggest_title(content)
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
             'เนื้อหาที่จะบันทึก:', body if body else '(ไม่มีเนื้อหา)']
    if warning:
        lines.append('⚠ %s' % warning)
    return '\n'.join(lines)
