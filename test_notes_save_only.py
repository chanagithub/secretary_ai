"""test_notes_save_only.py - ทดสอบ send_save เดี่ยว ๆ (ไม่อ่านรายชื่อโน้ตก่อน)
ผลที่ควรได้: แอปสลับไป Shortcuts แล้วกลับ Pythonista และมีโน้ต "ทดสอบส่งอย่างเดียว"
ใหม่ในโฟลเดอร์ เลขา AI (ลบทิ้งได้)
"""
import notes_shortcut

notes_shortcut.send_save('new', 'ทดสอบส่งอย่างเดียว',
                         'ทดสอบสร้างโน้ตจากโมดูล\nบรรทัดที่สอง')
print('ส่งคำสั่งสร้างโน้ตไปยัง Shortcut แล้ว')
