import shortcuts
from urllib.parse import urlencode, quote

q = urlencode({'name': 'AI SaveToNote',
               'input': 'text',
               'text': 'hello 123',
               'x-success': 'pythonista3://',
               'x-cancel': 'pythonista3://'}, quote_via=quote)
url = 'shortcuts://x-callback-url/run-shortcut?' + q
print(url)
shortcuts.open_url(url)