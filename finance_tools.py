"""finance_tools.py - เครื่องมือ (tools) ของโหมดรายรับรายจ่าย + ตัวตรวจค่าที่ AI ส่งมา (ตรรกะล้วน)

ไม่พึ่ง Pythonista/ui จึงทดสอบได้ทุกที่ ตามหลัก: AI แปลภาษา โค้ดตรวจซ้ำและเป็นผู้เขียนข้อมูลเอง
- schemas(lists)            schema ของ record_expense / record_income (ใส่รายชื่อหมวดจริงของไฟล์)
- system_message(...)       ข้อความ system ที่แนบท้าย history ตอนอยู่โหมดนี้
- validate_record(...)      ตรวจค่าที่ AI ส่ง -> rec (หมวด/ประเภทชำระ/วันที่ที่ไม่ตรงหรือว่าง = None ให้แอปถามผู้ใช้)
- parse_date_text / parse_amount   ใช้กับช่องพิมพ์ในเมนูแก้ไขด้วย
- amount_warning            เตือนถ้าตัวเลขที่ AI ส่งมาไม่พบในคำพูดของผู้ใช้
- format_confirm_text / format_saved_line   ข้อความป๊อปอัปยืนยัน / บรรทัดผลหลังบันทึก
ปีเป็น ค.ศ. เสมอ (ถ้าเจอปี > 2400 ถือว่า พ.ศ. แล้วลบ 543)
"""
import datetime
import math
import re

import finance_db as fdb

EXPENSE = 'expense'
INCOME = 'income'
TOOL_NAMES = ('record_expense', 'record_income')
KIND_BY_TOOL = {'record_expense': EXPENSE, 'record_income': INCOME}
MAX_AMOUNT = 1000000000.0

_DIGITS = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')
_WEEKDAYS = ['จันทร์', 'อังคาร', 'พุธ', 'พฤหัสบดี', 'ศุกร์', 'เสาร์', 'อาทิตย์']
_MONTHS_SHORT = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
                 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
_MONTHS_FULL = ['', 'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
                'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']
_RELATIVE_DAYS = {'วันนี้': 0, 'เมื่อวาน': -1, 'เมื่อวานนี้': -1, 'เมื่อวานซืน': -2,
                  'เมื่อวานซิน': -2, 'พรุ่งนี้': 1}


class FinanceToolError(Exception):
    """ค่าที่ AI ส่งมาไม่ผ่านการตรวจ ข้อความเป็นภาษาไทยอ่านได้ตรง ๆ"""


def _today(today):
    return today or datetime.date.today()


# ---------- จำนวนเงิน ----------
def parse_amount(value):
    """รับตัวเลขหรือข้อความ เช่น 120, '1,200', '๑๒๐ บาท' คืน float (ปัด 2 ตำแหน่ง) หรือ raise FinanceToolError"""
    if value is None or isinstance(value, bool):
        raise FinanceToolError('ไม่ได้ระบุจำนวนเงิน กรุณาบอกจำนวนเงิน')
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).translate(_DIGITS)
        for junk in (',', '฿', 'บาท', 'baht', 'THB', ' '):
            text = text.replace(junk, '')
        if not re.match(r'^\d+(\.\d+)?$', text):
            raise FinanceToolError('จำนวนเงินไม่ถูกต้อง (%s)' % value)
        number = float(text)
    if not math.isfinite(number) or number <= 0:
        raise FinanceToolError('จำนวนเงินต้องมากกว่า 0 (%s)' % value)
    if number > MAX_AMOUNT:
        raise FinanceToolError('จำนวนเงินสูงผิดปกติ (%s) กรุณาตรวจสอบ' % value)
    return round(number, 2)


_UNITS = {'พัน': 1000, 'หมื่น': 10000, 'แสน': 100000, 'ล้าน': 1000000, 'k': 1000, 'K': 1000}


def amount_warning(amount, source_text):
    """คืนข้อความเตือน ('' = ตัวเลขตรงกับคำพูด) เตือนเท่านั้น ไม่บล็อก"""
    text = (source_text or '').translate(_DIGITS)
    candidates = []
    for m in re.finditer(r'(\d[\d,]*(?:\.\d+)?)\s*(พัน|หมื่น|แสน|ล้าน|k|K)?', text):
        try:
            base = float(m.group(1).replace(',', ''))
        except ValueError:
            continue
        candidates.append(base)
        if m.group(2):
            candidates.append(base * _UNITS[m.group(2)])
    if not candidates:
        return 'จำนวนเงินมาจากคำพูดที่ไม่มีตัวเลข ตรวจให้แน่ใจว่าถูกต้อง'
    if any(abs(c - amount) < 0.005 for c in candidates):
        return ''
    return 'ไม่พบตัวเลข %s ในคำพูดของคุณ ตรวจจำนวนเงินอีกครั้ง' % format_amount(amount)


def format_amount(amount):
    return '{:,.2f}'.format(amount)


# ---------- วันที่ ----------
def _month_number(token):
    token = token.strip('.').replace('.', '')
    if not token:
        return None
    for number in range(1, 13):
        if token == _MONTHS_SHORT[number].replace('.', '') or token == _MONTHS_FULL[number]:
            return number
    if len(token) >= 3:  # พิมพ์ย่อ เช่น "ตุลา" "ธันวา"
        hits = [n for n in range(1, 13) if _MONTHS_FULL[n].startswith(token)]
        if len(hits) == 1:
            return hits[0]
    return None


def _fix_year(year):
    if year >= 2400:
        return year - 543
    if year < 100:
        return 2000 + year
    return year


def parse_date_text(text, today=None):
    """แปลงคำพูด/ข้อความวันที่เป็น datetime.date หรือ None ถ้าอ่านไม่ออก

    รับ: วันนี้ / เมื่อวาน / เมื่อวานซืน / พรุ่งนี้, 2026-10-05, 5/10/2026, 5/10/2569, 5/10,
         5 ตุลาคม, 5 ต.ค. 2026, 5 ตุลา, วันที่ 5 ตุลาคม 2569
    ถ้าไม่บอกปีและวันที่นั้นอยู่ในอนาคตเกิน 60 วัน ถือว่าหมายถึงปีที่แล้ว (เช่น พูด "28 ธันวา" ตอนต้นปี)
    """
    now = _today(today)
    t = ' '.join(str(text or '').translate(_DIGITS).split())
    if not t:
        return None
    if t in _RELATIVE_DAYS:
        return now + datetime.timedelta(days=_RELATIVE_DAYS[t])
    year = day = month = None
    explicit_year = True
    m = re.match(r'^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$', t)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.match(r'^(\d{1,2})[-/.](\d{1,2})(?:[-/.](\d{2,4}))?$', t)
        if m:
            day, month = int(m.group(1)), int(m.group(2))
            year = int(m.group(3)) if m.group(3) else None
        else:
            m = re.match(r'^(?:วันที่ ?)?(\d{1,2}) ?(?:เดือน ?)?([ก-๙.]+?) ?(\d{4})?$', t)
            if not m:
                return None
            day, month = int(m.group(1)), _month_number(m.group(2))
            year = int(m.group(3)) if m.group(3) else None
            if month is None:
                return None
    if year is None:
        explicit_year = False
        year = now.year
    else:
        year = _fix_year(year)
    try:
        result = datetime.date(year, month, day)
    except ValueError:
        return None
    if not explicit_year and result > now + datetime.timedelta(days=60):
        try:
            result = datetime.date(year - 1, month, day)
        except ValueError:
            return None
    return result


def check_date(day, today=None):
    """วันที่ต้องอยู่ในช่วงสมเหตุสมผล (อนาคตไม่เกิน ~1 ปี, อดีตไม่เกิน ~20 ปี)"""
    now = _today(today)
    if day > now + datetime.timedelta(days=366) or day < now - datetime.timedelta(days=7300):
        raise FinanceToolError('วันที่ที่ตีความได้ (%s) ผิดปกติ กรุณาตรวจสอบอีกครั้ง'
                               % format_day_text(day))
    return day


def format_day_text(day):
    return '%s %d %s %d' % (_WEEKDAYS[day.weekday()], day.day, _MONTHS_SHORT[day.month], day.year)


# ---------- ชื่อ ----------
def _clean_text(value, limit):
    text = ' '.join(str(value or '').split())
    return text[:limit]


def _match(items, value):
    """items = [(id, name)] คืน (id, name) ที่ชื่อตรงกันทุกตัวอักษร (ไม่สนช่องว่างเกิน/ตัวพิมพ์) ไม่ตรง = None"""
    return fdb.find_by_name(items, value) if value else None


# ---------- ตรวจค่าที่ AI ส่งมา ----------
def validate_record(args, kind, lists, today=None):
    """คืน rec: kind, detail, amount, category_id/name, payment_id/name, date (ISO หรือ None), note

    category / payment_type ที่ว่างหรือไม่ตรงชื่อในไฟล์ -> None (แอปจะขึ้นรายการให้ผู้ใช้เลือก ไม่เดา)
    date ว่าง/อ่านไม่ออก -> None (แอปจะถามยืนยันวันนี้หรือให้ระบุวันที่)
    raise FinanceToolError ถ้าไม่มีชื่อรายการ/จำนวนเงิน หรือวันที่ผิดปกติ
    """
    if kind not in (EXPENSE, INCOME):
        raise FinanceToolError('ชนิดรายการไม่ถูกต้อง')
    if not isinstance(args, dict):
        args = {}
    detail = _clean_text(args.get('detail'), 100)
    if not detail:
        raise FinanceToolError('ไม่ได้ระบุชื่อรายการ กรุณาพูดอีกครั้งว่าจ่ายหรือได้รับเรื่องอะไร')
    amount = parse_amount(args.get('amount'))

    cat = _match(lists['category_expense' if kind == EXPENSE else 'category_income'],
                 args.get('category'))
    pay = _match(lists['payment_type'], args.get('payment_type')) if kind == EXPENSE else None

    day = None
    raw_date = str(args.get('date') or '').strip()
    if raw_date:
        parsed = parse_date_text(raw_date, today)
        if parsed is not None:
            day = check_date(parsed, today)
    return {'kind': kind, 'detail': detail, 'amount': amount,
            'category_id': cat[0] if cat else None, 'category_name': cat[1] if cat else None,
            'payment_id': pay[0] if pay else None, 'payment_name': pay[1] if pay else None,
            'date': day.isoformat() if day else None,
            'note': _clean_text(args.get('note'), 200)}


# ---------- schema + system message ----------
def _quoted(items):
    return ', '.join('"%s"' % name for _, name in items) or '(ยังไม่มีรายการ)'


def schemas(lists):
    """schema ของ record_expense / record_income ตามรูปแบบ OpenAI function calling"""
    common = {
        'detail': {'type': 'string',
                   'description': 'ชื่อรายการสั้น ๆ ตามที่ผู้ใช้พูด เช่น ค่าข้าว, ปันผลกองทุน AAA'},
        'amount': {'type': 'number',
                   'description': 'จำนวนเงินเป็นตัวเลข ตามที่ผู้ใช้พูดเท่านั้น ห้ามเดา'},
        'date': {'type': 'string',
                 'description': ('วันที่ YYYY-MM-DD (ค.ศ.) ถ้าผู้ใช้ไม่ได้พูดถึงวันที่ให้เว้นว่าง '
                                 'ห้ามใส่วันนี้เอง')},
        'note': {'type': 'string', 'description': 'หมายเหตุ ถ้าผู้ใช้บอกมา (ไม่บังคับ)'},
    }
    expense_props = dict(common)
    expense_props['category'] = {
        'type': 'string',
        'description': ('หมวดรายจ่าย ต้องคัดลอกจากรายการนี้ให้ตรงทุกตัวอักษร: %s '
                        'ถ้าไม่แน่ใจให้เว้นว่าง' % _quoted(lists['category_expense']))}
    expense_props['payment_type'] = {
        'type': 'string',
        'description': ('วิธีชำระเงิน ต้องคัดลอกจากรายการนี้ให้ตรงทุกตัวอักษร: %s '
                        'ถ้าผู้ใช้ไม่ได้พูดถึงวิธีจ่ายให้เว้นว่าง ห้ามเดา (ห้ามถือเป็นเงินสดเอง)'
                        % _quoted(lists['payment_type']))}
    income_props = dict(common)
    income_props['category'] = {
        'type': 'string',
        'description': ('หมวดรายรับ ต้องคัดลอกจากรายการนี้ให้ตรงทุกตัวอักษร: %s '
                        'ถ้าไม่แน่ใจให้เว้นว่าง' % _quoted(lists['category_income']))}
    return [
        {'type': 'function', 'function': {
            'name': 'record_expense',
            'description': ('บันทึกรายจ่ายเมื่อผู้ใช้บอกว่าจ่ายเงิน/ซื้อของ/เสียค่าใช้จ่ายอะไร '
                            'เรียกทันทีแม้ยังไม่มีวันที่ หมวด หรือประเภทชำระ แล้วเว้นช่องที่ไม่รู้ไว้'),
            'parameters': {'type': 'object', 'properties': expense_props,
                           'required': ['detail', 'amount']}}},
        {'type': 'function', 'function': {
            'name': 'record_income',
            'description': ('บันทึกรายรับเมื่อผู้ใช้บอกว่าได้รับเงิน/มีรายได้อะไร '
                            'เรียกทันทีแม้ยังไม่มีวันที่หรือหมวด แล้วเว้นช่องที่ไม่รู้ไว้'),
            'parameters': {'type': 'object', 'properties': income_props,
                           'required': ['detail', 'amount']}}},
    ]


def system_message(lists, db_name, today=None):
    now = _today(today)
    text = (
        'โหมดรายรับรายจ่าย (ไฟล์ข้อมูล: %s)\n'
        'วันนี้คือ %s (%s) ปีเป็น ค.ศ. เสมอ ห้ามใช้ปี พ.ศ. ในพารามิเตอร์\n'
        'ผู้ใช้จะบอกเรื่องเงินที่จ่ายหรือได้รับ ให้เรียก record_expense (จ่าย) หรือ record_income (ได้รับ) เท่านั้น '
        'ห้ามบอกว่าบันทึกแล้ว เพราะแอปจะถามยืนยันและบันทึกเอง\n'
        'กติกา:\n'
        '- detail = ชื่อรายการสั้น ๆ ตามที่ผู้ใช้พูด เช่น ค่าข้าว\n'
        '- amount = ตัวเลขตามที่ผู้ใช้พูดเท่านั้น ห้ามเดา ถ้าไม่ได้บอกจำนวนเงิน ให้ถามกลับสั้น ๆ โดยไม่เรียกเครื่องมือ\n'
        '- เมื่อมีคำสั่งจ่าย/รับเงินและมีจำนวนเงิน ให้เรียก tool ทันที แม้ไม่มีวันที่ หมวด หรือวิธีชำระ; เว้นช่องที่ไม่มีข้อมูลไว้ แอปจะถามหรือให้เลือกเอง ห้ามตอบว่างหรือรอให้ผู้ใช้บอกวันที่ก่อน\n'
        '- category ต้องคัดลอกจากรายการให้ตรงทุกตัวอักษร ถ้าไม่แน่ใจให้เว้นว่าง\n'
        '  หมวดรายจ่าย: %s\n'
        '  หมวดรายรับ: %s\n'
        '- payment_type (เฉพาะรายจ่าย) ต้องคัดลอกจาก: %s ถ้าผู้ใช้ไม่ได้พูดถึงวิธีจ่าย ให้เว้นว่าง ห้ามเดา\n'
        '- date รูปแบบ YYYY-MM-DD ถ้าผู้ใช้ไม่ได้พูดถึงวันที่ ให้เว้นว่าง ห้ามใส่วันนี้เอง '
        'ถ้าผู้ใช้ตอบสั้น ๆ ว่าเป็นวันไหน (เช่น เมื่อวาน) ให้ใช้กับรายการที่ค้างจากข้อความก่อนหน้า\n'
        '- ถ้าคำพูดเป็นเรื่องอื่น (นัดหมาย เตือน ซื้อขายกองทุน/หุ้น) ให้ตอบสั้น ๆ ว่าเป็นเรื่องของโหมดอื่น'
    ) % (db_name, now.isoformat(), _WEEKDAYS[now.weekday()],
         _quoted(lists['category_expense']), _quoted(lists['category_income']),
         _quoted(lists['payment_type']))
    return {'role': 'system', 'content': text}


# ---------- ข้อความแสดงผู้ใช้ ----------
def kind_text(kind):
    return 'รายจ่าย' if kind == EXPENSE else 'รายรับ'


def confirm_title(kind):
    return 'บันทึก%sนี้ไหม?' % kind_text(kind)


def format_confirm_text(rec, db_name, warning=''):
    """ข้อความในป๊อปอัปยืนยัน: ไฟล์ วันที่ รายการ หมวด (ประเภทชำระ) จำนวนเงิน หมายเหตุ"""
    day = datetime.date.fromisoformat(rec['date'])
    lines = ['ไฟล์: %s' % db_name,
             'วันที่: %s' % format_day_text(day),
             'รายการ: %s' % rec['detail'],
             'หมวด: %s' % (rec.get('category_name') or '-')]
    if rec['kind'] == EXPENSE:
        lines.append('ชำระ: %s' % (rec.get('payment_name') or '-'))
    lines.append('จำนวนเงิน: %s บาท' % format_amount(rec['amount']))
    lines.append('หมายเหตุ: %s' % (rec.get('note') or '-'))
    if warning:
        lines.append('⚠ %s' % warning)
    return '\n'.join(lines)


def format_saved_line(rec, db_name):
    """บรรทัดผลหลังเขียน+อ่านกลับสำเร็จ (เรียกหลัง finance_write.save_record คืน ok เท่านั้น)"""
    day = datetime.date.fromisoformat(rec['date'])
    parts = ['%d %s %d' % (day.day, _MONTHS_SHORT[day.month], day.year), rec['detail'],
             rec.get('category_name') or '-']
    if rec['kind'] == EXPENSE:
        parts.append(rec.get('payment_name') or '-')
    parts.append('%s บาท' % format_amount(rec['amount']))
    return 'บันทึก%sแล้ว ✓ %s (ไฟล์ %s)' % (kind_text(rec['kind']), ' · '.join(parts), db_name)
