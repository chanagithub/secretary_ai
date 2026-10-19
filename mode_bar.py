"""mode_bar.py - แถบปุ่มเลือกโหมด 4 ปุ่ม (วางใต้ชื่อแอป)

ModeBar(on_select): กดปุ่ม -> เรียก on_select(key) (ต้องเป็น bound method)
refresh(current): ระบายสีปุ่มของโหมดที่ใช้อยู่ โหมดที่ยังไม่เปิดใช้เป็นสีเทา
"""
import ui
import modes


class ModeBar(ui.View):
    def __init__(self, on_select):
        super().__init__()
        self._on_select = on_select
        self._mode_buttons = []
        for key in modes.KEYS:
            b = ui.Button()
            b.name = key
            b.title = modes.label(key)
            b.font = ('<system-bold>', 12)
            b.corner_radius = 8
            b.border_width = 1
            b.action = self._pressed
            self.add_subview(b)
            self._mode_buttons.append(b)

    def layout(self):
        gap = 6
        n = len(self._mode_buttons)
        w = (self.width - gap * (n - 1)) / n
        for i, b in enumerate(self._mode_buttons):
            b.frame = (i * (w + gap), 0, w, self.height)

    def refresh(self, current):
        for b in self._mode_buttons:
            if b.name == current:
                b.background_color = '#007aff'
                b.tint_color = 'white'
                b.border_color = '#007aff'
            else:
                b.background_color = 'white'
                b.tint_color = '#007aff' if modes.is_enabled(b.name) else '#8e8e93'
                b.border_color = '#c7c7cc'

    def _pressed(self, sender):
        self._on_select(sender.name)
