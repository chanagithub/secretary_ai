"""finance_write.py - เขียนรายการรายรับ/รายจ่ายลงฐานข้อมูล ChanaFinance

SQL และค่าที่เขียนเหมือน _save_income / _save_expense ของแอปเดิมทุกจุด:
  detail_text = ชื่อรายการเป็นข้อความ, detail_id = 0 (ผู้ใช้ต้องการเก็บเป็นข้อความ ไม่เก็บเป็นรหัส)
  year / month แยกจากวันที่ YYYY-MM-DD (ค.ศ.), amount เป็น REAL
ก่อนเขียนตรวจ: ไฟล์มีจริง (กัน sqlite สร้างไฟล์เปล่าใหม่), โครงสร้างตารางครบ, รหัสหมวด/ประเภทชำระมีในไฟล์นี้
หลังเขียนเปิดแถวนั้นกลับมาอ่านด้วยการเชื่อมต่อใหม่และเทียบทุกช่อง

save_record(db_path, rec) -> (ok, ข้อความไทย, row_id)
  rec = {'kind': 'income'|'expense', 'date': 'YYYY-MM-DD', 'detail': str, 'category_id': int,
         'payment_id': int (รายจ่ายเท่านั้น), 'amount': number, 'note': str}
  ok=True เฉพาะเมื่อเขียนและอ่านกลับตรงกันแล้วเท่านั้น (ข้อความ "บันทึกแล้ว" ต้องมาจากผลนี้)
  ok=False และ row_id=None  -> ไม่ได้เขียนอะไรเลย
  ok=False และ row_id มีค่า  -> เขียนแล้วแต่ตรวจกลับไม่ได้/ไม่ตรง ต้องบอกผู้ใช้ให้ตรวจในแอปเดิม
"""
import datetime
import math
import os
import sqlite3

import finance_db as fdb
from debug_log import log as debug_log

INCOME = 'income'
EXPENSE = 'expense'
MAX_AMOUNT = 1000000000.0
_TIMEOUT = 10.0  # วินาทีที่รอถ้าไฟล์ถูกล็อก

_INSERT_INCOME = ("INSERT INTO income (date, year, month, detail_id, detail_text, category_id, amount, note) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
_INSERT_EXPENSE = ("INSERT INTO expense "
                   "(date, year, month, detail_id, detail_text, category_id, payment_type_id, amount, note) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)")


class _Refused(Exception):
    """ไม่ผ่านการตรวจก่อนเขียน (ข้อความไทย)"""


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _prepare(rec):
    """ตรวจและจัดรูปค่าก่อนเขียน คืน dict ใหม่ หรือ raise _Refused"""
    debug_log('finance_write: prepare start')
    if not isinstance(rec, dict):
        raise _Refused('ข้อมูลรายการไม่ถูกต้อง')
    debug_log('finance_write: prepare dict checked')
    kind = rec.get('kind')
    if kind not in (INCOME, EXPENSE):
        raise _Refused('ชนิดรายการไม่ถูกต้อง')
    debug_log('finance_write: prepare kind checked')
    date_str = str(rec.get('date') or '')
    debug_log('finance_write: prepare date text type=%s' % type(rec.get('date')).__name__)
    try:
        day = datetime.date.fromisoformat(date_str)
    except ValueError:
        raise _Refused('วันที่ไม่ถูกต้อง (%s)' % date_str)
    debug_log('finance_write: prepare date parsed')
    if day.isoformat() != date_str:  # กัน '2026-1-5' ให้เก็บเป็นรูปแบบเดียวกับแอปเดิมเสมอ
        raise _Refused('รูปแบบวันที่ต้องเป็น YYYY-MM-DD (%s)' % date_str)
    detail = ' '.join(str(rec.get('detail') or '').split())
    if not detail:
        raise _Refused('ไม่มีชื่อรายการ')
    debug_log('finance_write: prepare detail checked')
    raw_amount = rec.get('amount')
    if isinstance(raw_amount, bool):
        raise _Refused('จำนวนเงินไม่ถูกต้อง')
    try:
        amount = float(raw_amount)
    except (TypeError, ValueError):
        raise _Refused('จำนวนเงินไม่ถูกต้อง')
    debug_log('finance_write: prepare amount parsed')
    if not math.isfinite(amount) or amount <= 0 or amount > MAX_AMOUNT:
        raise _Refused('จำนวนเงินไม่ถูกต้องหรือผิดปกติ (%s)' % raw_amount)
    amount = round(amount, 2)
    if not _is_int(rec.get('category_id')):
        raise _Refused('ยังไม่ได้เลือกหมวด')
    debug_log('finance_write: prepare category checked')
    payment_id = rec.get('payment_id')
    if kind == EXPENSE and not _is_int(payment_id):
        raise _Refused('ยังไม่ได้เลือกประเภทการชำระ')
    debug_log('finance_write: prepare payment checked')
    return {'kind': kind, 'date': date_str, 'year': day.year, 'month': day.month,
            'detail': detail, 'category_id': rec['category_id'],
            'payment_id': payment_id if kind == EXPENSE else None,
            'amount': amount, 'note': str(rec.get('note') or '').strip()}


def _check_target(db_path, r):
    """ตรวจไฟล์/โครงสร้าง/รหัสอ้างอิง (อ่านอย่างเดียว) raise _Refused หรือ FinanceDBError"""
    import os
    if not os.path.isfile(db_path):
        raise _Refused('ไม่พบไฟล์ฐานข้อมูล: %s' % os.path.basename(str(db_path)))
    problems = fdb.check_schema(db_path)
    if any('locked' in p or 'busy' in p for p in problems):  # ไฟล์ถูกใช้อยู่ ไม่ใช่โครงสร้างผิด
        raise _Refused('ไฟล์ฐานข้อมูลกำลังถูกใช้งานอยู่ (ถูกล็อก) ไม่ได้บันทึก ลองใหม่อีกครั้งสักครู่')
    if problems:
        raise _Refused('ไฟล์ %s โครงสร้างไม่ครบ ไม่เขียนข้อมูล: %s'
                       % (os.path.basename(db_path), problems[0]))
    cat_table = 'category_income' if r['kind'] == INCOME else 'category_expense'
    conn = fdb._open_ro(db_path)
    try:
        if conn.execute('SELECT 1 FROM %s WHERE id = ?' % cat_table,
                        (r['category_id'],)).fetchone() is None:
            raise _Refused('ไม่พบหมวดนี้ในไฟล์ที่เลือก กรุณาเลือกหมวดใหม่')
        if r['kind'] == EXPENSE and conn.execute(
                'SELECT 1 FROM payment_type WHERE id = ?', (r['payment_id'],)).fetchone() is None:
            raise _Refused('ไม่พบประเภทการชำระนี้ในไฟล์ที่เลือก กรุณาเลือกใหม่')
    except sqlite3.Error as e:
        raise _Refused('ตรวจรหัสอ้างอิงไม่สำเร็จ: %s' % e)
    finally:
        conn.close()


def _read_back(db_path, kind, row_id):
    conn = fdb._open_ro(db_path)
    try:
        if kind == EXPENSE:
            sql = ('SELECT date, year, month, detail_id, detail_text, category_id, payment_type_id, '
                   'amount, note FROM expense WHERE id = ?')
        else:
            sql = ('SELECT date, year, month, detail_id, detail_text, category_id, NULL, '
                   'amount, note FROM income WHERE id = ?')
        return conn.execute(sql, (row_id,)).fetchone()
    finally:
        conn.close()


def _differences(r, row):
    if row is None:
        return ['ไม่พบแถวที่เพิ่งเขียน']
    keys = ('date', 'year', 'month', 'detail_id', 'detail_text', 'category_id',
            'payment_type_id', 'amount', 'note')
    want = (r['date'], r['year'], r['month'], 0, r['detail'], r['category_id'],
            r['payment_id'], r['amount'], r['note'])
    diffs = []
    for key, expected, got in zip(keys, want, row):
        if key == 'amount':
            same = got is not None and abs(float(got) - expected) < 0.005
        else:
            same = got == expected
        if not same:
            diffs.append(key)
    return diffs


def save_record(db_path, rec):
    debug_log('finance_write: start db=%s' % os.path.basename(str(db_path)))
    try:
        r = _prepare(rec)
        debug_log('finance_write: validated record')
        debug_log('finance_write: checking target')
        _check_target(db_path, r)
        debug_log('finance_write: target checked')
    except _Refused as e:
        return False, str(e), None
    except fdb.FinanceDBError as e:
        return False, str(e), None

    conn = None
    row_id = None
    try:
        debug_log('finance_write: opening writable connection')
        conn = sqlite3.connect(db_path, timeout=_TIMEOUT)
        debug_log('finance_write: writable connection opened')
        cur = conn.cursor()
        if r['kind'] == EXPENSE:
            cur.execute(_INSERT_EXPENSE, (r['date'], r['year'], r['month'], 0, r['detail'],
                                          r['category_id'], r['payment_id'], r['amount'], r['note']))
        else:
            cur.execute(_INSERT_INCOME, (r['date'], r['year'], r['month'], 0, r['detail'],
                                         r['category_id'], r['amount'], r['note']))
        row_id = cur.lastrowid
        debug_log('finance_write: insert executed row_id=%s' % row_id)
        conn.commit()
        debug_log('finance_write: commit completed')
    except sqlite3.Error as e:
        try:
            if conn is not None:
                conn.rollback()
        except sqlite3.Error:
            pass
        debug_log('finance_write: sqlite error: %r' % e)
        return False, 'เขียนฐานข้อมูลไม่สำเร็จ ไม่ได้บันทึก: %s' % e, None
    finally:
        if conn is not None:
            conn.close()
            debug_log('finance_write: writable connection closed')

    try:
        debug_log('finance_write: reading inserted row back')
        diffs = _differences(r, _read_back(db_path, r['kind'], row_id))
        debug_log('finance_write: read-back completed')
    except (sqlite3.Error, fdb.FinanceDBError) as e:
        return (False, 'เขียนแล้วแต่อ่านกลับมาตรวจไม่ได้ (%s) กรุณาเปิดแอป ChanaFinance ตรวจรายการนี้' % e,
                row_id)
    if diffs:
        debug_log('finance_write: read-back differences=%s' % ','.join(diffs))
        return (False, 'เขียนแล้วแต่ข้อมูลที่อ่านกลับไม่ตรง (%s) กรุณาเปิดแอป ChanaFinance ตรวจรายการนี้'
                % ', '.join(diffs), row_id)
    debug_log('finance_write: save verified row_id=%s' % row_id)
    return True, '', row_id
