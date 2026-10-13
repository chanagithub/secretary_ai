"""debug_log.py - บันทึกร่องรอยการทำงานลงไฟล์ debug.log (ข้างไฟล์นี้)

ใช้หาสาเหตุที่แอปล่ม: เขียนแล้ว flush + fsync ทุกบรรทัด บรรทัดสุดท้ายในไฟล์
จึงบอกได้ว่าโปรแกรมทำอะไรอยู่ก่อนล่ม เกิน 100 KB จะย้ายไปเป็น debug.log.old
"""
import os
import time
import traceback
import sys

BUILD = 'diagnostic-1'

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug.log')
_MAX_BYTES = 100000


def _console(message):
    try:
        sys.stderr.write('debug_log %s\n' % message)
        sys.stderr.flush()
    except Exception:
        try:
            print('debug_log %s' % message)
        except Exception:
            pass


_console('BUILD=%s loaded module=%s path=%s' % (BUILD, __file__, _PATH))


def log(msg):
    try:
        if os.path.exists(_PATH) and os.path.getsize(_PATH) > _MAX_BYTES:
            os.replace(_PATH, _PATH + '.old')
        with open(_PATH, 'a', encoding='utf-8') as f:
            f.write('%s %s\n' % (time.strftime('%H:%M:%S'), msg))
            f.flush()
            os.fsync(f.fileno())
    except Exception as exc:
        # Keep logging failures visible in Pythonista's console during diagnosis.
        _console('WRITE FAILED path=%s error=%r' % (_PATH, exc))


def log_exc(where):
    log('EXC %s: %s' % (where, traceback.format_exc()))


log('debug_log BUILD=%s ready module=%s path=%s' % (BUILD, __file__, _PATH))
