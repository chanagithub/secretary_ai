# test_reminders.py
"""
สคริปต์ทดสอบโมดูล reminders_tool ด้วยมือ (ยังไม่ต่อ AI)
รันตรง ๆ ใน Pythonista เพื่อตอบคำถามค้างข้อ 5 ใน handoff:
- สิทธิ์เข้าถึงใช้ได้จริงไหม
- รีมายเดอร์ที่มีวันเวลาขึ้นในแอปปฏิทินด้วยหรือไม่
"""

import datetime
import reminders_tool as rt

print("=" * 40)
print("ขั้นที่ 1: ตรวจสิทธิ์เข้าถึง Reminders")
ok, info = rt.check_access()
if ok:
    print("เข้าถึงได้ พบลิสต์ทั้งหมด {} ลิสต์".format(info))
else:
    print("เข้าถึงไม่ได้:", info)
    print("ถ้าเพิ่งรันครั้งแรก กด 'OK' ที่ popup ขอสิทธิ์ของ iOS แล้วรันสคริปต์นี้ใหม่")
    raise SystemExit

print()
print("=" * 40)
print("ขั้นที่ 2: หา/สร้างลิสต์ 'เลขา AI'")
calendar = rt.get_ai_calendar()
print("ใช้ลิสต์:", calendar.title)

print()
print("=" * 40)
print("ขั้นที่ 3: สร้างรีมายเดอร์ทดสอบ")
# ตั้งเวลา 2 นาทีจากตอนนี้ เพื่อให้เห็นการแจ้งเตือนเร็วตอนทดสอบ
test_due = datetime.datetime.now() + datetime.timedelta(minutes=2)
test_reminder = rt.create_reminder(
    title="[ทดสอบ] ช่างมาซ่อมแอร์",
    due_date=test_due,
    notes="รีมายเดอร์นี้สร้างจาก test_reminders.py เพื่อทดสอบเท่านั้น",
    alarm_minutes_before=1,
    calendar=calendar,
)
print("สร้างแล้ว ชื่อเรื่อง:", test_reminder.title)
print("วันเวลาครบกำหนด:", test_reminder.due_date)
print("จำนวนการเตือน:", len(test_reminder.alarms))

print()
print("=" * 40)
print("ขั้นที่ 4: โปรดเช็กด้วยตัวเอง")
print("1. เปิดแอป Reminders -> ลิสต์ 'เลขา AI' -> ควรเห็น '[ทดสอบ] ช่างมาซ่อมแอร์'")
print("2. เปิดแอปปฏิทิน -> วันที่ {} -> ควรเห็นรายการนี้ด้วย".format(
    test_due.strftime("%d/%m/%Y")))
print("3. รอดูว่ามี notification เด้งขึ้นก่อนเวลาจริง 1 นาทีไหม")
input("เช็กเสร็จแล้ว กด Enter เพื่อลบรีมายเดอร์ทดสอบทิ้ง...")

print()
print("=" * 40)
print("ขั้นที่ 5: ลบรีมายเดอร์ทดสอบ")
try:
    test_reminder.delete()
    print("ลบเรียบร้อย")
except AttributeError:
    print("เวอร์ชันนี้ไม่มีเมธอด delete() ตรง ๆ")
    print("กรุณาลบมือ: เปิด Reminders -> ลิสต์ 'เลขา AI' -> ปัดซ้ายที่รายการทดสอบ -> Delete")
except Exception as e:
    print("ลบไม่สำเร็จ:", e)
    print("กรุณาลบมือจากแอป Reminders")

print()
print("ทดสอบเสร็จสิ้น")