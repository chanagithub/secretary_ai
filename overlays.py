"""overlays.py - หน้าป๊อปอัปที่ทับหน้าจอหลัก (ย้ายมาจาก app_ui.py ไม่เปลี่ยนโค้ด)"""
import ui


class ConfirmOverlay(ui.View):
    """หน้ายืนยันก่อนเขียนทุกครั้ง (กลไกกลาง ใช้ซ้ำได้ทุกเฟส)"""

    def __init__(self, title, lines, on_ok, on_cancel):
        super().__init__()
        self.flex = 'WH'
        self.background_color = (0, 0, 0, 0.45)
        self._on_ok = on_ok
        self._on_cancel = on_cancel

        self.card = ui.View()
        self.card.background_color = 'white'
        self.card.corner_radius = 14
        self.add_subview(self.card)

        self.title_label = ui.Label()
        self.title_label.text = title
        self.title_label.font = ('<system-bold>', 18)
        self.title_label.alignment = ui.ALIGN_CENTER
        self.title_label.number_of_lines = 0
        self.card.add_subview(self.title_label)

        self.body = ui.TextView()
        self.body.editable = False
        self.body.font = ('<system>', 16)
        self.body.text = '\n\n'.join('%s\n%s' % (k, v) for k, v in lines)
        self.card.add_subview(self.body)

        self.cancel_btn = ui.Button()
        self.cancel_btn.title = 'ยกเลิก'
        self.cancel_btn.background_color = '#e5e5ea'
        self.cancel_btn.tint_color = 'black'
        self.cancel_btn.corner_radius = 10
        self.cancel_btn.action = self._cancel
        self.card.add_subview(self.cancel_btn)

        self.ok_btn = ui.Button()
        self.ok_btn.title = 'ตกลง'
        self.ok_btn.background_color = '#007aff'
        self.ok_btn.tint_color = 'white'
        self.ok_btn.corner_radius = 10
        self.ok_btn.action = self._ok
        self.card.add_subview(self.ok_btn)

    def layout(self):
        pad = 16
        cw = min(self.width - 32, 420)
        ch = min(self.height - 64, 340)
        self.card.frame = ((self.width - cw) / 2,
                           max((self.height - ch) / 2 - 40, 16), cw, ch)
        self.title_label.frame = (pad, pad, cw - 2 * pad, 50)
        btn_y = ch - pad - 44
        half = (cw - 3 * pad) / 2
        self.cancel_btn.frame = (pad, btn_y, half, 44)
        self.ok_btn.frame = (2 * pad + half, btn_y, half, 44)
        body_y = pad + 54
        self.body.frame = (pad, body_y, cw - 2 * pad, btn_y - body_y - pad)

    def _close(self):
        if self.superview:
            self.superview.remove_subview(self)

    def _ok(self, sender):
        self._close()
        self._on_ok()

    def _cancel(self, sender):
        self._close()
        self._on_cancel()