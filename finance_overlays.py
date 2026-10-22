"""finance_overlays.py - ป๊อปอัปของโหมดรายรับรายจ่าย (แยกจาก overlays.py ไม่ให้ไฟล์เดิมยาวขึ้น)

FinanceConfirmOverlay(title, body, on_ok, on_edit, on_cancel, on_redo)
    ยืนยันก่อนเขียน: ตกลง / แก้ไข / ไม่เอา / ทำรายการใหม่ (callback ไม่มีอาร์กิวเมนต์)
ListPickOverlay(title, items, on_pick, on_cancel)
    เลือกหนึ่งข้อจากรายการยาว (หมวด 12 รายการ ฯลฯ) items = [(ข้อความ, ค่า)] -> on_pick(ค่า)
TextInputOverlay(title, initial, on_ok, on_cancel, keyboard='default')
    ช่องพิมพ์เดียว (keyboard='decimal' สำหรับจำนวนเงิน) -> on_ok(ข้อความที่พิมพ์)

เหมือน overlays.py: ปิดตัวเองก่อนเรียก callback เสมอ (จึงเปิดป๊อปอัปถัดไปต่อใน callback ได้
แต่ให้ใช้ ui.delay(เมธอด, 0.3) ตามบทเรียนกันล่ม) และ callback ที่ส่งมาควรเป็น bound method
ถามวันที่ "ใช่ วันนี้ / ระบุวันที่" ใช้ overlays.ChoiceOverlay เดิม ไม่ต้องมีในไฟล์นี้
"""
import ui
from overlays import _Popup, _BLUE, _GREEN, _GRAY
from debug_log import log as debug_log

FINANCE_OVERLAYS_BUILD = 'notes-reuse-picker-2-steplog'
debug_log('finance_overlays BUILD=%s loaded' % FINANCE_OVERLAYS_BUILD)


class FinanceConfirmOverlay(_Popup):
    """ข้อความยืนยัน 7-9 บรรทัด (ไฟล์/วันที่/รายการ/หมวด/ชำระ/จำนวนเงิน/หมายเหตุ/เตือน)"""

    def __init__(self, title, body, on_ok, on_edit, on_cancel, on_redo):
        super().__init__(
            title, body,
            [('ตกลง', _GREEN, 'white', on_ok),
             ('แก้ไข', _BLUE, 'white', on_edit),
             ('ไม่เอา', _GRAY, 'black', on_cancel),
             ('ทำรายการใหม่', _GRAY, 'black', on_redo)],
            body_height=190)


class _CardView(ui.View):
    """พื้นหลังมืด + การ์ดขาว + ปิดตัวเองครั้งเดียว (ฐานของสองป๊อปอัปด้านล่าง)"""
    PAD = 16
    TITLE_H = 54
    BTN_H = 46
    GAP = 10

    def __init__(self, title):
        debug_log('finance card init: before ui.View class=%s' %
                  type(self).__name__)
        super().__init__()
        debug_log('finance card init: ui.View ready class=%s' %
                  type(self).__name__)
        self.flex = 'WH'
        self.background_color = (0, 0, 0, 0.45)
        self._closing = False
        self.card = ui.View()
        self.card.background_color = 'white'
        self.card.corner_radius = 14
        self.add_subview(self.card)
        self.title_label = ui.Label()
        self.title_label.text = title
        self.title_label.text_color = 'black'
        self.title_label.font = ('<system-bold>', 18)
        self.title_label.alignment = ui.ALIGN_CENTER
        self.title_label.number_of_lines = 0
        self.card.add_subview(self.title_label)
        debug_log('finance card init: complete class=%s' %
                  type(self).__name__)

    def _button(self, label, bg, fg, action):
        btn = ui.Button()
        btn.title = label
        btn.font = ('<system-bold>', 17)
        btn.background_color = bg
        btn.tint_color = fg
        btn.corner_radius = 10
        btn.action = action
        self.card.add_subview(btn)
        return btn

    def _card_width(self):
        return min(self.width - 32, 420)

    def _close(self):
        if self._closing:
            return False
        self._closing = True
        parent = self.superview
        if parent is not None:
            parent.remove_subview(self)  # ui.View ไม่มี remove_from_superview
        return True

    def _finish(self, callback, *args):
        if self._close() and callback is not None:
            callback(*args)


class ListPickOverlay(_CardView):
    ROW_H = 52

    def __init__(self, title, items, on_pick, on_cancel, keep_open=False):
        debug_log('finance list init: begin item_count=%d' % len(items))
        super().__init__(title)
        debug_log('finance list init: card ready')
        self._items = list(items)
        self._on_pick = on_pick
        self._on_cancel = on_cancel
        self._keep_open = bool(keep_open)
        self._ds = ui.ListDataSource([{'title': label} for label, _ in self._items])
        debug_log('finance list init: data source ready')
        self._ds.action = self._row_selected  # bound method (sender = data source)
        self._ds.font = ('<system>', 17)
        try:
            self._ds.number_of_lines = 2  # ชื่อหมวดยาว ๆ ขึ้นบรรทัดที่สองได้
        except AttributeError:
            pass
        self.table = ui.TableView()
        self.table.row_height = self.ROW_H
        self.table.background_color = 'white'
        self.table.data_source = self._ds
        self.table.delegate = self._ds
        self.card.add_subview(self.table)
        debug_log('finance list init: table ready')
        self.cancel_btn = self._button('ยกเลิก', _GRAY, 'black', self._cancel_pressed)
        debug_log('finance list init: complete')

    def replace_items(self, title, items, on_pick, keep_open=False):
        """Reuse this picker for a second choice without creating another UI view."""
        debug_log('finance list reuse: step1 begin')
        self._items = list(items)
        self._on_pick = on_pick
        self._keep_open = bool(keep_open)
        self._closing = False
        debug_log('finance list reuse: step2 before title_label.text')
        self.title_label.text = title
        debug_log('finance list reuse: step3 before ds.items')
        self._ds.items = [{'title': label} for label, _ in self._items]
        debug_log('finance list reuse: step4 before table.reload')
        self.table.reload()
        debug_log('finance list reused: item_count=%d' % len(self._items))

    def _row_selected(self, sender):
        row = sender.selected_row
        debug_log('finance list selection: row=%r item_count=%d' %
                  (row, len(self._items)))
        if row is None or row < 0 or row >= len(self._items):
            debug_log('finance list selection ignored: invalid_row=True')
            return
        value = self._items[row][1]
        debug_log('finance list selection value_empty=%s' %
                  (not bool(str(value or '').strip())))
        if self._keep_open:
            if self._on_pick is not None:
                self._on_pick(value)
        else:
            self._finish(self._on_pick, value)

    def _cancel_pressed(self, sender):
        self._finish(self._on_cancel)

    def layout(self):
        pad, gap = self.PAD, self.GAP
        cw = self._card_width()
        fixed = pad + self.TITLE_H + gap + gap + self.BTN_H + pad
        avail = self.height - 64 - fixed
        table_h = max(min(len(self._items) * self.ROW_H, avail), self.ROW_H * 2)
        ch = fixed + table_h
        self.card.frame = ((self.width - cw) / 2, max((self.height - ch) / 2 - 20, 16), cw, ch)
        self.title_label.frame = (pad, pad, cw - 2 * pad, 50)
        y = pad + self.TITLE_H
        self.table.frame = (pad, y, cw - 2 * pad, table_h)
        self.cancel_btn.frame = (pad, y + table_h + gap + gap, cw - 2 * pad, self.BTN_H)


class TextInputOverlay(_CardView):
    def __init__(self, title, initial, on_ok, on_cancel, keyboard='default'):
        super().__init__(title)
        self._on_ok = on_ok
        self._on_cancel = on_cancel
        self.field = ui.TextField()
        self.field.text = str(initial or '')
        self.field.font = ('<system>', 18)
        self.field.keyboard_type = (ui.KEYBOARD_DECIMAL_PAD if keyboard == 'decimal'
                                    else ui.KEYBOARD_DEFAULT)
        self.field.clear_button_mode = 'while_editing'
        self.field.autocapitalization_type = ui.AUTOCAPITALIZE_NONE
        self.field.delegate = self  # ปุ่ม return บนคีย์บอร์ด = ตกลง
        self.card.add_subview(self.field)
        self.cancel_btn = self._button('ยกเลิก', _GRAY, 'black', self._cancel_pressed)
        self.ok_btn = self._button('ตกลง', _GREEN, 'white', self._ok_pressed)
        ui.delay(self._focus, 0.4)

    def _focus(self):
        if not self._closing and self.superview is not None:
            self.field.begin_editing()

    def _submit(self):
        text = self.field.text
        self.field.end_editing()
        self._finish(self._on_ok, text)

    def _ok_pressed(self, sender):
        self._submit()

    def _cancel_pressed(self, sender):
        self.field.end_editing()
        self._finish(self._on_cancel)

    def textfield_should_return(self, textfield):
        self._submit()
        return True

    def layout(self):
        pad, gap = self.PAD, self.GAP
        cw = self._card_width()
        field_h = 44
        ch = pad + self.TITLE_H + field_h + gap + gap + self.BTN_H + pad
        self.card.frame = ((self.width - cw) / 2, 80, cw, ch)  # ชิดบน ไม่ให้คีย์บอร์ดบัง
        self.title_label.frame = (pad, pad, cw - 2 * pad, 50)
        y = pad + self.TITLE_H
        self.field.frame = (pad, y, cw - 2 * pad, field_h)
        y += field_h + gap + gap
        half = (cw - 2 * pad - gap) / 2
        self.cancel_btn.frame = (pad, y, half, self.BTN_H)
        self.ok_btn.frame = (pad + half + gap, y, half, self.BTN_H)
