"""test_notime.py - ทดสอบบน iPhone: บันทึกการเตือนแบบ "ไม่ระบุเวลา" ได้จริงไหม

รันไฟล์นี้ใน Pythonista (โฟลเดอร์เดียวกับ reminders_tool.py) แล้วเปิดแอป Reminders ดูลิสต์ "เลขา AI"
จะมีรายการทดสอบ 3 รายการของวันมะรืนนี้ แล้วบอกผมว่าแต่ละอันแสดงยังไง:
  A ทดสอบ A ไม่ระบุเวลา  -> ควรแสดงเฉพาะวัน ไม่มีเวลา
  B ทดสอบ B เวลา 18:30   -> ควรแสดงเวลา 18:30 ของวันมะรืนนี้ (ไม่ใช่วันถัดไป)
  C ทดสอบ C เวลา 09:00   -> ควรแสดงเวลา 09:00 ของวันมะรืนนี้
ตอนท้ายสคริปต์จะทดสอบ "ติ๊กเสร็จ" กับ C แล้วลบรายการทดสอบทั้งหมดให้เอง
"""
import datetime

import reminders

import reminders_tool


def main():
    day = datetime.date.today() + datetime.timedelta(days=2)
    midnight = datetime.datetime(day.year, day.month, day.day)
    tests = [
        ('ทดสอบ A ไม่ระบุเวลา', midnight, False),
        ('ทดสอบ B เวลา 18:30', midnight.replace(hour=18, minute=30), True),
        ('ทดสอบ C เวลา 09:00', midnight.replace(hour=9), True),
    ]
    created = []
    for title, due, has_time in tests:
        try:
            r = reminders_tool.create_reminder(title, due, has_time=has_time)
        except Exception as e:
            print('สร้างไม่สำเร็จ:', title, '->', repr(e))
            continue
        created.append(r)
        print('สร้างแล้ว: %s | อ่านกลับ due_date = %r' % (title, r.due_date))

    print('\nเปิดแอป Reminders ลิสต์ "เลขา AI" ดูวันที่ %s แล้วจดไว้ว่า A, B, C แสดงยังไง'
          % day.isoformat())
    input('ดูเสร็จแล้วกด Enter ที่นี่เพื่อทดสอบติ๊กเสร็จและลบรายการทดสอบ... ')

    if created:
        target = created[-1]
        try:
            reminders_tool.mark_done(target)
            done_titles = [x.title for x in reminders.get_reminders(
                calendar=reminders_tool.get_ai_calendar(), completed=True)]
            print('ติ๊กเสร็จ "%s": %s' % (
                target.title,
                'พบในรายการที่เสร็จแล้ว' if target.title in done_titles
                else 'ไม่พบในรายการที่เสร็จแล้ว'))
        except Exception as e:
            print('ติ๊กเสร็จไม่สำเร็จ ->', repr(e))

    for r in created:
        try:
            reminders_tool.delete_reminder(r)
            print('ลบแล้ว:', r.title)
        except Exception as e:
            print('ลบไม่สำเร็จ (ลบเองในแอป Reminders):', r.title, repr(e))
    print('จบการทดสอบ')


if __name__ == '__main__':
    main()