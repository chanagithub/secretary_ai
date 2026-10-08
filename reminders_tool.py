# reminders_tool.py
"""
โมดูลสำหรับสร้าง/ดึง รีมายเดอร์ผ่านแอป Reminders ของ iOS
ใช้โมดูล reminders ที่มากับ Pythonista เท่านั้น (ไม่พึ่ง library ภายนอก)

อ้างอิง: https://omz-software.com/pythonista/docs/ios/reminders.html

การออกแบบ:
- รีมายเดอร์ที่สร้างจากที่นี่ ทั้งหมดจะอยู่ในลิสต์ (Calendar) ชื่อ "เลขา AI"
  แยกจากลิสต์เดิมของผู้ใช้ เพื่อให้ช่วงทดสอบลบ/ตรวจสอบง่าย ไม่ปนของจริง
"""

import datetime
import reminders

AI_LIST_NAME = "เลขา AI"


def get_ai_calendar():
    """
    หาลิสต์ (Calendar) ชื่อ 'เลขา AI'
    ถ้ายังไม่มีในแอป Reminders จะสร้างใหม่ให้อัตโนมัติ
    คืนค่า: reminders.Calendar object
    """
    for calendar in reminders.get_all_calendars():
        if calendar.title == AI_LIST_NAME:
            return calendar
    new_calendar = reminders.Calendar()
    new_calendar.title = AI_LIST_NAME
    new_calendar.save()
    return new_calendar


def check_access():
    """
    ตรวจว่าแอปเข้าถึง Reminders ได้หรือยัง
    หมายเหตุ: โมดูลนี้ไม่มีฟังก์ชันขอสิทธิ์ตรง ๆ
    ครั้งแรกที่เรียก get_all_calendars() iOS จะเด้ง popup ขอสิทธิ์เอง
    ถ้ากดปฏิเสธ ต้องไปเปิดเองที่ Settings > Pythonista > Reminders
    """
    try:
        calendars = reminders.get_all_calendars()
        return True, len(calendars)
    except Exception as e:
        return False, str(e)


def create_reminder(title, due_date=None, notes=None,
                     alarm_minutes_before=None, calendar=None):
    """
    สร้างรีมายเดอร์ 1 รายการ แล้วบันทึกเข้าแอป Reminders จริง

    title: ชื่อเรื่อง (string, บังคับ)
    due_date: datetime object วันเวลาที่ต้องทำ (ไม่บังคับ)
    notes: บันทึกเพิ่มเติม (ไม่บังคับ)
    alarm_minutes_before: ตัวเลขนาที ถ้าใส่จะตั้งแจ้งเตือนล่วงหน้าก่อนถึง due_date
                           (ต้องมี due_date ด้วยถึงจะมีผล)
    calendar: ถ้าไม่ระบุ จะใช้ลิสต์ 'เลขา AI' โดยอัตโนมัติ

    คืนค่า: reminders.Reminder object ที่บันทึกแล้ว
    """
    if calendar is None:
        calendar = get_ai_calendar()

    r = reminders.Reminder(calendar)
    r.title = title
    if notes:
        r.notes = notes
    if due_date:
        r.due_date = due_date
        if alarm_minutes_before is not None:
            alarm_time = due_date - datetime.timedelta(minutes=alarm_minutes_before)
            alarm = reminders.Alarm(alarm_time)
            r.alarms = [alarm]
    r.save()
    return r