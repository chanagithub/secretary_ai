"""Call the app's debug_log.log and immediately verify that same file."""
import os
import time
import debug_log

folder = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(folder, 'debug.log')
marker = 'LOGGER_FUNCTION_PROBE %s' % time.strftime('%Y-%m-%d %H:%M:%S')
print('module: %s' % getattr(debug_log, '__file__', '?'))
print('path: %s' % path)

debug_log.log(marker)
with open(path, 'r', encoding='utf-8') as f:
    contents = f.read()
print('LOGGER LINE PRESENT: %s' % (marker in contents))
print('--- final 8 lines ---')
for line in contents.splitlines()[-8:]:
    print(line)
