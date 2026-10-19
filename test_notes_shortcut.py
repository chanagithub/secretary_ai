"""test_notes_shortcut.py - ทดสอบ notes_shortcut.py บน iPhone (วางในโฟลเดอร์ secretary_ai)

ขั้นที่ 1 (ค่าเริ่มต้น): อ่านรายชื่อโน้ตในโฟลเดอร์ เลขา AI แล้วพิมพ์ออกมา
ขั้นที่ 2: เปลี่ยน DO_SAVE = True จะสร้างโน้ตทดสอบใหม่ 1 โน้ตในโฟลเดอร์ เลขา AI (ลบทิ้งได้)
"""
import time

import notes_shortcut

DO_SAVE = False


class Tester:
    def __init__(self):
        self.finished = False

    def on_done(self, names):
        print('ได้ %d รายชื่อ:' % len(names))
        for i, name in enumerate(names, 1):
            print('%2d. %s' % (i, name))
        self.finished = True
        if DO_SAVE:
            notes_shortcut.send_save('new', 'ทดสอบโมดูล notes_shortcut',
                                     'ทดสอบสร้างโน้ตจากโมดูล\nบรรทัดที่สอง')
            print('ส่งคำสั่งสร้างโน้ตไปยัง Shortcut แล้ว')

    def on_error(self, message):
        print('ผิดพลาด:', message)
        self.finished = True


t = Tester()
reader = notes_shortcut.NoteListReader(t.on_done, t.on_error)
reader.start()
waited = 0
while not t.finished and waited < 45:  # ตัวจับเวลาของ ui.delay ทำงานในเธรดหลัก ลูปนี้แค่รอให้สคริปต์ไม่จบก่อน
    time.sleep(0.2)
    waited += 0.2
if not t.finished:
    print('สคริปต์รอเกินเวลา')
