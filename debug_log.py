"""debug_log.py - บันทึกร่องรอยการทำงานลงไฟล์ debug.log (ข้างไฟล์นี้)

ใช้หาสาเหตุที่แอปล่ม: เขียนแล้ว flush + fsync ทุกบรรทัด บรรทัดสุดท้ายในไฟล์
จึงบอกได้ว่าโปรแกรมทำอะไรอยู่ก่อนล่ม เกิน 100 KB จะย้ายไปเป็น debug.log.old
"""
import os
import time
import traceback

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug.log')
_MAX_BYTES = 100000


def log(msg):
    try:
        if os.path.exists(_PATH) and os.path.getsize(_PATH) > _MAX_BYTES:
            os.replace(_PATH, _PATH + '.old')
        with open(_PATH, 'a', encoding='utf-8') as f:
            f.write('%s %s\n' % (time.strftime('%H:%M:%S'), msg))
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        pass  # การบันทึก log ต้องไม่ทำให้แอปพัง


def log_exc(where):
    log('EXC %s: %s' % (where, traceback.format_exc()))