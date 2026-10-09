"""test_allday.py - ทดสอบบน iPhone: สร้างการเตือนแบบ "ไม่ระบุเวลา" จริง (สวิตช์ เวลา ในแอป Reminders ปิด)

เหตุผล: โมดูล reminders ของ Pythonista ส่งวันที่ไปเป็นเวลา 00:00 ทำให้แอป Reminders เปิดสวิตช์เวลาไว้
Apple บอกไว้ว่า (EKReminder.dueDateComponents) ถ้าตั้งวันที่โดยไม่มี hour/minute/second
การเตือนจะเป็นแบบ all-day (ไม่มีเวลา) สคริปต์นี้เรียก EventKit ตรง ๆ ผ่าน objc_util เพื่อลองทำแบบนั้น

รันไฟล์นี้ใน Pythonista (โฟลเดอร์เดียวกับ reminders_tool.py) แล้วเปิดแอป Reminders ลิสต์ "เลขา AI"
ดูวันมะรืนนี้ จะมีรายการทดสอบ 2 รายการ แล้วบอกผมว่า:
  E ทดสอบ E ไม่ระบุเวลา -> สวิตช์ "เวลา" ปิดอยู่ไหม วันที่ถูกไหม
  F ทดสอบ F เวลา 09:00   -> แสดง 09:00 ถูกไหม (เทียบกับ E)
ถ้ารันแล้ว Pythonista เด้งออกไปหน้าโฮม ให้บอกผมด้วยว่าเด้งตอนไหน (ก่อน/หลังข้อความ "สร้าง E")
"""
import datetime
from ctypes import c_void_p, byref

import reminders
from objc_util import ObjCClass, ObjCInstance, ns, load_framework

import reminders_tool


def _all_day_components(day, gregorian):
    """วันที่แบบไม่มี hour/minute/second (ต้องตั้ง calendar เป็น gregorian ไม่งั้น EventKit จะ raise)"""
    comps = ObjCClass('NSDateComponents').alloc().init()
    comps.setCalendar_(gregorian)
    comps.setYear_(day.year)
    comps.setMonth_(day.month)
    comps.setDay_(day.day)
    return comps


def create_all_day(title, day, calendar_identifier, notes=None):
    """สร้างการเตือนแบบ all-day ผ่าน EventKit คืน True ถ้าบันทึกสำเร็จ"""
    try:
        load_framework('EventKit')
    except Exception:
        pass  # โหลดไว้แล้ว หรือไม่มีฟังก์ชันนี้ ก็ข้ามไป
    status = ObjCClass('EKEventStore').authorizationStatusForEntityType_(1)
    print('สถานะสิทธิ์ Reminders (3 = เข้าถึงได้เต็มที่):', status)

    store = ObjCClass('EKEventStore').alloc().init()
    ek_cal = store.calendarWithIdentifier_(ns(calendar_identifier))
    if ek_cal is None:
        raise RuntimeError('หาลิสต์ "เลขา AI" ใน EventKit ไม่เจอ')

    gregorian = ObjCClass('NSCalendar').calendarWithIdentifier_(ns('gregorian'))
    rem = ObjCClass('EKReminder').reminderWithEventStore_(store)
    rem.setTitle_(ns(title))
    if notes:
        rem.setNotes_(ns(notes))
    rem.setCalendar_(ek_cal)
    # iOS ต้องมีวันเริ่มด้วยถ้าตั้งวันกำหนด (ตามเอกสาร Apple) จึงตั้งทั้งสองเป็นวันเดียวกัน
    rem.setStartDateComponents_(_all_day_components(day, gregorian))
    rem.setDueDateComponents_(_all_day_components(day, gregorian))

    err = c_void_p()
    ok = store.saveReminder_commit_error_(rem, True, byref(err))
    if not ok:
        reason = ObjCInstance(err).localizedDescription() if err.value else 'ไม่ทราบสาเหตุ'
        raise RuntimeError('บันทึกไม่สำเร็จ: %s' % reason)
    return True


def _find(cal, title):
    return [r for r in reminders.get_reminders(calendar=cal, completed=False)
            if r.title == title]


def main():
    day = datetime.date.today() + datetime.timedelta(days=2)
    cal = reminders_tool.get_ai_calendar()
    title_e = 'ทดสอบ E ไม่ระบุเวลา'
    title_f = 'ทดสอบ F เวลา 09:00'

    print('กำลังสร้าง E (all-day ผ่าน EventKit) ...')
    try:
        create_all_day(title_e, day, cal.identifier)
        print('สร้าง E สำเร็จ')
    except Exception as e:
        print('สร้าง E ไม่สำเร็จ ->', repr(e))

    print('กำลังสร้าง F (มีเวลา ผ่านโมดูลเดิม) ...')
    try:
        reminders_tool.create_reminder(
            title_f, datetime.datetime(day.year, day.month, day.day, 9, 0))
        print('สร้าง F สำเร็จ')
    except Exception as e:
        print('สร้าง F ไม่สำเร็จ ->', repr(e))

    for title in (title_e, title_f):
        for r in _find(cal, title):
            print('อ่านกลับผ่านโมดูล: %s | due_date = %r' % (title, r.due_date))

    print('\nเปิดแอป Reminders ลิสต์ "เลขา AI" ดูวันที่ %s แล้วดูว่า E กับ F ต่างกันยังไง'
          % day.isoformat())
    input('ดูเสร็จแล้วกด Enter ที่นี่เพื่อลบรายการทดสอบ... ')
    for title in (title_e, title_f):
        for r in _find(cal, title):
            try:
                reminders.delete_reminder(r)
                print('ลบแล้ว:', title)
            except Exception as e:
                print('ลบไม่สำเร็จ (ลบเองในแอป Reminders):', title, repr(e))
    print('จบการทดสอบ')


if __name__ == '__main__':
    main()