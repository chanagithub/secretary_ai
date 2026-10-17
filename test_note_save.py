import json, shortcuts
from urllib.parse import urlencode, quote

SHORTCUT_NAME = 'AI SaveToNote'
MODE = 'new'   # ลอง 'new' ก่อน แล้วค่อยเปลี่ยนเป็น 'append'
TITLE = 'ทดสอบเลขา AI'
BODY = '17 ต.ค. 2026\nเพลงทดสอบ 1\nเพลงทดสอบ 2'

payload = json.dumps({'MODE': MODE, 'TITLE': TITLE, 'BODY': BODY},
                     ensure_ascii=False
q = urlencode({'name': SHORTCUT_NAME,
               'input': 'text',
               'text': payload,
               'x-success': 'pythonista3://',
               'x-cancel': 'pythonista3://'}, quote_via=quote)
shortcuts.open_url('shortcuts://x-callback-url/run-shortcut?' + q)