"""results_view.py - หน้าตารางแสดงผลค้น Reminder (อ่านอย่างเดียว จัดกลุ่มตามเดือน)

ใช้เมื่อผลค้นมีมากกว่า TABLE_THRESHOLD รายการ ไม่แตะข้อมูลใน Reminders
- build_sections : แปลงผลค้น (dated, undated) เป็นหมวดตามเดือน (ไม่ใช้ ui ทดสอบนอกเครื่องได้)
- ResultsOverlay : หน้าจอทับ (รูปแบบเดียวกับป๊อปอัปใน overlays.py) มีตาราง + ปุ่มปิด
ปิดตัวเองก่อนเรียก on_close เสมอ จึงเปิดหน้าถัดไปต่อใน callback ได้
"""
import ui
import tools
from debug_log import log as debug_log

TABLE_THRESHOLD = 8   # ผลมากกว่านี้ถึงจะขึ้นตาราง

_MONTHS = ('', 'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
           'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม')

# เก็บตัวที่ปิดแล้วไว้ ไม่ปล่อยให้ถูกทำลายทันทีขณะที่ native ยังอ้างถึง (กันอาการล่มแบบเดิม)
_RETIRED = []


def _detail(parts):
    return ' · '.join(p for p in parts if p)


def build_sections(dated, undated):
    """คืน [(หัวข้อหมวด, [(บรรทัดหลัก, บรรทัดรอง, เสร็จแล้วไหม), ...]), ...]
    dated เรียงมาแล้วตามโหมดค้น จึงจัดกลุ่มเดือนที่ติดกันเป็นหมวดเดียว ไม่เรียงใหม่"""
    sections = []
    current_key = None
    for item in dated:
        due = item['due']
        key = (due.year, due.month)
        if key != current_key:
            sections.append(('%s %d' % (_MONTHS[due.month], due.year), []))
            current_key = key
        clock = '' if (due.hour == 0 and due.minute == 0) else due.strftime('%H:%M')
        rows = sections[-1][1]
        rows.append((('✓ ' if item['completed'] else '') + item['title'],
                     _detail([tools.format_day_text(due.date()), clock,
                              'เสร็จแล้ว' if item['completed'] else '',
                              ('ลิสต์: %s' % item['list']) if item['list'] else '']),
                     bool(item['completed'])))
    if undated:
        rows = []
        for item in undated:
            rows.append((('✓ ' if item['completed'] else '') + item['title'],
                         _detail(['เสร็จแล้ว' if item['completed'] else '',
                                  ('ลิสต์: %s' % item['list']) if item['list'] else '']),
                         bool(item['completed'])))
        sections.append(('ไม่ได้กำหนดวัน', rows))
    return sections


class ResultsSource:
    """data source ของตาราง (อ่านอย่างเดียว)"""

    def __init__(self, sections):
        self.sections = sections

    def tableview_number_of_sections(self, tableview):
        return len(self.sections)

    def tableview_number_of_rows(self, tableview, section):
        return len(self.sections[section][1])

    def tableview_title_for_header(self, tableview, section):
        title, rows = self.sections[section]
        return '%s (%d)' % (title, len(rows))

    def tableview_cell_for_row(self, tableview, section, row):
        main, detail, done = self.sections[section][1][row]
        cell = ui.TableViewCell('subtitle')
        cell.text_label.text = main
        cell.text_label.font = ('<system>', 15)
        cell.text_label.number_of_lines = 2
        cell.detail_text_label.text = detail
        cell.detail_text_label.font = ('<system>', 12)
        cell.detail_text_label.number_of_lines = 1
        if done:
            cell.text_label.text_color = '#8e8e93'
        return cell


class ResultsOverlay(ui.View):
    """หน้าจอตารางผลค้นทับหน้าจอหลัก มีปุ่มปิดปุ่มเดียว"""
    PAD = 12
    BTN_H = 46

    def __init__(self, header, dated, undated, on_close):
        super().__init__()
        self.flex = 'WH'
        self.background_color = (0, 0, 0, 0.45)
        self._on_close = on_close
        self._is_closing = False

        self.card = ui.View()
        self.card.background_color = 'white'
        self.card.corner_radius = 14
        self.add_subview(self.card)

        self.title_label = ui.Label()
        self.title_label.text = header
        self.title_label.text_color = 'black'
        self.title_label.font = ('<system-bold>', 15)
        self.title_label.number_of_lines = 0
        self.card.add_subview(self.title_label)

        self._source = ResultsSource(build_sections(dated, undated))
        self.table = ui.TableView()
        self.table.data_source = self._source
        self.table.row_height = 64
        self.table.allows_selection = False
        self.card.add_subview(self.table)

        self.close_btn = ui.Button()
        self.close_btn.title = 'ปิด'
        self.close_btn.font = ('<system-bold>', 17)
        self.close_btn.background_color = '#007aff'
        self.close_btn.tint_color = 'white'
        self.close_btn.corner_radius = 10
        self.close_btn.action = self._on_close_pressed   # bound method ไม่ใช้ closure/lambda
        self.card.add_subview(self.close_btn)

    def layout(self):
        pad = self.PAD
        cw = min(self.width - 24, 520)
        ch = max(self.height - 64, 200)
        self.card.frame = ((self.width - cw) / 2, 32, cw, ch)
        title_h = 66
        self.title_label.frame = (pad, pad, cw - 2 * pad, title_h)
        btn_y = ch - pad - self.BTN_H
        self.close_btn.frame = (pad, btn_y, cw - 2 * pad, self.BTN_H)
        table_y = pad + title_h + 4
        self.table.frame = (0, table_y, cw, max(btn_y - pad - table_y, 60))

    def _close(self):
        # ui.View ไม่มี remove_from_superview ใช้ superview.remove_subview และกันปิดซ้ำ
        if self._is_closing:
            return
        self._is_closing = True
        _RETIRED.append(self)
        del _RETIRED[:-5]
        parent = self.superview
        if parent is not None:
            parent.remove_subview(self)

    def _on_close_pressed(self, sender):
        if self._is_closing:   # กดซ้ำ: ไม่เรียก callback ซ้ำ
            return
        debug_log('results: close pressed')
        self._close()
        debug_log('results: closed')
        self._on_close()
