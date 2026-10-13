"""Print the active Pythonista debug.log path and its newest lines."""
import os
import time

folder = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(folder, 'debug.log')
print('DEBUG LOG CHECK')
print('script folder: %s' % folder)
print('log path: %s' % path)

try:
    stat = os.stat(path)
    print('modified: %s' % time.strftime(
        '%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)))
    print('size: %s bytes' % stat.st_size)
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    print('--- last 15 lines ---')
    for line in lines[-15:]:
        print(line.rstrip())
except Exception as exc:
    print('READ FAILED: %r' % exc)
