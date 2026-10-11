"""guardrails.py - กฎตายตัวระดับโหมด (ไม่เรียก AI ทดสอบด้วยภาษาไทยล้วนได้)

detect_mode(text): เดาว่าข้อความเป็นเรื่องของโหมดไหน (หรือไม่แน่ใจ = None)
mode_hint(current, text): ถ้าเรื่องที่พูดไม่ตรงโหมดปัจจุบัน คืนโหมดที่น่าจะใช่ ไม่งั้น None
ตั้งใจให้ "ระวังเกินไป" ดีกว่าเตือนพร่ำเพรื่อ: ไม่แน่ใจ = ไม่เตือน
กฎเฉพาะของแต่ละโหมด (เช่น ตรวจยอดเงิน) ให้เพิ่มที่นี่หรือในโมดูลของโหมดนั้น
ของเฟส 1 (date_guard, tools.validate_*, reminder_search) ไม่ย้ายมาที่นี่
"""
import re

REMINDERS = 'reminders'
ACCOUNTS = 'accounts'
ASSETS = 'assets'

_DIGITS = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')

# คำที่บ่งว่าเป็นงานเตือนความจำ (ชนะเสมอ เช่น "เตือนจ่ายค่าไฟ 500 บาท")
_REMINDER_WORDS = ('เตือน', 'นัด', 'ปลุก', 'ประชุม', 'อย่าลืม', 'ลบทิ้ง', 'เลื่อน',
                   'reminder', 'alarm')
# คำถาม/ค้นย้อนหลัง ไม่ใช่การบันทึกรายการ
_QUESTION_WORDS = ('กี่', 'เท่าไหร่', 'เท่าไร', 'ไหม', 'หรือเปล่า', 'ที่ผ่านมา',
                   'ย้อนหลัง', 'ในอดีต', 'ก่อนหน้า', 'ทั้งหมด', 'ยอดรวม', 'รายการ')
_ASSET_RE = re.compile(
    r'(ซื้อ|ขาย|สั่งซื้อ|สับเปลี่ยน)\s*(กองทุน|หุ้น|หลักทรัพย์|etf|ตราสาร|หน่วยลงทุน)')
_AMOUNT_RE = re.compile(r'\d[\d,]*(?:\.\d+)?\s*(?:บาท|฿|baht)|เป็นเงิน\s*\d', re.I)
_MONEY_VERBS = ('จ่าย', 'ซื้อ', 'ใช้จ่าย', 'ค่า', 'ได้รับ', 'รับเงิน', 'โอน',
                'เงินเดือน', 'ถอน', 'ฝาก', 'ปันผล')


def detect_mode(text):
    """คืน 'reminders' / 'accounts' / 'assets' หรือ None ถ้าไม่แน่ใจ"""
    t = (text or '').translate(_DIGITS).lower()
    if not t.strip():
        return None
    if any(w in t for w in _REMINDER_WORDS):
        return REMINDERS
    if any(w in t for w in _QUESTION_WORDS):
        return None
    if _ASSET_RE.search(t):
        return ASSETS
    if _AMOUNT_RE.search(t) and any(v in t for v in _MONEY_VERBS):
        return ACCOUNTS
    return None


def mode_hint(current, text):
    """โหมดที่ควรแนะนำให้สลับ (None = ไม่ต้องเตือน)"""
    detected = detect_mode(text)
    if detected is not None and detected != current:
        return detected
    return None
