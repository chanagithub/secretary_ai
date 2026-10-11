"""mode_flow.py - ตัวควบคุมโหมด (เตือนความจำ / รายรับรายจ่าย / การลงทุน)

แยกจาก app_ui.py เพื่อไม่ให้ไฟล์หลักยาวขึ้น
- on_select(key): กดปุ่มโหมด (โหมดที่ยังไม่เปิดใช้ -> แจ้งเตือน ไม่สลับ)
- check(text): ก่อนส่งให้ AI ถ้าเรื่องที่พูดดูเป็นของอีกโหมด ขึ้นป๊อปอัปแจ้ง
  คืน True = จัดการแล้ว (รอผู้ใช้เลือก) ห้ามส่งต่อ, คืน False = ส่งต่อได้เลย
callback ทั้งหมดเป็น bound method ตามบทเรียนกันล่ม
"""
import ui
import console
import guardrails
import modes
from overlays import ChoiceOverlay
from mode_bar import ModeBar


class ModeController:
    def __init__(self, host):
        self.host = host
        self.mode = modes.get_mode()
        self._pending_text = None
        self._pending_target = None
        self._stay_text = None
        self.bar = ModeBar(self.on_select)
        self.bar.refresh(self.mode)

    # ---------- ปุ่มโหมด ----------
    def on_select(self, key):
        if self.host._busy_warning():
            return
        if not modes.is_enabled(key):
            console.hud_alert('โหมด "%s" ยังไม่เปิดใช้' % modes.label(key), 'error', 1.5)
            return
        self._switch(key)

    def _switch(self, key):
        if modes.set_mode(key):
            self.mode = key
            self.bar.refresh(key)
        else:
            console.hud_alert('บันทึกโหมดไม่สำเร็จ', 'error', 1.5)

    # ---------- ตรวจเรื่องที่พูดกับโหมดปัจจุบัน ----------
    def check(self, text):
        target = guardrails.mode_hint(self.mode, text)
        if target is None:
            return False
        self._pending_text = text
        self._pending_target = target
        if modes.is_enabled(target):
            title = 'เรื่องนี้ดูเหมือนอยู่ในโหมด "%s"\nตอนนี้อยู่โหมด "%s"' % (
                modes.label(target), modes.label(self.mode))
            options = [('สลับไปโหมด "%s"' % modes.label(target), 'switch'),
                       ('ทำต่อในโหมด "%s"' % modes.label(self.mode), 'stay')]
        else:
            title = ('เรื่องนี้ดูเหมือนอยู่ในโหมด "%s"\n(ยังไม่เปิดใช้)\n'
                     'ทำต่อในโหมด "%s" ไหม' % (modes.label(target), modes.label(self.mode)))
            options = [('ทำต่อในโหมด "%s"' % modes.label(self.mode), 'stay')]
        self.host.show_overlay(ChoiceOverlay(title, options, self.on_pick, self.on_cancel))
        return True

    def on_pick(self, choice):
        text = self._pending_text
        target = self._pending_target
        self._pending_text = self._pending_target = None
        if choice == 'switch' and target:
            self._switch(target)
            console.hud_alert('สลับเป็นโหมด "%s" แล้ว ส่งคำสั่งอีกครั้งได้เลย' % modes.label(target),
                              'success', 2)
        elif choice == 'stay' and text:
            # หน่วงก่อนทำต่อ กันเปิดป๊อปอัปซ้อน (เช่น ป๊อปอัปเลือกวัน) ขณะป๊อปอัปนี้ยังปิดไม่เสร็จ
            self._stay_text = text
            ui.delay(self._continue_stay, 0.3)

    def _continue_stay(self):
        text = self._stay_text
        self._stay_text = None
        if text:
            self.host.begin_request_unchecked(text)

    def on_cancel(self):
        self._pending_text = self._pending_target = None
