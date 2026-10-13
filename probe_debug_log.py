"""Directly append and read back a diagnostic line in this folder's debug.log."""
import os
import time

folder = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(folder, 'debug.log')
line = 'DIRECT_WRITE_PROBE %s\n' % time.strftime('%Y-%m-%d %H:%M:%S')
print('target: %s' % path)

try:
    data = line.encode('utf-8')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o666)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    with open(path, 'r', encoding='utf-8') as f:
        tail = f.readlines()[-5:]
    print('WRITE AND READBACK OK')
    for item in tail:
        print(item.rstrip())
except Exception as exc:
    print('DIRECT WRITE FAILED: %r' % exc)
