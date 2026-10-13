# Handoff v19 — AI เลขาส่วนตัว (Pythonista, iPhone) — Phase 2 ขั้น 4 เสร็จ
อ่านคู่กับ handoff_v18.md (ภาพรวม/ข้อตกลง/สคีมา ChanaFinance ทั้งหมดอยู่ใน v18 ไม่ซ้ำที่นี่)

## ข้อจำกัดของผู้ใช้ (ห้ามลืม)
- app_ui.py / assistant_flow.py ยาวมากแล้ว ห้ามเพิ่มยาว → โค้ดใหม่แยกไฟล์
- ยืนยันความเข้าใจก่อนเขียนโค้ด, แก้เฉพาะจุด, ส่งไฟล์ทั้งไฟล์ให้วางทับ "ทุกไฟล์ที่ส่ง" แล้วปิด Pythonista สนิท
- ห้ามทำให้ ChanaFinance พัง, ทดสอบกับ "สำเนา" .db, ทำทีละขั้น หยุดหลังแต่ละขั้น + handoff ใหม่ (เครดิตหมด 2 รอบแล้ว)

## สถานะ 6 ขั้นของเฟส 2
1 handoff ✓ | 2 finance_db / finance_write / finance_tools ✓ | 3 finance_overlays ✓ (ผู้ใช้ทดสอบผ่าน)
4 finance_flow.py + ai_client.py (แก้เล็ก) ✓ ทดสอบด้วยโมดูลจำลอง ผ่านทั้งหมด (ยังไม่ได้ทดสอบบนเครื่องจริง)
5 ต่อเข้า app_ui.py + เปิดโหมด (ยังไม่ทำ) | 6 ทดสอบบนเครื่องกับสำเนา .db (ยังไม่ทำ)

## สิ่งที่ส่งในขั้น 4
- ai_client.py: เพิ่มพารามิเตอร์ท้าย `system_prompt=None` ใน `stream_chat_with_tools` (None = พฤติกรรมเดิม)
  เหตุผล: prompt เดิมเป็นของโหมดเตือนความจำ (สั่งให้ถามวันที่/ห้ามถามเวลา) ขัดกับโหมดบัญชี
  **ต่างจาก v16/v18**: system message ของการเงินถูกส่งเป็น system_prompt แทนทั้งก้อน ไม่ได้ต่อท้าย history
- finance_flow.py (~430 บรรทัด) API เหมือน assistant_flow: `ask_ai`, `prepare_actions`, `run_actions(host, actions, on_done(lines, redo, saved))`
  ลำดับ: วันที่ (ถามวันนี้ไหม) → หมวด → ชำระ (รายจ่าย) → ยืนยัน → save_record(เขียน+อ่านกลับ) → "บันทึก…แล้ว ✓"
  แก้ไข = เมนู 6-7 ช่อง (วันที่/รายการ/หมวด/ชำระ/จำนวนเงิน/หมายเหตุ/ไฟล์); ยกเลิกในเมนูแก้ = กลับหน้ายืนยัน
  เปลี่ยนไฟล์ = map หมวด/ชำระตามชื่อ ถ้าไม่มีในไฟล์ใหม่ถามใหม่; ไฟล์โครงสร้างเก่า → ⚠ ในหน้ายืนยัน ใช้ไฟล์เดิมต่อ
  "ระบุวันที่" = จบรอบ ไม่บันทึก `host._keep_context=True` ผู้ใช้พูดวันที่ในข้อความถัดไป
  ทุก callback เป็น bound method + `ui.delay(...,0.3)`; `_guarded` กัน exception กลางทาง
- ผลทดสอบ (t/test_flow.py, t/test_ai.py ใน sandbox, stub ui/console/ai_client, DB จาก DDL จริง): ผ่านทั้งหมด
  ครอบคลุมโซ่ถาม, ไฟล์ล่าสุด, ⚠ จำนวนเงิน, ระบุวันที่, redo+คิว, 2 รายการ, แก้ทุกช่อง+ค่าผิด, สลับไฟล์, ไฟล์ล็อก/อ่านกลับไม่ตรง/exception, ไม่มีหมวดในไฟล์

## ขั้นถัดไป (5) — แก้ app_ui.py ไม่เกิน ~10 บรรทัด
- `import finance_flow`, `import modes`; ใน `__init__`: `self._active_flow = assistant_flow`
- ต้น `begin_request_unchecked`: `self._active_flow = finance_flow if self.mode_ctl.mode == modes.ACCOUNTS else assistant_flow`;
  ถ้าเป็น finance → `self.start_request(text, text); return` (ข้ามตัวแยกประโยคเตือนความจำ/guardrails)
- เปลี่ยน `assistant_flow.ask_ai` (worker ใน start_request), `.prepare_actions` (_on_done), `.run_actions` (_start_action_flow) เป็น `self._active_flow.…`
- modes.py: `ENABLED = {REMINDERS, ACCOUNTS}`
- ใช้ไฟล์ app_ui.py ปัจจุบันของผู้ใช้ (ล่าสุดที่เห็น 655 บรรทัด) — ถ้าไม่แน่ใจให้ขอไฟล์ล่าสุดก่อน

## ขั้นที่ 6 ทดสอบบนเครื่อง (กับสำเนา .db)
"จ่ายค่าข้าว 120 บาท" (ถามวันนี้→หมวด→ชำระ→ยืนยัน), "ได้รับเงินปันผลจากกองทุน AAA เป็นเงิน 3000 วันที่ 5 ตุลาคม",
แก้แต่ละช่อง, "ระบุวันที่" แล้วพูด "เมื่อวาน", ไม่เอา/ทำรายการใหม่, สลับไฟล์ → แล้วเปิด ChanaFinance ตรวจแถว/ยอดรวม

## ค้างเดิม
"บ่ายโมง" ไม่มีตัวเลขในประโยคปลุก; คำตอบสั้นหลัง ask-back ในประโยครวม; monthly_summary.py/yearly_summary.py ยังไม่เคยเห็น; เฟส 3 หลักทรัพย์; ปุ่มเพิ่มหมวด (อาจทำ)
