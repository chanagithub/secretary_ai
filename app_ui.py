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


HINT_TEXT = 'พิมพ์ หรือกดไมค์บนคีย์บอร์ดเพื่อพูด แล้วกดส่ง'
_SEPARATOR = '\n\n' + '─' * 14 + '\n\n'


def format_turn(turn):
    """แปลงหนึ่งรอบถามตอบเป็นข้อความสำหรับแสดงบนจอ"""
    ai = turn.get('ai') or ''
    status = turn.get('status', 'ok')
    if status == 'live':
        ai = ai or 'กำลังคิด...'
    elif status == 'stopped':
        ai = (ai + '\n' if ai else '') + '(หยุดกลางคัน)'
    elif status == 'error':
        ai = (ai + '\n' if ai else '') + '(ผิดพลาด: %s)' % turn.get('error', '')
    elif not ai.strip():
        ai = '(AI ไม่ได้ตอบกลับ)'
    return 'คุณ · %s\n%s\n\nAI\n%s' % (
        turn.get('time', ''), turn.get('user', ''), ai)


def format_chat(turns):
    return _SEPARATOR.join(format_turn(t) for t in turns if isinstance(t, dict))


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


class HistorySource:
    """data source ของตารางประวัติคำสั่ง (แตะ = เลือก, ปัดซ้าย = ลบ)"""

    def __init__(self, items, on_pick):
        self.items = items
        self.on_pick = on_pick

    def tableview_number_of_sections(self, tableview):
        return 1

    def tableview_number_of_rows(self, tableview, section):
        return len(self.items)

    def tableview_cell_for_row(self, tableview, section, row):
        cell = ui.TableViewCell()
        cell.text_label.text = self.items[row]
        cell.text_label.font = ('<system>', 15)
        cell.text_label.number_of_lines = 2
        return cell

    def tableview_can_delete(self, tableview, section, row):
        return True

    def tableview_can_move(self, tableview, section, row):
        return False

    def tableview_delete(self, tableview, section, row):
        text = self.items.pop(row)
        config.remove_history(text)
        tableview.delete_rows([row])

    def tableview_did_select(self, tableview, section, row):
        self.on_pick(self.items[row])


class ChatListSource:
    """data source ของรายการแชทเก่า (แตะ = เปิดดู, ปัดซ้าย = ลบ)"""

    def __init__(self, chats, on_pick, on_delete):
        self.chats = chats
        self.on_pick = on_pick
        self.on_delete = on_delete

    def tableview_number_of_sections(self, tableview):
        return 1

    def tableview_number_of_rows(self, tableview, section):
        return len(self.chats)

    def tableview_cell_for_row(self, tableview, section, row):
        chat = self.chats[row]
        cell = ui.TableViewCell('subtitle')
        first = chat['first_user'].replace('\n', ' ') or '(ไม่มีข้อความ)'
        cell.text_label.text = first
        cell.text_label.font = ('<system>', 15)
        cell.detail_text_label.text = '%s · %d คำถาม' % (
            chat['updated'] or chat['started'], chat['count'])
        return cell

    def tableview_can_delete(self, tableview, section, row):
        return True

    def tableview_can_move(self, tableview, section, row):
        return False

    def tableview_delete(self, tableview, section, row):
        chat = self.chats.pop(row)
        self.on_delete(chat['id'])
        tableview.delete_rows([row])

    def tableview_did_select(self, tableview, section, row):
        self.on_pick(self.chats[row]['id'])


class ChatViewer(ui.View):
    """หน้าอ่านแชทเก่า พร้อมปุ่มคุยต่อ"""

    def __init__(self, chat, on_continue):
        super().__init__()
        self.name = chat.get('started') or 'แชทเก่า'
        self.background_color = 'white'
        self._on_continue = on_continue

        self.body = ui.TextView()
        self.body.editable = False
        self.body.font = ('<system>', 16)
        self.body.text = format_chat(chat['turns'])
        self.add_subview(self.body)

        self.continue_btn = ui.Button()
        self.continue_btn.title = 'คุยต่อจากแชทนี้'
        self.continue_btn.font = ('<system-bold>', 17)
        self.continue_btn.background_color = '#007aff'
        self.continue_btn.tint_color = 'white'
        self.continue_btn.corner_radius = 10
        self.continue_btn.action = self._continue
        self.add_subview(self.continue_btn)

    def layout(self):
        m = 12
        self.continue_btn.frame = (m, self.height - m - 44,
                                   self.width - 2 * m, 44)
        self.body.frame = (m, m, self.width - 2 * m,
                           max(self.height - 3 * m - 44, 50))

    def _continue(self, sender):
        self._on_continue()


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
    def show_output(self, text):
        self.output.text = text

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
        if self._overlay is not None and self._overlay.superview:
            return
        text = self.input.text.strip()
        if not text:
            console.hud_alert('พิมพ์หรือพูดคำสั่งก่อน', 'error', 1.2)
            return
        self.input.end_editing()
        config.add_history(text)
        self.start_request(text)

    def _set_busy(self, busy):
        if busy:
            self.send_btn.title = 'หยุด'
            self.send_btn.background_color = '#ff3b30'
        else:
            self.send_btn.title = 'ส่ง'
            self.send_btn.background_color = '#007aff'

    def _memory_messages(self):
        """ข้อความที่ให้ AI จำ: MEMORY_PAIRS คู่ล่าสุดที่สำเร็จ (ไม่รวมรอบที่หยุด/ผิดพลาด)"""
        done = [t for t in self._turns
                if t.get('status') == 'ok' and (t.get('ai') or '').strip()]
        messages = []
        for t in done[-config.MEMORY_PAIRS:]:
            messages.append({'role': 'user', 'content': t.get('user', '')})
            messages.append({'role': 'assistant', 'content': t['ai']})
        return messages

    def start_request(self, text):
        token = ai_client.CancelToken()
        self._token = token
        model = config.get_current_model()
        history = self._memory_messages()  # เก็บก่อนเพิ่มข้อความใหม่
        self._live = {'time': config.now_text(), 'model': model,
                      'user': text, 'ai': '', 'status': 'live'}
        self._set_busy(True)
        self.render()
        received = []

        def on_chunk(piece):
            received.append(piece)
            snapshot = ''.join(received)
            ui.delay(lambda: self._on_progress(token, snapshot), 0)

        def worker():
            error = None
            try:
                ai_client.stream_chat(text, on_chunk, token, model, history)
            except ai_client.AIError as e:
                error = str(e)
            except Exception as e:
                error = 'เกิดข้อผิดพลาดที่ไม่คาดคิด: %s' % e
            final = ''.join(received)
            ui.delay(lambda: self._on_done(token, final, error), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _on_progress(self, token, text):
        if token is not self._token or self._live is None:  # ถูกกดหยุดไปแล้ว
            return
        self._live['ai'] = text
        self.render()

    def _finish_turn(self, text, status, error=None):
        """ปิดรอบที่กำลังรอ แล้วบันทึกลงแชทและไฟล์"""
        turn = self._live
        self._live = None
        turn['ai'] = text
        turn['status'] = status
        if error:
            turn['error'] = error
        if self._chat_id is None:
            self._chat_id = config.new_chat_id()
        self._turns.append(turn)
        try:
            config.append_turn(self._chat_id, turn)
        except OSError:
            console.hud_alert('บันทึกแชทลงไฟล์ไม่สำเร็จ', 'error', 2)
        self.render()

    def _on_done(self, token, text, error):
        if token is not self._token:  # ถูกกดหยุดไปแล้ว
            return
        self._token = None
        self._set_busy(False)
        if error:
            self._finish_turn(text, 'error', error)
            return
        self._finish_turn(text, 'ok')
        self.input.text = ''

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
        if self._token is not None:
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
            ui.delay(lambda: self.show_chat_viewer(chat_id), 0.45)

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
        viewer.present('sheet')

    def _continue_chat(self, chat, viewer):
        if self._busy_warning():
            return
        self._chat_id = chat['id']
        self._turns = [t for t in chat['turns'] if isinstance(t, dict)]
        self._live = None
        viewer.close()
        self.render()

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