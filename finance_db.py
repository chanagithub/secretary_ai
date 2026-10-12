"""finance_db.py - อ่านฐานข้อมูลของ ChanaFinance (อ่านอย่างเดียว ไม่เขียนอะไรทั้งสิ้น)

ใช้โดยโหมดรายรับรายจ่ายของเลขา AI (การเขียนข้อมูลจะแยกไว้อีกโมดูลในขั้นถัดไป)
- find_finance_folder(): หาโฟลเดอร์ ChanaFinance ที่เป็น "พี่น้อง" ของโฟลเดอร์เลขา AI
  โดยดูจากไฟล์ income_entry.py + expense_entry.py (หรือกำหนดชื่อเองที่ APP_FOLDER_NAME)
- list_db_files(folder): ไฟล์ .db ในโฟลเดอร์ (เหมือน main.py ของ ChanaFinance) ใหม่ -> เก่า
- guess_default_db(folder): ไฟล์ที่เลขา AI ใช้ล่าสุด ถ้าไม่มีใช้ไฟล์ที่แก้ไขล่าสุด
- check_schema(db_path): ตรวจว่าตาราง/คอลัมน์ครบเท่าที่แอปเดิมใช้ ถ้าไม่ครบห้ามเขียน
- read_lists(db_path): หมวดรายรับ/รายจ่าย ประเภทชำระ ชื่อรายละเอียด
  (รหัส id เป็นของไฟล์นั้นเท่านั้น ห้ามเอาไปใช้ข้ามไฟล์)
- find_by_name(items, text): หารายการที่ชื่อตรงกันทุกตัวอักษร (ไม่สนช่องว่างเกิน/ตัวพิมพ์ใหญ่เล็ก)
"""
import json
import os
import sqlite3
import urllib.parse

# ถ้าหาโฟลเดอร์อัตโนมัติไม่เจอ (หรือมีหลายโฟลเดอร์ที่คล้ายกัน) ใส่ชื่อโฟลเดอร์ ChanaFinance ที่นี่
APP_FOLDER_NAME = None

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
_STATE_PATH = os.path.join(_HERE, 'finance_state.json')
_MARKERS = ('income_entry.py', 'expense_entry.py')

DETAIL_INCOME = 'รายรับ'
DETAIL_EXPENSE = 'รายจ่าย'

# คอลัมน์ที่แอปเดิม (ChanaFinance) ใช้จริง: ดูจาก chanafunction.create_tables / db_manager.TABLES
REQUIRED_COLUMNS = {
    'category_income': ('id', 'name'),
    'category_expense': ('id', 'name'),
    'payment_type': ('id', 'name'),
    'detail_master': ('id', 'detail_name', 'type'),
    'income': ('id', 'date', 'year', 'month', 'detail_id', 'detail_text',
               'category_id', 'amount', 'note'),
    'expense': ('id', 'date', 'year', 'month', 'detail_id', 'detail_text',
                'category_id', 'payment_type_id', 'amount', 'note'),
}


class FinanceDBError(Exception):
    """ข้อความเป็นภาษาไทย แสดงให้ผู้ใช้อ่านได้เลย"""


# ---------- หาโฟลเดอร์ / ไฟล์ ----------
def find_finance_folder():
    if APP_FOLDER_NAME:
        path = os.path.join(_PARENT, APP_FOLDER_NAME)
        if os.path.isdir(path):
            return path
        raise FinanceDBError('ไม่พบโฟลเดอร์ "%s" ข้าง ๆ โฟลเดอร์เลขา AI' % APP_FOLDER_NAME)
    try:
        names = sorted(os.listdir(_PARENT))
    except OSError as e:
        raise FinanceDBError('อ่านโฟลเดอร์แม่ไม่ได้: %s' % e)
    found = []
    for name in names:
        path = os.path.join(_PARENT, name)
        if path == _HERE or not os.path.isdir(path):
            continue
        if all(os.path.isfile(os.path.join(path, m)) for m in _MARKERS):
            found.append(path)
    if len(found) == 1:
        return found[0]
    if not found:
        raise FinanceDBError('ไม่พบโฟลเดอร์ ChanaFinance ข้าง ๆ โฟลเดอร์เลขา AI '
                             '(ต้องมี income_entry.py และ expense_entry.py)')
    raise FinanceDBError('พบหลายโฟลเดอร์ที่ดูเหมือน ChanaFinance: %s — '
                         'ให้ใส่ชื่อที่ถูกต้องใน APP_FOLDER_NAME ของ finance_db.py'
                         % ', '.join(os.path.basename(p) for p in found))


def list_db_files(folder):
    """[{'name','path','mtime'}] ใหม่ -> เก่า (เฉพาะไฟล์ .db ในโฟลเดอร์นั้น เหมือน main.py)"""
    try:
        names = os.listdir(folder)
    except OSError as e:
        raise FinanceDBError('อ่านโฟลเดอร์ไม่ได้: %s' % e)
    files = []
    for name in names:
        path = os.path.join(folder, name)
        if name.endswith('.db') and os.path.isfile(path):
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            files.append({'name': name, 'path': path, 'mtime': mtime})
    files.sort(key=lambda f: (-f['mtime'], f['name']))
    return files


# ---------- จำไฟล์ที่ใช้ล่าสุด (ChanaFinance ไม่ได้จำไว้ให้) ----------
def get_last_db_name():
    try:
        with open(_STATE_PATH, 'r', encoding='utf-8') as f:
            name = json.load(f).get('last_db')
    except (OSError, ValueError, AttributeError):
        return None
    return name if isinstance(name, str) and name else None


def set_last_db_name(name):
    tmp = _STATE_PATH + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'last_db': name}, f, ensure_ascii=False)
        os.replace(tmp, _STATE_PATH)
    except OSError:
        return False
    return True


def guess_default_db(folder):
    """คืน dict ไฟล์ (จาก list_db_files) หรือ None ถ้าไม่มีไฟล์ .db เลย"""
    files = list_db_files(folder)
    if not files:
        return None
    last = get_last_db_name()
    for f in files:
        if f['name'] == last:
            return f
    return files[0]  # แก้ไขล่าสุด


# ---------- เปิดแบบอ่านอย่างเดียว ----------
def _open_ro(db_path):
    """mode=ro: เขียนไม่ได้แม้โค้ดผิด และไม่สร้างไฟล์ใหม่ถ้าไม่มีไฟล์"""
    uri = 'file:' + urllib.parse.quote(os.path.abspath(db_path)) + '?mode=ro'
    try:
        return sqlite3.connect(uri, uri=True)
    except sqlite3.Error as e:
        raise FinanceDBError('เปิดไฟล์ฐานข้อมูลไม่ได้: %s (%s)' % (os.path.basename(db_path), e))


def check_schema(db_path):
    """คืนรายการปัญหา (ข้อความไทย) ถ้าว่าง = โครงสร้างครบตามที่แอปเดิมใช้"""
    problems = []
    conn = _open_ro(db_path)
    try:
        for table, needed in REQUIRED_COLUMNS.items():
            try:
                cols = [row[1] for row in conn.execute('PRAGMA table_info(%s)' % table)]
            except sqlite3.Error as e:
                problems.append('อ่านตาราง %s ไม่ได้: %s' % (table, e))
                continue
            if not cols:
                problems.append('ไม่มีตาราง %s' % table)
                continue
            for col in needed:
                if col not in cols:
                    problems.append('ตาราง %s ไม่มีคอลัมน์ %s' % (table, col))
    finally:
        conn.close()
    return problems


def read_lists(db_path):
    """อ่านรายการอ้างอิงของไฟล์นี้ (ใช้ได้เฉพาะไฟล์นี้)"""
    conn = _open_ro(db_path)
    try:
        def pairs(sql, args=()):
            return [(r[0], r[1]) for r in conn.execute(sql, args) if r[1]]

        def names(sql, args=()):
            return [r[0] for r in conn.execute(sql, args) if r[0]]

        try:
            return {
                'category_income': pairs('SELECT id, name FROM category_income ORDER BY name'),
                'category_expense': pairs('SELECT id, name FROM category_expense ORDER BY name'),
                'payment_type': pairs('SELECT id, name FROM payment_type ORDER BY name'),
                'detail_income': names('SELECT detail_name FROM detail_master '
                                       'WHERE type = ? ORDER BY detail_name', (DETAIL_INCOME,)),
                'detail_expense': names('SELECT detail_name FROM detail_master '
                                        'WHERE type = ? ORDER BY detail_name', (DETAIL_EXPENSE,)),
            }
        except sqlite3.Error as e:
            raise FinanceDBError('อ่านรายการอ้างอิงไม่สำเร็จ: %s' % e)
    finally:
        conn.close()


def _norm(text):
    return ' '.join(str(text or '').split()).casefold()


def find_by_name(items, text):
    """items = [(id, name)] คืน (id, name) ตัวที่ชื่อตรงกัน ไม่เจอคืน None"""
    target = _norm(text)
    if not target:
        return None
    for item in items:
        if _norm(item[1]) == target:
            return item
    return None
