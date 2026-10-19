"""modes.py - โหมดของ AI เลขา (เตือนความจำ / รายรับรายจ่าย / การลงทุน / โน้ต)

เก็บโหมดล่าสุดใน mode.json (แยกจาก settings.json เพราะ config._save เขียนทับทั้งไฟล์)
ENABLED = โหมดที่เปิดใช้แล้ว; โหมดอื่นกดได้แต่ขึ้น "ยังไม่เปิดใช้" และไม่สลับ
เมื่อทำเฟส 2/3 เสร็จ เพิ่มชื่อโหมดใน ENABLED
"""
import json
import os

REMINDERS = 'reminders'
ACCOUNTS = 'accounts'
ASSETS = 'assets'
NOTES = 'notes'

KEYS = (REMINDERS, ACCOUNTS, ASSETS, NOTES)
LABELS = {REMINDERS: 'เตือนความจำ',
          ACCOUNTS: 'รายรับรายจ่าย',
          ASSETS: 'การลงทุน',
          NOTES: 'โน้ต'}
ENABLED = {REMINDERS, ACCOUNTS, NOTES}

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mode.json')


def label(key):
    return LABELS.get(key, key)


def is_enabled(key):
    return key in ENABLED


def get_mode():
    """โหมดล่าสุดที่เลือก (ถ้าไฟล์เสีย/โหมดยังไม่เปิดใช้ ใช้เตือนความจำ)"""
    try:
        with open(_PATH, 'r', encoding='utf-8') as f:
            key = json.load(f).get('mode')
    except (OSError, ValueError, AttributeError):
        return REMINDERS
    return key if key in ENABLED else REMINDERS


def set_mode(key):
    """สลับโหมด คืน True ถ้าสำเร็จ (โหมดที่ยังไม่เปิดใช้ คืน False และไม่เปลี่ยน)"""
    if key not in ENABLED:
        return False
    tmp = _PATH + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'mode': key}, f, ensure_ascii=False)
        os.replace(tmp, _PATH)
    except OSError:
        return False
    return True
