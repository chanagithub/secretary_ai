"""test_finance_overlays.py - ลองดูหน้าตาและการกดป๊อปอัปของโหมดรายรับรายจ่าย (รันใน Pythonista)

วางในโฟลเดอร์ secretary_ai (ต้องมี finance_overlays.py, overlays.py, finance_tools.py, finance_db.py)
ไม่เขียนฐานข้อมูล ไม่เรียก AI ถ้าอ่านหมวดจริงจาก ChanaFinance ได้จะใช้ชื่อจริง (อ่านอย่างเดียว)
กดปุ่มทีละอัน ดูหน้าตา กดตัวเลือกแล้วผลจะแสดงในกล่องข้อความด้านล่าง
สิ่งที่ควรดู: (1) ป๊อปอัปยืนยันไม่ล้นจอ ข้อความอ่านครบ (2) เลือกหมวด 12 รายการเลื่อนได้ ชื่อยาวขึ้นสองบรรทัดไม่ถูกตัด
(3) ช่องพิมพ์ไม่ถูกคีย์บอร์ดบัง กด return = ตกลง (4) กดปุ่มแล้วป๊อปอัปปิด ไม่ค้าง ไม่เด้งออกจากแอป
"""
import datetime
import os
import sys

import ui

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import finance_tools as ft
from finance_overlays import FinanceConfirmOverlay, ListPickOverlay, TextInputOverlay
from overlays import ChoiceOverlay

SAMPLE_LISTS = {
    'category_expense': [(1, 'อาหาร'), (2, 'ค่าน้ำ ค่าไฟฟ้า ค่าอินเตอร์เน็ต'), (3, 'ค่ายา ค่ารักษาพยาบาล'),
                         (4, 'ค่าอุปกรณ์ช่าง และทำสวน'), (5, 'อื่น ๆ')],
    'category_income': [(1, 'เงินปันผลจากกองทุน'), (2, 'ค่าเช่าบ้าน')],
    'payment_type': [(1, 'บัตรเครดิต/เดบิต'), (2, 'สแกนคิวอาร์โค้ด'), (3, 'เงินสด'), (4, 'โอนเงิน')],
}
DB_NAME = 'ตัวอย่าง.db'


def load_real_lists():
    """อ่านหมวดจริงของไฟล์ล่าสุดใน ChanaFinance (อ่านอย่างเดียว) ถ้าไม่ได้ใช้ตัวอย่าง"""
    try:
        import finance_db as fdb
        folder = fdb.find_finance_folder()
        db = fdb.guess_default_db(folder)
        if db and not fdb.check_schema(db['path']):
            return fdb.read_lists(db['path']), db['name']
    except Exception as e:
        print('ใช้รายการตัวอย่าง (อ่านของจริงไม่ได้):', e)
    return SAMPLE_LISTS, DB_NAME


class Host(ui.View):
    """จำลอง MainView: มี show_overlay เหมือนกัน"""

    def __init__(self):
        super().__init__()
        self.name = 'ทดสอบป๊อปอัปรายรับรายจ่าย'
        self.background_color = 'white'
        self.lists, self.db_name = load_real_lists()
        today = datetime.date.today().isoformat()
        self.rec = {'kind': 'expense', 'detail': 'ค่าข้าว', 'amount': 120.0, 'category_id': 1,
                    'category_name': self.lists['category_expense'][0][1], 'payment_id': 3,
                    'payment_name': 'เงินสด', 'date': today, 'note': 'ร้านป้า'}
        self.income = {'kind': 'income', 'detail': 'ปันผลกองทุน AAA', 'amount': 3000.0,
                       'category_id': 1, 'category_name': self.lists['category_income'][0][1],
                       'payment_id': None, 'payment_name': None, 'date': today, 'note': ''}
        self.buttons = []
        for label, action in [
                ('1 ยืนยันรายจ่าย (มีคำเตือน)', self.t_confirm_expense),
                ('2 ยืนยันรายรับ', self.t_confirm_income),
                ('3 เลือกหมวดรายจ่าย (รายการจริง)', self.t_pick_category),
                ('4 เลือกประเภทชำระ', self.t_pick_payment),
                ('5 ช่องพิมพ์: จำนวนเงิน', self.t_text_amount),
                ('6 ช่องพิมพ์: วันที่ (ลอง เมื่อวาน, 5 ตุลา)', self.t_text_date),
                ('7 ถามวันที่ (ChoiceOverlay เดิม)', self.t_ask_date)]:
            b = ui.Button()
            b.title = label
            b.font = ('<system>', 15)
            b.background_color = '#f2f2f7'
            b.corner_radius = 8
            b.action = action
            self.add_subview(b)
            self.buttons.append(b)
        self.log_view = ui.TextView()
        self.log_view.editable = False
        self.log_view.font = ('<system>', 14)
        self.add_subview(self.log_view)
        self.say('พร้อมแล้ว กดปุ่มด้านบนทีละอัน (ไฟล์: %s)' % self.db_name)

    def layout(self):
        y = 8
        for b in self.buttons:
            b.frame = (12, y, self.width - 24, 38)
            y += 44
        self.log_view.frame = (12, y + 4, self.width - 24, max(self.height - y - 16, 60))

    def say(self, text):
        self.log_view.text = text + '\n' + self.log_view.text

    def show_overlay(self, overlay):
        overlay.frame = self.bounds
        self.add_subview(overlay)

    # ----- 1-2 ยืนยัน -----
    def t_confirm_expense(self, sender):
        warn = ft.amount_warning(self.rec['amount'], 'จ่ายค่าข้าว 150 บาท')  # ตัวอย่างคำเตือน
        body = ft.format_confirm_text(self.rec, self.db_name, warn)
        self.show_overlay(FinanceConfirmOverlay(ft.confirm_title('expense'), body,
                                                self.cb_ok, self.cb_edit, self.cb_cancel, self.cb_redo))

    def t_confirm_income(self, sender):
        body = ft.format_confirm_text(self.income, self.db_name)
        self.show_overlay(FinanceConfirmOverlay(ft.confirm_title('income'), body,
                                                self.cb_ok, self.cb_edit, self.cb_cancel, self.cb_redo))

    def cb_ok(self):
        self.say('กด: ตกลง (ของจริงจะเขียนฐานข้อมูลตรงนี้ แต่ทดสอบนี้ไม่เขียน)')

    def cb_edit(self):
        self.say('กด: แก้ไข -> ของจริงจะเปิดเมนูเลือกช่อง (ลองข้อ 3-6)')

    def cb_cancel(self):
        self.say('กด: ไม่เอา')

    def cb_redo(self):
        self.say('กด: ทำรายการใหม่')

    # ----- 3-4 เลือกจากรายการ -----
    def t_pick_category(self, sender):
        items = [(name, cid) for cid, name in self.lists['category_expense']]
        self.show_overlay(ListPickOverlay('เลือกหมวดรายจ่าย', items, self.cb_pick, self.cb_pick_cancel))

    def t_pick_payment(self, sender):
        items = [(name, pid) for pid, name in self.lists['payment_type']]
        self.show_overlay(ListPickOverlay('เลือกประเภทการชำระ', items, self.cb_pick, self.cb_pick_cancel))

    def cb_pick(self, value):
        self.say('เลือกแล้ว ค่า (id) = %r' % (value,))

    def cb_pick_cancel(self):
        self.say('ยกเลิกการเลือก')

    # ----- 5-6 ช่องพิมพ์ -----
    def t_text_amount(self, sender):
        self.show_overlay(TextInputOverlay('จำนวนเงิน (บาท)', '120', self.cb_amount,
                                           self.cb_text_cancel, keyboard='decimal'))

    def cb_amount(self, text):
        try:
            self.say('จำนวนเงินที่อ่านได้: %s' % ft.format_amount(ft.parse_amount(text)))
        except ft.FinanceToolError as e:
            self.say('อ่านจำนวนเงินไม่ได้: %s' % e)

    def t_text_date(self, sender):
        self.show_overlay(TextInputOverlay('วันที่ (เช่น เมื่อวาน, 5 ตุลา, 5/10/2569)', '',
                                           self.cb_date, self.cb_text_cancel))

    def cb_date(self, text):
        day = ft.parse_date_text(text)
        if day is None:
            self.say('อ่านวันที่ไม่ได้: %r' % text)
        else:
            self.say('วันที่ที่อ่านได้: %s (%s)' % (ft.format_day_text(day), day.isoformat()))

    def cb_text_cancel(self):
        self.say('ยกเลิกช่องพิมพ์')

    # ----- 7 ถามวันที่ (ใช้ ChoiceOverlay เดิม) -----
    def t_ask_date(self, sender):
        title = 'วันที่ของรายการนี้คือวันนี้\n(%s) ใช่ไหม?' % ft.format_day_text(datetime.date.today())
        self.show_overlay(ChoiceOverlay(title, [('ใช่ วันนี้', 'today'), ('ระบุวันที่', 'set')],
                                        self.cb_ask_date, self.cb_text_cancel))

    def cb_ask_date(self, value):
        self.say('เลือก: %s' % value)


if __name__ == '__main__':
    Host().present('fullscreen')
