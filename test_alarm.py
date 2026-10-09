"""test_alarm.py - ทดสอบบน iPhone: การเตือนที่มีเวลา "เด้งแจ้งเตือน/มีเสียง" จริงไหม

เอกสาร Pythonista บอกว่าตั้งวันกำหนด (due_date) อย่างเดียวจะไม่มีแจ้งเตือน ต้องเพิ่ม Alarm ด้วย
สคริปต์นี้สร้างการเตือน 2 รายการในลิสต์ "เลขา AI":
  X ทดสอบ X มี Alarm   -> อีก 3 นาที (ตั้ง due_date + Alarm เวลาเดียวกัน)
  Y ทดสอบ Y ไม่มี Alarm -> อีก 4 นาที (ตั้งเฉพาะ due_date เหมือนที่แอปทำอยู่ตอนนี้)
จากนั้นล็อกหน้าจอ (หรือวางไว้เฉย ๆ) รอถึงเวลา แล้วบอกผมว่า X, Y เด้งแจ้งเตือนมีเสียงไหม
ถ้าเสร็จแล้วกด Enter ที่คอนโซล สคริปต์จะลบรายการทดสอบให้
"""
import datetime

import reminders

import reminders_tool


def main():
    cal = reminders_tool.get_ai_calendar()
    now = datetime.datetime.now().replace(second=0, microsecond=0)
    t_x = now + datetime.timedelta(minutes=3)
    t_y = now + datetime.timedelta(minutes=4)
    created = []

    rx = reminders.Reminder(cal)
    rx.title = 'ทดสอบ X มี Alarm'
    rx.due_date = t_x
    alarm = reminders.Alarm()
    alarm.date = t_x
    rx.alarms = [alarm]
    rx.save()
    created.append(rx)

    ry = reminders.Reminder(cal)
    ry.title = 'ทดสอบ Y ไม่มี Alarm'
    ry.due_date = t_y
    ry.save()
    created.append(ry)

    print('X จะถึงเวลา %s (มี Alarm)' % t_x.strftime('%H:%M'))
    print('Y จะถึงเวลา %s (ไม่มี Alarm)' % t_y.strftime('%H:%M'))
    print('รอถึงเวลา แล้วดูว่า X, Y เด้งแจ้งเตือนไหม มีเสียงไหม')
    input('ทดสอบเสร็จแล้วกด Enter เพื่อลบรายการทดสอบ... ')
    for r in created:
        try:
            reminders.delete_reminder(r)
            print('ลบแล้ว:', r.title)
        except Exception as e:
            print('ลบไม่สำเร็จ (ลบเองในแอป Reminders):', r.title, repr(e))


if __name__ == '__main__':
    main()