import time, clipboard, shortcuts
from urllib.parse import urlencode, quote

SHORTCUT_NAME = 'ทดสอบรายชื่อโน้ต'
MARK = '__WAITING__'
MAX_TRIES = 40      # 40 รอบ x 0.5 วินาที = รอสูงสุด 20 วินาที
INTERVAL = 0.5

# 1) ตั้งคลิปบอร์ดเป็นตัวหมาย เพื่อแยกว่า Shortcut เขียนค่าใหม่มาแล้วหรือยัง
clipboard.set(MARK)

# 2) เรียก Shortcut แล้วให้กลับมา Pythonista เอง
q = urlencode({'name': SHORTCUT_NAME,
               'x-success': 'pythonista3://',
               'x-cancel': 'pythonista3://'}, quote_via=quote)
shortcuts.open_url('shortcuts://x-callback-url/run-shortcut?' + q)

# 3) วนอ่านคลิปบอร์ดจนค่าเปลี่ยน
result = None
for i in range(MAX_TRIES):
    time.sleep(INTERVAL)
    try:
        v = clipboard.get()
    except Exception as e:
        print('อ่านคลิปบอร์ดไม่ได้:', e)
        break
    if v and v != MARK:
        result = v
        break

if result is None:
    print('หมดเวลา: คลิปบอร์ดไม่เปลี่ยน (Shortcut ไม่ทำงาน หรือกด Don\'t Allow Paste)')
else:
    names = [n.strip() for n in result.split('\n') if n.strip()]
    print('ได้ %d รายชื่อ:' % len(names))
    for n, name in enumerate(names, 1):
        print('%2d. %s' % (n, name))
