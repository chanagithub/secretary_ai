"""overlays.py - หน้าป๊อปอัปที่ทับหน้าจอหลัก (ปุ่มกดแทนการพิมพ์ตอบ)

ConfirmOverlay = ยืนยันก่อนเขียนจริง: ตกลง / ไม่เอา / ทำรายการใหม่
ChoiceOverlay  = ให้เลือกตัวเลือกหนึ่งข้อ (เช่น วันนี้ / สัปดาห์หน้า) พร้อมปุ่มยกเลิก

ทั้งสองแบบปิดตัวเองก่อนเรียก callback เสมอ จึงเปิดป๊อปอัปถัดไปต่อใน callback ได้
"""
import ui

_BLUE = '#007aff'
_GREEN = '#34c759'
_GRAY = '#e5e5ea'


class _Popup(ui.View):
    """พื้นฐานของป๊อปอัป: พื้นหลังมืด + การ์ดขาว + หัวข้อ + (ข้อความ) + ปุ่มเรียงลง

    buttons = [(ข้อความปุ่ม, สีพื้น, สีตัวอักษร, callback), ...]
    """
    PAD = 16
    BTN_H = 46
    GAP = 10

    def __init__(self, title, body, buttons, body_height=0):
        super().__init__()
        self.flex = 'WH'
        self.background_color = (0, 0, 0, 0.45)
        self._body_height = body_height if body else 0

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

        self.body = None
        if body:
            self.body = ui.TextView()
            self.body.editable = False
            self.body.font = ('<system>', 16)
            self.body.text_color = 'black'
            self.body.text = body
            self.card.add_subview(self.body)

        self._buttons = []
        for label, bg, fg, callback in buttons:
            btn = ui.Button()
            btn.title = label
            btn.font = ('<system-bold>', 17)
            btn.background_color = bg
            btn.tint_color = fg
            btn.corner_radius = 10
            btn.action = self._make_action(callback)
            self.card.add_subview(btn)
            self._buttons.append(btn)

    def _make_action(self, callback):
        def action(sender):
            self._close()
            callback()
        return action

    def _close(self):
        if self.superview:
            self.superview.remove_subview(self)

    def layout(self):
        pad, bh, gap = self.PAD, self.BTN_H, self.GAP
        n = len(self._buttons)
        cw = min(self.width - 32, 420)
        title_h = 54
        buttons_h = n * (bh + gap) - gap
        fixed = pad + title_h + buttons_h + pad
        body_h = 0
        if self.body is not None:
            avail = self.height - 64 - fixed - pad
            body_h = max(min(self._body_height, avail), 60)
            fixed += body_h + pad
        ch = fixed
        self.card.frame = ((self.width - cw) / 2,
                           max((self.height - ch) / 2 - 40, 16), cw, ch)
        self.title_label.frame = (pad, pad, cw - 2 * pad, 50)
        y = pad + title_h
        if self.body is not None:
            self.body.frame = (pad, y, cw - 2 * pad, body_h)
            y += body_h + pad
        for btn in self._buttons:
            btn.frame = (pad, y, cw - 2 * pad, bh)
            y += bh + gap


class ConfirmOverlay(_Popup):
    """หน้ายืนยันก่อนเขียนทุกครั้ง: ตกลง / ไม่เอา / ทำรายการใหม่"""

    def __init__(self, title, body, on_ok, on_cancel, on_redo):
        super().__init__(
            title, body,
            [('ตกลง', _GREEN, 'white', on_ok),
             ('ไม่เอา', _GRAY, 'black', on_cancel),
             ('ทำรายการใหม่', _GRAY, 'black', on_redo)],
            body_height=130)


class ChoiceOverlay(_Popup):
    """ให้เลือกหนึ่งข้อ: options = [(ข้อความปุ่ม, ค่า), ...] แล้วเรียก on_pick(ค่า)"""

    def __init__(self, title, options, on_pick, on_cancel):
        buttons = []
        for label, value in options:
            buttons.append((label, _BLUE, 'white',
                            lambda v=value: on_pick(v)))
        buttons.append(('ยกเลิก', _GRAY, 'black', on_cancel))
        super().__init__(title, None, buttons)