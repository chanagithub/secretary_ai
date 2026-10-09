"""chat_views.py - ส่วนแสดงแชทและรายการประวัติ (ย้ายมาจาก app_ui.py ไม่เปลี่ยนโค้ด)

format_chat = แปลงรอบถามตอบเป็นข้อความบนจอ
HistorySource = ตารางประวัติคำสั่ง, ChatListSource = ตารางแชทเก่า, ChatViewer = หน้าอ่านแชทเก่า
"""
import ui
import config


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