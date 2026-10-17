import json, clipboard, shortcuts, time
from urllib.parse import urlencode, quote

payload = json.dumps({'MODE': 'new', 'TITLE': 'ทดสอบเลขา AI',
                      'BODY': '17 ต.ค. 2026\nเพลงทดสอบ 1'},
                     ensure_ascii=False)
MARK = '__WAITING__'
clipboard.set(MARK)
q = urlencode({'name': 'AI SaveToNote',
               'input': 'text',
               'text': payload,
               'x-success': 'pythonista3://',
               'x-cancel': 'pythonista3://'}, quote_via=quote)
shortcuts.open_url('shortcuts://x-callback-url/run-shortcut?' + q)
for _ in range(40):
    time.sleep(0.5)
    t = clipboard.get()
    if t and t != MARK:
        print('Shortcut ได้รับ:', repr(t))
        break
else:
    print('หมดเวลา: ไม่ได้รับอะไร')