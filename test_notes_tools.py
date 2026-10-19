"""test_notes_tools.py - ทดสอบ notes_tools.py บน iPhone (ไม่แตะ Notes ไม่เรียก Shortcut ไม่เรียก AI)
ต้องมี notes_shortcut.py อยู่โฟลเดอร์เดียวกัน
"""
import datetime

import notes_tools as nt

today = datetime.date.today()
src = 'ช่วยบันทึกให้หน่อยครับ ชื่อเพลงที่ซ้อมวันนี้ มีเพลง ก และเพลง ข'

print('1) ตัดคำสั่งนำหน้า:')
print('  ', nt.strip_command(src))

print('2) AI ส่งเนื้อหาตรงคำพูด -> ใช้ของ AI:')
print('  ', nt.validate_call({'content': 'ชื่อเพลงที่ซ้อมวันนี้ มีเพลง ก และเพลง ข',
                              'title': 'เพลงที่ซ้อม'}, src))

print('3) AI แต่งเพิ่ม -> ใช้คำพูดผู้ใช้แทน:')
print('  ', nt.validate_call({'content': 'สรุป: ซ้อมเพลง ก ข สำเร็จ', 'title': 'x'}, src))

print('4) หัวข้อวันที่ต่อท้าย:')
print(nt.build_body('append', 'เนื้อหาตัวอย่าง', today))

print('5) ตรวจชื่อโน้ตซ้อนกัน (ควรเตือน 2 ข้อความ ข้อสุดท้ายว่าง):')
names = ['เพลง', 'เพลงโปรด', 'ทดสอบ', 'ทดสอบ', 'Test1']
for n in ('เพลง', 'ทดสอบ', 'Test1'):
    print('  ', n, '->', repr(nt.conflict_text(n, names)))

print('6) หน้ายืนยัน:')
print(nt.format_confirm_body('new', 'เพลงที่ซ้อม', 'เนื้อหาตัวอย่าง'))
