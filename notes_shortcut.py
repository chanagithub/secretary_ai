"""notes_shortcut.py - ตัวเชื่อมโหมดโน้ตกับ Apple Notes ผ่าน Shortcuts

ใช้เฉพาะโฟลเดอร์ "เลขา AI" (On My iPhone) การเลือกโฟลเดอร์ทำอยู่ใน Shortcut

  NoteListReader(on_done, on_error).start()
      เปิด Shortcut LIST_SHORTCUT_NAME ให้คัดลอกชื่อโน้ตไปคลิปบอร์ด แล้วรอ/อ่านจากคลิปบอร์ด
      สำเร็จ -> on_done(names) (names = list ชื่อโน้ต เรียงตามที่ Shortcut ส่งมา, ว่างได้)
      ไม่สำเร็จ -> on_error(ข้อความภาษาไทย)
      ไม่บล็อกหน้าจอ: ใช้ ui.delay วนอ่านทุก 0.5 วินาที (callback ต้องเป็น bound method)
      ผลข้างเคียง: เขียนทับคลิปบอร์ดของผู้ใช้ และ iOS จะถามสิทธิ์ paste ต้องกด Allow Paste

  send_save(mode, title, body)
      ส่ง JSON {MODE, TITLE, BODY} (key ตัวพิมพ์ใหญ่ ตรงกับ Shortcut AI SaveToNote)
      mode = 'new' สร้างโน้ตใหม่ / 'append' ต่อท้ายโน้ตเดิม
      คืนทันทีหลังเปิด Shortcut: Python ยืนยันไม่ได้ว่าโน้ตถูกสร้าง/ต่อท้ายจริง

ชื่อ Shortcut ต้องตรงทุกตัวอักษรรวมวรรณยุกต์ แก้ที่ค่าคงที่ด้านล่างที่เดียว
"""
import json
import time
from urllib.parse import urlencode, quote

import ui

LIST_SHORTCUT_NAME = 'ทดสอบรายชื่อโน้ต'
SAVE_SHORTCUT_NAME = 'AI SaveToNote'
FOLDER_NAME = 'เลขา AI'
MODES = ('new', 'append')

_MARK = '__WAITING__'
_POLL_SECONDS = 0.5
_TIMEOUT_SECONDS = 30


class NotesShortcutError(Exception):
    """ข้อผิดพลาดที่มีข้อความภาษาไทยพร้อมแสดงให้ผู้ใช้อ่าน"""


def _run_url(name, extra):
    query = {'name': name}
    query.update(extra)
    query['x-success'] = 'pythonista3://'  # กลับ Pythonista เองหลัง Shortcut จบ
    query['x-cancel'] = 'pythonista3://'
    # quote_via=quote: ต้องเป็น %20 ไม่ใช่ '+' (ชื่อ Shortcut และข้อความมีช่องว่าง)
    return 'shortcuts://x-callback-url/run-shortcut?' + urlencode(query, quote_via=quote)


def build_save_url(mode, title, body):
    """สร้าง URL เรียก Shortcut บันทึกโน้ต (ตรวจค่าก่อน ไม่ผ่านจะ raise NotesShortcutError)"""
    if mode not in MODES:
        raise NotesShortcutError('โหมดบันทึกโน้ตไม่ถูกต้อง: %s' % mode)
    title = ' '.join(str(title or '').split())
    body = str(body or '').strip()
    if not title:
        raise NotesShortcutError('ชื่อโน้ตว่างไม่ได้')
    if not body:
        raise NotesShortcutError('เนื้อหาโน้ตว่างไม่ได้')
    payload = json.dumps({'MODE': mode, 'TITLE': title, 'BODY': body},
                         ensure_ascii=False)
    return _run_url(SAVE_SHORTCUT_NAME, {'input': 'text', 'text': payload})


def send_save(mode, title, body):
    url = build_save_url(mode, title, body)
    try:
        import shortcuts
    except ImportError:
        raise NotesShortcutError('ต้องรันใน Pythonista เพื่อเรียก Shortcut บันทึกโน้ต')
    shortcuts.open_url(url)


def parse_names(text):
    """แยกข้อความจากคลิปบอร์ด (ชื่อโน้ตบรรทัดละชื่อ) เป็น list ตัดบรรทัดว่างและช่องว่างหัวท้าย"""
    names = []
    for line in str(text or '').replace('\r', '\n').split('\n'):
        name = line.strip()
        if name:
            names.append(name)
    return names


class NoteListReader:
    def __init__(self, on_done, on_error):
        self._on_done = on_done
        self._on_error = on_error
        self._deadline = 0
        self._active = False

    def start(self):
        if self._active:
            return
        try:
            import clipboard
            import shortcuts
        except ImportError:
            self._on_error('ต้องรันใน Pythonista เพื่ออ่านรายชื่อโน้ต')
            return
        self._active = True
        self._deadline = time.time() + _TIMEOUT_SECONDS
        try:
            clipboard.set(_MARK)  # ตัวหมาย แยกว่า Shortcut เขียนค่าใหม่มาแล้วหรือยัง
            shortcuts.open_url(_run_url(LIST_SHORTCUT_NAME, {}))
        except Exception as e:
            self._fail('เรียก Shortcut อ่านรายชื่อโน้ตไม่สำเร็จ: %s' % e)
            return
        ui.delay(self._poll, _POLL_SECONDS)

    def cancel(self):
        self._active = False

    def _poll(self):
        if not self._active:
            return
        import clipboard
        try:
            value = clipboard.get()
        except Exception as e:
            self._fail('อ่านคลิปบอร์ดไม่ได้: %s' % e)
            return
        # ตรวจค่าก่อนตรวจเวลา: ตอนผู้ใช้สลับไป Shortcuts แอปอาจหยุดชั่วคราว
        # พอกลับมา ค่าใหม่อาจมาถึงแล้วแม้เกินเวลา
        if value is not None and value != _MARK:
            self._active = False
            try:
                clipboard.set('')  # ไม่ทิ้งรายชื่อโน้ตค้างในคลิปบอร์ด
            except Exception:
                pass
            self._on_done(parse_names(value))
            return
        if time.time() > self._deadline:
            self._fail('ไม่ได้รับรายชื่อโน้ตจาก Shortcut ภายใน %d วินาที '
                       '(Shortcut ไม่ทำงาน หรือกด Don\'t Allow Paste)' % _TIMEOUT_SECONDS)
            return
        ui.delay(self._poll, _POLL_SECONDS)

    def _fail(self, message):
        self._active = False
        self._on_error(message)
