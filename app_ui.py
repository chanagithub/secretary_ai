"""app_ui.py - หน้าจอหลักของ AI เลขาส่วนตัว (UI + เชื่อมเฟส 1 เตือนความจำ)

ตั้งชื่อ app_ui แทน ui เพราะชื่อ ui จะไปบังโมดูล ui ของ Pythonista
ลำดับงานกับ AI (เลือกวัน, tool calling, ยืนยัน, บันทึก) อยู่ใน assistant_flow.py
รันไฟล์นี้ใน Pythonista (ต้องมี config.py, ai_client.py, chat_views.py, overlays.py,
assistant_flow.py, tools.py, date_guard.py, reminders_tool.py อยู่โฟลเดอร์เดียวกัน)
"""
import threading

import ui
import dialogs
import console
import config
import ai_client
import assistant_flow
from chat_views import format_chat, HistorySource, ChatListSource, ChatViewer
from overlays import ChoiceOverlay


HINT_TEXT = 'พิมพ์ หรือกดไมค์บนคีย์บอร์ดเพื่อพูด แล้วกดส่ง'


class MainView(ui.View):
    def __init__(self):
        super().__init__()
        self.name = 'AI เลขาส่วนตัว'
        self.background_color = 'white'
        self._overlay = None
        self._token = None  # งานที่กำลังรอ AI อยู่ (None = ว่าง)
        self._chat_id = None  # แชทที่เปิดอยู่ (None = ยังไม่มีข้อความแรก)
        self._turns = []      # รอบถามตอบของแชทที่เปิดอยู่
        self._live = None     # รอบที่กำลังรอ AI ตอบ

        self.model_btn = ui.Button()
        self.model_btn.font = ('<system>', 14)
        self.model_btn.border_width = 1
        self.model_btn.border_color = '#c7c7cc'
        self.model_btn.corner_radius = 8
        self.model_btn.action = self.show_model_picker
        self.add_subview(self.model_btn)

        self.history_btn = ui.Button()
        self.history_btn.title = 'ประวัติ'
        self.history_btn.font = ('<system>', 14)
        self.history_btn.border_width = 1
        self.history_btn.border_color = '#c7c7cc'
        self.history_btn.corner_radius = 8
        self.history_btn.action = self.show_history_picker
        self.add_subview(self.history_btn)

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
        self.add_subview(self.output)

        self.right_button_items = [
            ui.ButtonItem(title='แชทเก่า', action=self.show_chats),
            ui.ButtonItem(title='เริ่มใหม่', action=self.new_chat)]

        self.refresh_model_button()
        self.render()

    def layout(self):
        m = 12
        w, h = self.width, self.height
        self.model_btn.frame = (m, m, w - 3 * m - 76, 36)
        self.history_btn.frame = (w - m - 76, m, 76, 36)
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

    # ---------- ประวัติคำสั่ง ----------
    def show_history_picker(self, sender):
        if self._token is not None:
            console.hud_alert('รอ AI ตอบหรือกดหยุดก่อน', 'error', 1.5)
            return
        items = config.get_history()
        if not items:
            console.hud_alert('ยังไม่มีประวัติ', 'error', 1.2)
            return

        table = ui.TableView()
        table.name = 'ประวัติคำสั่ง'
        table.row_height = 64

        def on_pick(text):
            self.input.text = text
            table.close()

            def focus_input():
                self.input.begin_editing()
                try:  # เลื่อนเคอร์เซอร์ไปท้ายข้อความ (นับเป็นหน่วย UTF-16)
                    end = len(text.encode('utf-16-le')) // 2
                    self.input.selected_range = (end, end)
                except ValueError:
                    pass
            ui.delay(focus_input, 0.4)

        def on_clear(btn):
            try:
                console.alert('ล้างประวัติทั้งหมด?',
                              'ลบคำสั่งที่เคยส่งทั้งหมด', 'ล้าง')
            except KeyboardInterrupt:  # กดยกเลิก
                return
            config.clear_history()
            source.items[:] = []
            table.reload()

        source = HistorySource(items, on_pick)
        table.data_source = source
        table.delegate = source
        table.right_button_items = [
            ui.ButtonItem(title='ล้างทั้งหมด', action=on_clear)]
        table.present('sheet')

    # ---------- ส่งคำสั่ง + ยืนยัน ----------
    def render(self):
        turns = list(self._turns)
        if self._live is not None:
            turns.append(self._live)
        if not turns:
            self.output.text = HINT_TEXT
            return
        self.output.text = format_chat(turns)
        self._scroll_to_bottom()
        ui.delay(self._scroll_to_bottom, 0.05)

    def _scroll_to_bottom(self):
        try:
            y = self.output.content_size[1] - self.output.height
            self.output.content_offset = (0, max(y, 0))
        except Exception:  # ถ้า TextView ไม่รองรับ ก็แค่ไม่เลื่อนอัตโนมัติ
            pass

    def send(self, sender):
        # ระหว่างรอ AI ปุ่มนี้กลายเป็นปุ่ม "หยุด"
        if self._token is not None:
            self.stop()
            return
        if self._popup_open():
            return
        text = self.input.text.strip()
        if not text:
            console.hud_alert('พิมพ์หรือพูดคำสั่งก่อน', 'error', 1.2)
            return
        self.input.end_editing()
        config.add_history(text)
        self.begin_request(text)

    def _set_busy(self, busy):
        if busy:
            self.send_btn.title = 'หยุด'
            self.send_btn.background_color = '#ff3b30'
        else:
            self.send_btn.title = 'ส่ง'
            self.send_btn.background_color = '#007aff'

    def _memory_messages(self):
        """ข้อความที่ให้ AI จำ: MEMORY_PAIRS คู่ล่าสุดที่สำเร็จ (ไม่รวมรอบที่หยุด/ผิดพลาด)

        นับเฉพาะรอบหลังรอบล่าสุดที่มีการเรียกเครื่องมือ (turn['tool']) เหมือนตอนทดสอบ
        ใช้ข้อความที่ส่งให้ AI จริง (turn['sent'], มีวันที่ที่ผู้ใช้เลือกต่อท้าย) ถ้ามี
        """
        done = []
        for t in reversed(self._turns):
            if t.get('tool'):
                break
            if t.get('status') == 'ok' and (t.get('ai') or '').strip():
                done.append(t)
        done.reverse()
        messages = []
        for t in done[-config.MEMORY_PAIRS:]:
            messages.append({'role': 'user',
                             'content': t.get('sent') or t.get('user', '')})
            messages.append({'role': 'assistant', 'content': t['ai']})
        return messages

    def begin_request(self, text):
        """ถ้าพูดชื่อวันที่ตรงกับวันนี้ ถามผู้ใช้ด้วยปุ่มก่อน แล้วค่อยส่งให้ AI"""
        info = assistant_flow.find_ambiguous_weekday(text)
        if not info:
            self.start_request(text, text)
            return
        title, options = assistant_flow.weekday_choice(info)

        def on_pick(choice):
            self.start_request(text, assistant_flow.apply_choice(text, info, choice))

        overlay = ChoiceOverlay(title, options, on_pick, lambda: None)
        self.show_overlay(overlay)

    def start_request(self, text, sent_text):
        token = ai_client.CancelToken()
        self._token = token
        model = config.get_current_model()
        history = self._memory_messages()  # เก็บก่อนเพิ่มข้อความใหม่
        self._live = {'time': config.now_text(), 'model': model,
                      'user': text, 'ai': '', 'status': 'live'}
        if sent_text != text:
            self._live['sent'] = sent_text
        self._set_busy(True)
        self.render()
        received = []

        def on_chunk(piece):
            received.append(piece)
            snapshot = ''.join(received)
            ui.delay(lambda: self._on_progress(token, snapshot), 0)

        def worker():
            error = None
            calls = []
            try:
                _, calls = assistant_flow.ask_ai(
                    sent_text, on_chunk, token, model, history)
            except ai_client.AIError as e:
                error = str(e)
            except Exception as e:
                error = 'เกิดข้อผิดพลาดที่ไม่คาดคิด: %s' % e
            final = ''.join(received)
            ui.delay(lambda: self._on_done(token, final, calls, error), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _on_progress(self, token, text):
        if token is not self._token or self._live is None:  # ถูกกดหยุดไปแล้ว
            return
        self._live['ai'] = text
        self.render()

    def _finish_turn(self, text, status, error=None, tool=False):
        """ปิดรอบที่กำลังรอ แล้วบันทึกลงแชทและไฟล์ (tool=True: รอบนี้มีการเรียกเครื่องมือ)"""
        turn = self._live
        self._live = None
        turn['ai'] = text
        turn['status'] = status
        if error:
            turn['error'] = error
        if tool:
            turn['tool'] = True
        if self._chat_id is None:
            self._chat_id = config.new_chat_id()
        self._turns.append(turn)
        try:
            config.append_turn(self._chat_id, turn)
        except OSError:
            console.hud_alert('บันทึกแชทลงไฟล์ไม่สำเร็จ', 'error', 2)
        self.render()

    def _on_done(self, token, text, calls, error):
        if token is not self._token:  # ถูกกดหยุดไปแล้ว
            return
        self._token = None
        self._set_busy(False)
        if error:
            self._finish_turn(text, 'error', error)
            return
        if not calls:  # AI ตอบเป็นข้อความ (หรือถามกลับ)
            self._finish_turn(text, 'ok')
            self.input.text = ''
            return
        self._run_actions(text, assistant_flow.prepare_actions(calls))

    def _run_actions(self, ai_text, actions):
        """ตรวจค่า -> ป๊อปอัปยืนยัน -> บันทึก แล้วปิดรอบพร้อมผลลัพธ์"""
        self._live['ai'] = ai_text or '(รอคุณยืนยัน)'
        self.render()

        def on_done(lines, redo, saved):
            parts = ([ai_text.strip()] if ai_text.strip() else []) + lines
            self._finish_turn('\n'.join(parts), 'ok', tool=True)
            if saved or redo:
                self.input.text = ''
            if redo:  # ล้างช่องแล้วเริ่มใหม่
                ui.delay(self.input.begin_editing, 0.3)

        assistant_flow.run_actions(self, actions, on_done)

    def stop(self):
        token = self._token
        if token is None:
            return
        token.cancel()
        text = self._live['ai'] if self._live else ''
        self._token = None
        self._set_busy(False)
        self._finish_turn(text, 'stopped')

    # ---------- เริ่มใหม่ / แชทเก่า ----------
    def _busy_warning(self):
        if self._token is not None or self._popup_open():
            console.hud_alert('รอ AI ตอบหรือกดหยุดก่อน', 'error', 1.5)
            return True
        return False

    def _reset_chat(self):
        self._chat_id = None
        self._turns = []
        self._live = None
        self.render()

    def new_chat(self, sender):
        if self._busy_warning():
            return
        self._reset_chat()

    def show_chats(self, sender):
        if self._busy_warning():
            return
        chats = config.list_chats()
        if not chats:
            console.hud_alert('ยังไม่มีแชทเก่า', 'error', 1.2)
            return

        table = ui.TableView()
        table.name = 'แชทเก่า'
        table.row_height = 64

        def on_pick(chat_id):
            table.close()
            ui.delay(lambda: self.show_chat_viewer(chat_id), 0.6)

        def on_delete(chat_id):
            config.delete_chat(chat_id)
            if chat_id == self._chat_id:  # ลบแชทที่เปิดอยู่ ให้ล้างจอด้วย
                self._reset_chat()

        def on_clear(btn):
            try:
                console.alert('ล้างแชทเก่าทั้งหมด?',
                              'ลบประวัติแชททั้งหมดและเริ่มแชทใหม่', 'ล้าง')
            except KeyboardInterrupt:  # กดยกเลิก
                return
            config.clear_chats()
            self._reset_chat()
            source.chats[:] = []
            table.reload()

        source = ChatListSource(chats, on_pick, on_delete)
        table.data_source = source
        table.delegate = source
        table.right_button_items = [
            ui.ButtonItem(title='ล้างทั้งหมด', action=on_clear)]
        table.present('sheet')

    def show_chat_viewer(self, chat_id):
        chat = config.get_chat(chat_id)
        if chat is None:
            console.hud_alert('ไม่พบแชทนี้', 'error', 1.5)
            return
        viewer = ChatViewer(chat, lambda: self._continue_chat(chat, viewer))
        self._present_when_ready(viewer, 10)

    def _present_when_ready(self, viewer, attempts):
        """เปิดหน้าใหม่ทับ sheet ที่เพิ่งปิด: ถ้าแอนิเมชันยังไม่จบจะลองใหม่ทุก 0.3 วินาที"""
        try:
            viewer.present('sheet')
        except ValueError:  # view is already being presented or animation
            if attempts <= 0:
                console.hud_alert('เปิดแชทไม่สำเร็จ ลองกดใหม่อีกครั้ง', 'error', 2)
                return
            ui.delay(lambda: self._present_when_ready(viewer, attempts - 1), 0.3)

    def _continue_chat(self, chat, viewer):
        if self._busy_warning():
            return
        self._chat_id = chat['id']
        self._turns = [t for t in chat['turns'] if isinstance(t, dict)]
        self._live = None
        viewer.close()
        self.render()

    # ---------- ป๊อปอัป ----------
    def _popup_open(self):
        return self._overlay is not None and self._overlay.superview is not None

    def show_overlay(self, overlay):
        """แสดงป๊อปอัปทับหน้าจอ (assistant_flow เรียกใช้)"""
        self.input.end_editing()
        overlay.frame = self.bounds
        self._overlay = overlay
        self.add_subview(overlay)


def main():
    view = MainView()
    view.present('fullscreen')


if __name__ == '__main__':
    main()