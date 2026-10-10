# reminders_tool.py
"""
โมดูลสำหรับสร้าง/ดึง รีมายเดอร์ผ่านแอป Reminders ของ iOS
ใช้โมดูล reminders ที่มากับ Pythonista เท่านั้น (ไม่พึ่ง library ภายนอก)

อ้างอิง: https://omz-software.com/pythonista/docs/ios/reminders.html

การออกแบบ:
- รายการที่สร้างจากแอปยังบันทึกในลิสต์ "เลขา AI"
- การอ่านรายการใช้ทุกลิสต์ใน Reminders เพื่อให้ค้นนัดเดิมของผู้ใช้ได้ด้วย
"""

import datetime
import json
from urllib.parse import urlencode
import reminders
from debug_log import log as debug_log

AI_LIST_NAME = "เลขา AI"
URGENT_SHORTCUT_NAME = "สร้าง Urgent Reminder"


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


def _create(calendar, title, notes, due_value, alarm_minutes_before):
    r = reminders.Reminder(calendar)
    r.title = title
    if notes:
        r.notes = notes
    if due_value is not None:
        r.due_date = due_value
        if alarm_minutes_before is not None:
            alarm_time = due_value - datetime.timedelta(minutes=alarm_minutes_before)
            alarm = reminders.Alarm(alarm_time)
            r.alarms = [alarm]
    r.save()
    return r


def _create_all_day(calendar, title, notes, day):
    """สร้างการเตือนแบบ all-day (ไม่มีเวลา) ผ่าน EventKit ด้วย objc_util

    Apple: dueDateComponents ที่ไม่มี hour/minute/second = all-day และต้องตั้ง calendar เป็น gregorian
    iOS ต้องมี startDateComponents เมื่อมี due จึงตั้งทั้งสองเป็นวันเดียวกัน
    """
    from ctypes import c_void_p, byref
    from objc_util import ObjCClass, ObjCInstance, ns

    store = ObjCClass('EKEventStore').alloc().init()
    ek_cal = store.calendarWithIdentifier_(ns(calendar.identifier))
    if ek_cal is None:
        raise RuntimeError('หาลิสต์ "%s" ใน EventKit ไม่เจอ' % AI_LIST_NAME)

    gregorian = ObjCClass('NSCalendar').calendarWithIdentifier_(ns('gregorian'))

    def components():
        c = ObjCClass('NSDateComponents').alloc().init()
        c.setCalendar_(gregorian)
        c.setYear_(day.year)
        c.setMonth_(day.month)
        c.setDay_(day.day)
        return c

    rem = ObjCClass('EKReminder').reminderWithEventStore_(store)
    rem.setTitle_(ns(title))
    if notes:
        rem.setNotes_(ns(notes))
    rem.setCalendar_(ek_cal)
    rem.setStartDateComponents_(components())
    rem.setDueDateComponents_(components())

    err = c_void_p()
    ok = store.saveReminder_commit_error_(rem, True, byref(err))
    if not ok:
        reason = ObjCInstance(err).localizedDescription() if err.value else 'ไม่ทราบสาเหตุ'
        raise RuntimeError('บันทึกไม่สำเร็จ: %s' % reason)


def create_reminder(title, due_date=None, notes=None,
                     alarm_minutes_before=None, calendar=None, has_time=True,
                     urgent_alarm=False):
    """
    สร้างรีมายเดอร์ 1 รายการ แล้วบันทึกเข้าแอป Reminders จริง

    title: ชื่อเรื่อง (string, บังคับ)
    due_date: datetime object วันเวลาที่ต้องทำ (ไม่บังคับ)
    notes: บันทึกเพิ่มเติม (ไม่บังคับ)
    alarm_minutes_before: ตัวเลขนาที ถ้าใส่จะตั้งแจ้งเตือนล่วงหน้าก่อนถึง due_date
                           (ต้องมี due_date ด้วยถึงจะมีผล)
    calendar: ถ้าไม่ระบุ จะใช้ลิสต์ 'เลขา AI' โดยอัตโนมัติ
    has_time: False = บันทึกเฉพาะวัน ไม่กำหนดเวลา (สวิตช์ "เวลา" ในแอป Reminders ปิด)
              โมดูล reminders ของ Pythonista ทำแบบนี้ไม่ได้ (ส่งเป็น 00:00) จึงเขียนผ่าน EventKit
              ตรง ๆ (ทดสอบบน iPhone แล้วด้วย test_allday.py) ถ้าไม่สำเร็จจะ raise ไม่ย้อนไปใช้ 00:00

    urgent_alarm=True จะส่งรายการที่มีเวลาให้ Shortcut ซึ่งเปิด Urgent ไว้
    รายการทั่วไปและรายการ all-day จะสร้างผ่านทางปกติโดยไม่มี Urgent

    คืนค่า: 'shortcut' เมื่อส่งให้ Shortcut, reminders.Reminder object เมื่อสร้างตรง,
    และ None สำหรับ all-day
    """
    if due_date and not has_time:
        if calendar is None:
            calendar = get_ai_calendar()
        day = due_date.date() if isinstance(due_date, datetime.datetime) else due_date
        debug_log('reminders: saving all-day via EventKit')
        _create_all_day(calendar, title, notes, day)
        debug_log('reminders: all-day saved')
        return None

    if urgent_alarm and due_date is not None and has_time:
        try:
            import shortcuts
        except ImportError:
            raise RuntimeError('ต้องรันใน Pythonista เพื่อเรียก Shortcut สร้าง Urgent Reminder')
        due = due_date
        if due.tzinfo is not None:
            due = due.astimezone().replace(tzinfo=None)
        payload = json.dumps({
            'title': title,
            'due': due.strftime('%Y-%m-%d %H:%M'),
            'notes': notes or '',
        }, ensure_ascii=False)
        debug_log('reminders: dispatching timed reminder to shortcut=%s' % URGENT_SHORTCUT_NAME)
        # ใช้ x-callback เพื่อกลับเข้า Pythonista หลัง Shortcut จบ แทนการทิ้งผู้ใช้ไว้ที่ Home
        query = urlencode({
            'name': URGENT_SHORTCUT_NAME,
            'input': 'text',
            'text': payload,
            'x-success': 'pythonista3://',
            'x-cancel': 'pythonista3://',
            'x-error': 'pythonista3://',
        })
        shortcuts.open_url('shortcuts://x-callback-url/run-shortcut?' + query)
        debug_log('reminders: shortcut launched')
        return 'shortcut'

    if calendar is None:
        calendar = get_ai_calendar()
    return _create(calendar, title, notes, due_date, alarm_minutes_before)

def _naive(d):
    """ทำให้เป็นเวลาท้องถิ่นแบบไม่มี timezone (ถ้าระบบคืนมาพร้อม timezone)"""
    if d.tzinfo is not None:
        d = d.astimezone().replace(tzinfo=None)
    return d


def list_reminders_on(day):
    """งานที่ยังไม่เสร็จของวัน 'day' (datetime.date) จากทุกลิสต์ใน Reminders

    คืนค่า: list ของ (due_date: datetime, reminder) เรียงตามเวลา
    """
    items = []
    for r in reminders.get_reminders(completed=False):
        if r.due_date is None:
            continue
        due = _naive(r.due_date)
        if due.date() == day:
            items.append((due, r))
    items.sort(key=lambda x: x[0])
    return items


def list_reminders_between(start, end, status='incomplete'):
    """ดึงรายการจากทุกลิสต์ในช่วง [start, end) ตามสถานะที่ระบุ"""
    completed = False if status == 'incomplete' else True if status == 'completed' else None
    items = []
    for r in reminders.get_reminders(completed=completed):
        if r.due_date is None:
            continue
        due = _naive(r.due_date)
        if start <= due.date() < end:
            items.append((due, r))
    items.sort(key=lambda x: x[0])
    return items


def mark_done(reminder):
    """ติ๊กว่าเสร็จแล้ว (ยังเหลืออยู่ในแอป Reminders ในหมวดที่เสร็จแล้ว กู้คืนได้)"""
    reminder.completed = True
    reminder.save()


def delete_reminder(reminder):
    """ลบถาวร"""
    if not reminders.delete_reminder(reminder):
        raise RuntimeError('ลบรายการไม่สำเร็จ')


def reschedule_reminder(reminder, new_due):
    """เปลี่ยนวัน/เวลาและคงระยะห่างของ alarm เดิมไว้ถ้ามี"""
    old_due = _naive(reminder.due_date) if reminder.due_date else None
    alarm_offsets = []
    try:
        for alarm in reminder.alarms or []:
            alarm_date = _naive(alarm.date)
            if old_due is not None:
                alarm_offsets.append(old_due - alarm_date)
    except Exception:
        alarm_offsets = []
    reminder.due_date = new_due
    if alarm_offsets:
        reminder.alarms = [reminders.Alarm(new_due - offset) for offset in alarm_offsets]
    reminder.save()
    return reminder
