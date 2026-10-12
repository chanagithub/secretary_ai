"""check_finance.py - ตรวจว่าเลขา AI มองเห็นฐานข้อมูล ChanaFinance ถูกต้องไหม (อ่านอย่างเดียว)

วางในโฟลเดอร์ secretary_ai แล้วรันใน Pythonista ถ้าผ่านทุกข้อ ส่งข้อความที่พิมพ์ออกมาให้ผม
(ตัวเลขนับจำนวนแถว ชื่อหมวด และประเภทชำระ ไม่มีจำนวนเงินหรือรายการส่วนตัว)
"""
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import finance_db as fdb

try:
    folder = fdb.find_finance_folder()
except fdb.FinanceDBError as e:
    print('หาโฟลเดอร์ไม่สำเร็จ:', e)
    raise SystemExit

print('โฟลเดอร์ ChanaFinance:', os.path.basename(folder))
files = fdb.list_db_files(folder)
print('ไฟล์ .db ทั้งหมด %d ไฟล์ (ใหม่ -> เก่า):' % len(files))
for f in files:
    stamp = datetime.datetime.fromtimestamp(f['mtime']).strftime('%Y-%m-%d %H:%M')
    print('  -', f['name'], '| แก้ไขล่าสุด', stamp)

default = fdb.guess_default_db(folder)
print('\nไฟล์ที่เลขา AI จะเดาให้:', default['name'] if default else '(ไม่มี)')

for f in files:
    print('\n=== %s ===' % f['name'])
    try:
        problems = fdb.check_schema(f['path'])
        if problems:
            print('โครงสร้างไม่ครบ (เลขา AI จะไม่เขียนไฟล์นี้):')
            for p in problems:
                print('   *', p)
            continue
        print('โครงสร้างครบ')
        data = fdb.read_lists(f['path'])
        print('หมวดรายรับ  (%d): %s' % (len(data['category_income']),
              ', '.join(n for _, n in data['category_income']) or '-'))
        print('หมวดรายจ่าย (%d): %s' % (len(data['category_expense']),
              ', '.join(n for _, n in data['category_expense']) or '-'))
        print('ประเภทชำระ  (%d): %s' % (len(data['payment_type']),
              ', '.join(n for _, n in data['payment_type']) or '-'))
        print('ชื่อรายละเอียดที่บันทึกไว้: รายรับ %d / รายจ่าย %d' % (
            len(data['detail_income']), len(data['detail_expense'])))
    except fdb.FinanceDBError as e:
        print('อ่านไม่สำเร็จ:', e)
print('\nเสร็จ (ไม่มีการเขียนข้อมูลใด ๆ)')
