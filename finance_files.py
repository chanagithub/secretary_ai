"""finance_files.py - สั่ง "เปลี่ยนไฟล์" ในโหมดรายรับรายจ่าย

พิมพ์/พูดว่า เปลี่ยนไฟล์ / สลับไฟล์ / เลือกไฟล์ -> ขึ้นรายการไฟล์ .db ในโฟลเดอร์ ChanaFinance ให้ผู้ใช้เลือกเอง
ไม่เรียก AI และไม่เขียนฐานข้อมูล (แค่เปลี่ยนตัวชี้ไฟล์ที่จำไว้ใน finance_state.json)
ทั้งการบันทึกรายการและสรุปยอดจะใช้ไฟล์นี้ต่อไป ข้อความผลลัพธ์มาจากโค้ดเท่านั้น
callback เป็น bound method + ui.delay(เมธอด, 0.3) ตามบทเรียนกันล่ม
"""
import ui
import config
import finance_db as fdb
from finance_overlays import ListPickOverlay
from debug_log import log as debug_log

_SWITCH_WORDS = ('เปลี่ยนไฟล์', 'สลับไฟล์', 'เลือกไฟล์', 'ใช้ไฟล์อื่น', 'ไฟล์อื่น')
_MAX_LEN = 40  # ประโยคยาวมักเป็นเรื่องอื่น (เช่น รายการจ่ายเงิน) ไม่ใช่คำสั่งเปลี่ยนไฟล์


def is_switch_request(text):
    value = ''.join(str(text or '').split())
    return 0 < len(value) <= _MAX_LEN and any(w in value for w in _SWITCH_WORDS)


class FileSwitcher:
    def __init__(self, host, text):
        self.host = host
        self.text = text
        self.folder = None
        self.current = None
        self._pick = None
        self.done = False

    def show(self):
        host = self.host
        host._file_switcher = self  # เก็บไว้ให้อยู่จนจบ
        host._live = {'time': config.now_text(), 'model': config.get_current_model(),
                      'user': self.text, 'ai': '', 'status': 'live'}
        try:
            self.folder = fdb.find_finance_folder()
            files = fdb.list_db_files(self.folder)
        except fdb.FinanceDBError as e:
            self.finish('เปลี่ยนไฟล์ไม่ได้: %s' % e)
            return
        if not files:
            self.finish('ไม่พบไฟล์ .db ในโฟลเดอร์ ChanaFinance')
            return
        info = fdb.guess_default_db(self.folder)
        self.current = info['name'] if info else None
        items = [(f['name'] + (' (ใช้อยู่)' if f['name'] == self.current else ''), f['name'])
                 for f in files]
        host.show_overlay(ListPickOverlay('เลือกไฟล์ข้อมูล', items, self.on_pick, self.on_cancel))

    def on_pick(self, value):
        self._pick = value
        ui.delay(self.do_pick, 0.3)

    def do_pick(self):
        try:
            self._switch(self._pick)
        except Exception as e:
            debug_log('finance_files: error %r' % (e,))
            self.finish('เปลี่ยนไฟล์ไม่สำเร็จ: %s' % e)

    def _switch(self, name):
        if name == self.current:
            self.finish('ใช้ไฟล์ %s อยู่แล้ว ไม่ได้เปลี่ยน' % name)
            return
        info = next((f for f in fdb.list_db_files(self.folder) if f['name'] == name), None)
        if info is None:
            self.finish('ไม่พบไฟล์ %s แล้ว ไม่ได้เปลี่ยน ใช้ %s ต่อ' % (name, self.current or 'ไฟล์เดิม'))
            return
        try:
            problems = fdb.check_schema(info['path'])
        except fdb.FinanceDBError as e:
            self.finish('เปิดไฟล์ %s ไม่ได้ ไม่ได้เปลี่ยน: %s' % (name, e))
            return
        if any('locked' in p or 'busy' in p for p in problems):
            self.finish('ไฟล์ %s กำลังถูกใช้งานอยู่ (ถูกล็อก) ไม่ได้เปลี่ยน ลองใหม่อีกครั้งสักครู่' % name)
            return
        if problems:
            self.finish('ไฟล์ %s โครงสร้างไม่ครบ ไม่ได้เปลี่ยน: %s' % (name, problems[0]))
            return
        if not fdb.set_last_db_name(name):
            self.finish('บันทึกการเปลี่ยนไฟล์ไม่สำเร็จ ยังใช้ %s' % (self.current or 'ไฟล์เดิม'))
            return
        self.finish('เปลี่ยนไฟล์เป็น %s แล้ว ✓ (การบันทึกและสรุปยอดจะใช้ไฟล์นี้ต่อไป)' % name)

    def on_cancel(self):
        ui.delay(self.do_cancel, 0.3)

    def do_cancel(self):
        self.finish('ไม่ได้เปลี่ยนไฟล์ ใช้ %s ต่อ' % (self.current or 'ไฟล์เดิม'))

    def finish(self, message):
        if self.done:
            return
        self.done = True
        host = self.host
        if getattr(host, '_file_switcher', None) is self:
            host._file_switcher = None
        host._finish_turn(message, 'ok', tool=True)  # tool=True: ไม่ให้ AI จำรอบนี้เป็นบทสนทนา
        try:
            host.input.text = ''
        except Exception:
            pass
