"""app_ui.py - หน้าจอหลักของ AI เลขาส่วนตัว (เฟส 0: UI)

ตั้งชื่อ app_ui แทน ui เพราะชื่อ ui จะไปบังโมดูล ui ของ Pythonista
ต่อ AI จริงผ่าน ai_client (ตอนนี้ AI ตอบเป็นข้อความอย่างเดียว ยังไม่มีเครื่องมือ)
รันไฟล์นี้ใน Pythonista (ต้องมี config.py และ ai_client.py อยู่โฟลเดอร์เดียวกัน)
"""
import threading

import ui
import dialogs
import console
import config
import ai_client


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

    def _ok(self, sender):
        self.remove_from_superview()
        self._on_ok()

    def _cancel(self, sender):
        self.remove_from_superview()
        self._on_cancel()


class MainView(ui.View):
    def __init__(self):
        super().__init__()
        self.name = 'AI เลขาส่วนตัว'
        self.background_color = 'white'
        self._overlay = None
        self._token = None  # งานที่กำลังรอ AI อยู่ (None = ว่าง)
        self._partial = ''  # คำตอบที่ได้รับแล้วระหว่างรอ

        self.model_btn = ui.Button()
        self.model_btn.font = ('<system>', 14)
        self.model_btn.border_width = 1
        self.model_btn.border_color = '#c7c7cc'
        self.model_btn.corner_radius = 8
        self.model_btn.action = self.show_model_picker
        self.add_subview(self.model_btn)

        self.input = ui.TextView()
        self.input.font = ('<system>', 17)
        self.input.border_width = 1
        self.input.border_color = '#c7c7cc'
        self.input.corner_radius = 8
        self.add_subview(self.input)

        self.send_btn = ui.Button()
        self.send_btn.title = 'ส่ง'
        self.send_btn.font = ('<system-bold>', 17)
        self.send_btn.background_color = '#007aff'
        self.send_btn.tint_color = 'white'
        self.send_btn.corner_radius = 10
        self.send_btn.action = self.send
        self.add_subview(self.send_btn)

        self.output = ui.TextView()
        self.output.editable = False
        self.output.font = ('<system>', 16)
        self.output.text = 'พิมพ์ หรือกดไมค์บนคีย์บอร์ดเพื่อพูด แล้วกดส่ง'
        self.add_subview(self.output)

        self.refresh_model_button()

    def layout(self):
        m = 12
        w, h = self.width, self.height
        self.model_btn.frame = (m, m, w - 2 * m, 36)
        self.input.frame = (m, 56, w - 2 * m, 120)
        self.send_btn.frame = (m, 184, w - 2 * m, 44)
        self.output.frame = (m, 240, w - 2 * m, max(h - 252, 50))

    def refresh_model_button(self):
        self.model_btn.title = 'โมเดล: %s  ▾' % config.get_current_model()

    # ---------- เลือก/เพิ่มโมเดล ----------
    def _picker_items(self):
        current = config.get_current_model()
        return [{'title': m,
                 'accessory_type': 'checkmark' if m == current else 'none'}
                for m in config.get_models()]

    def show_model_picker(self, sender):
        table = ui.TableView()
        table.name = 'เลือกโมเดล'
        ds = ui.ListDataSource(self._picker_items())
        ds.font = ('<system>', 15)

        def on_pick(ds_sender):
            model = ds_sender.items[ds_sender.selected_row]['title']
            config.set_current_model(model)
            self.refresh_model_button()
            table.close()

        def on_add(btn):
            try:
                text = dialogs.input_alert(
                    'เพิ่มโมเดล',
                    'ชื่อโมเดลจาก OpenRouter เช่น openai/gpt-4o',
                    '', 'เพิ่ม')
            except KeyboardInterrupt:  # กดยกเลิก
                return
            ok, result = config.add_model(text)
            if not ok:
                console.hud_alert(result, 'error', 2)
                return
            self.refresh_model_button()
            table.close()

        ds.action = on_pick
        table.data_source = ds
        table.delegate = ds
        table.right_button_items = [ui.ButtonItem(title='+ เพิ่ม', action=on_add)]
        table.present('sheet')

    # ---------- ส่งคำสั่ง + ยืนยัน ----------
    def show_output(self, text):
        self.output.text = text

    def send(self, sender):
        # ระหว่างรอ AI ปุ่มนี้กลายเป็นปุ่ม "หยุด"
        if self._token is not None:
            self.stop()
            return
        if self._overlay is not None and self._overlay.superview:
            return
        text = self.input.text.strip()
        if not text:
            console.hud_alert('พิมพ์หรือพูดคำสั่งก่อน', 'error', 1.2)
            return
        self.input.end_editing()
        self.start_request(text)

    def _set_busy(self, busy):
        if busy:
            self.send_btn.title = 'หยุด'
            self.send_btn.background_color = '#ff3b30'
        else:
            self.send_btn.title = 'ส่ง'
            self.send_btn.background_color = '#007aff'

    def start_request(self, text):
        token = ai_client.CancelToken()
        self._token = token
        self._partial = ''
        self._set_busy(True)
        self.show_output('กำลังคิด...')
        model = config.get_current_model()
        received = []

        def on_chunk(piece):
            received.append(piece)
            snapshot = ''.join(received)
            ui.delay(lambda: self._on_progress(token, snapshot), 0)

        def worker():
            error = None
            try:
                ai_client.stream_chat(text, on_chunk, token, model)
            except ai_client.AIError as e:
                error = str(e)
            except Exception as e:
                error = 'เกิดข้อผิดพลาดที่ไม่คาดคิด: %s' % e
            final = ''.join(received)
            ui.delay(lambda: self._on_done(token, final, error), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _on_progress(self, token, text):
        if token is not self._token:  # ถูกกดหยุดไปแล้ว
            return
        self._partial = text
        self.show_output(text)

    def _on_done(self, token, text, error):
        if token is not self._token:  # ถูกกดหยุดไปแล้ว
            return
        self._token = None
        self._set_busy(False)
        if error:
            self.show_output((text + '\n\n' if text else '') + error)
            return
        self.show_output(text or '(AI ไม่ได้ตอบกลับ)')
        self.input.text = ''

    def stop(self):
        token = self._token
        if token is None:
            return
        token.cancel()
        partial = self._partial
        self._token = None
        self._set_busy(False)
        self.show_output((partial + '\n\n' if partial else '')
                         + 'หยุดแล้ว ไม่ได้ทำรายการใด ๆ')

    def ask_confirm(self, action):
        def on_ok():
            self.show_output('ยืนยันแล้ว (จำลอง ยังไม่ได้บันทึกจริง)\n\n'
                             + '\n'.join('%s: %s' % (k, v)
                                         for k, v in action['lines']))
            self.input.text = ''

        def on_cancel():
            self.show_output('ยกเลิกแล้ว')

        overlay = ConfirmOverlay(action['title'], action['lines'],
                                 on_ok, on_cancel)
        overlay.frame = self.bounds
        self._overlay = overlay
        self.add_subview(overlay)


def main():
    view = MainView()
    view.present('fullscreen')


if __name__ == '__main__':
    main()