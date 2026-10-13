# Handoff v17 — AI เลขาส่วนตัว (Pythonista 3 / iPhone 15)
วันที่ 13 ต.ค. 2026 — **v17 = ส่วนเพิ่มต่อจาก v16 (ต้องอ่าน v16 คู่กัน: กติกา ข้อตกลง ออกแบบ แผน 6 ขั้น)** ที่นี่บอกเฉพาะสิ่งที่เปลี่ยนหลังขั้น 2
ผู้ใช้: Chana — ตอบไทย กระชับ **เครดิตจำกัด ทำทีละขั้น หยุดรอผู้ใช้ทุกขั้น ทำ handoff ใหม่หลังแต่ละขั้น**

## 1. สถานะ
- ขั้น 1 (handoff v16) ✔
- **ขั้น 2 ✔ (ผู้ช่วยส่งแล้ว): `finance_write.py` + `finance_tools.py`** ตรรกะล้วน ไม่แตะหน้าจอ ไม่เปลี่ยนพฤติกรรมแอปจนกว่าจะเชื่อมในขั้น 5
  - ทดสอบในเครื่องผู้ช่วยกับฐานข้อมูลจำลองที่สร้างจาก DDL จริงของ ChanaFinance (`chanafunction.create_tables`): ผ่านทั้งหมด (tools 70+ กรณี, write 35+ กรณี) **แต่ผู้ใช้ยังไม่ได้รันบนเครื่องจริง** ไม่มีสคริปต์ทดสอบบนเครื่องสำหรับขั้นนี้ (ผู้ใช้วางไฟล์ลงโฟลเดอร์ secretary_ai ก็พอ)
- ขั้นถัดไป: **ขั้น 3 = `finance_overlays.py` + `test_finance_overlays.py`** (ดูข้อ 4)
- ยังไม่เปิดโหมดบัญชี (`modes.ENABLED = {'reminders'}`); `assistant_flow.py` ไม่ต้องแก้ ; `app_ui.py` แก้ตอนขั้น 5 ตาม v16 ข้อ 5

## 2. API ที่ทำเสร็จ (ใช้ในขั้น 3-5)
**finance_tools.py** (ไม่พึ่ง ui; พึ่ง finance_db.find_by_name)
- ค่าคงที่: `EXPENSE='expense'`, `INCOME='income'`, `TOOL_NAMES=('record_expense','record_income')`, `KIND_BY_TOOL`; ข้อผิดพลาด `FinanceToolError` (ข้อความไทยแสดงผู้ใช้ได้ตรง ๆ)
- `schemas(lists) -> [schema record_expense, schema record_income]` (lists = ผลของ `finance_db.read_lists`; รายชื่อหมวดจริงอยู่ในคำอธิบายพารามิเตอร์ ใส่เครื่องหมายคำพูดครอบชื่อ)
- `system_message(lists, db_name, today=None) -> {'role':'system','content':...}` แนบท้าย history (วันนี้+ไฟล์+หมวด+กติกา ห้ามเดาประเภทชำระ/วันที่)
- `validate_record(args, kind, lists, today=None) -> rec` โดย **rec = {kind, detail, amount, category_id, category_name, payment_id, payment_name, date, note}**; `category_*`/`payment_*`/`date` เป็น `None` เมื่อ AI ปล่อยว่าง, ชื่อไม่ตรงทุกตัวอักษร (ไม่ทำ fuzzy), หรืออ่านวันที่ไม่ออก -> แอปต้องถามผู้ใช้; `FinanceToolError` เมื่อไม่มีชื่อรายการ/จำนวนเงิน หรือวันที่ผิดปกติ (อนาคต >366 วัน, อดีต >20 ปี); detail รวมช่องว่าง ≤100 ตัวอักษร; note ≤200
- `parse_amount(v)` (รับ 120, '1,200', '๑๒๐ บาท', '฿45' -> float ปัด 2 ตำแหน่ง; ≤0/ไม่ใช่ตัวเลข/>1,000 ล้าน -> error) ใช้กับช่องพิมพ์ในเมนูแก้ไข
- `parse_date_text(text, today=None) -> date|None` รับ วันนี้/เมื่อวาน/เมื่อวานซืน/พรุ่งนี้, `2026-10-05`, `5/10/2026`, `5/10/2569`, `5/10`, `5 ตุลาคม`, `5 ต.ค.`, `5 ตุลา`, `วันที่ 5 ตุลาคม 2569`, เลขไทย; ปี >2400 -> ลบ 543; ไม่บอกปีและวันนั้นอยู่อนาคตเกิน 60 วัน -> ถือเป็นปีที่แล้ว; `check_date(day, today)` ตรวจช่วง (raise error); `format_day_text(day)` เช่น "จันทร์ 12 ต.ค. 2026"
- `amount_warning(amount, source_text) -> str` ('' = ตรงคำพูด; รู้จัก 3,000 / ๓๐๐๐ / 3 พัน / 5 หมื่น / 2 แสน / 1 ล้าน / 1.5k; ไม่มีตัวเลขในคำพูดเลย -> เตือน "มาจากคำพูดที่ไม่มีตัวเลข") ใช้ source_text = ข้อความผู้ใช้รอบนี้ + ข้อความผู้ใช้ก่อนหน้าในแชท; เตือนเท่านั้น ไม่บล็อก
- `format_confirm_text(rec, db_name, warning='')` (ไฟล์/วันที่/รายการ/หมวด/[ชำระ]/จำนวนเงิน/หมายเหตุ/⚠), `confirm_title(kind)` ("บันทึกรายจ่ายนี้ไหม?"), `format_saved_line(rec, db_name)` ("บันทึกรายจ่ายแล้ว ✓ 12 ต.ค. 2026 · ค่าข้าว · อาหาร · เงินสด · 120.00 บาท (ไฟล์ X.db)"), `kind_text`, `format_amount`
  - `format_confirm_text`/`format_saved_line` ต้องมี `rec['date']` เป็น ISO แล้ว (ผู้เรียกต้องเติมวันที่ก่อน เมื่อผู้ใช้กด "ใช่ วันนี้")

**finance_write.py**
- `save_record(db_path, rec) -> (ok, ข้อความไทย, row_id)` ; **ส่ง rec จาก `validate_record` เข้าไปตรง ๆ ได้** (ใช้คีย์ kind, date, detail, category_id, payment_id, amount, note)
- เขียน SQL เหมือน `_save_income/_save_expense` ของแอปเดิม: `detail_id=0`, `detail_text`=ชื่อรายการ, year/month แยกจากวันที่, amount REAL ปัด 2 ตำแหน่ง
- ก่อนเขียนตรวจ: ไฟล์มีจริง (ไม่สร้างไฟล์เปล่า), `check_schema` ครบ, รหัสหมวด/ประเภทชำระมีใน**ไฟล์นี้**, ค่าที่ไม่ถูกต้องทั้งหมด (จำนวนเงิน ≤0/nan/bool/ข้อความ/>1,000 ล้าน, วันที่ผิดรูป เช่น `2026-1-5`, ชื่อว่าง, id เป็นข้อความ/bool) -> `(False, เหตุผล, None)` ไม่เขียนอะไรเลย
- ไฟล์ถูกล็อก -> `(False, 'ไฟล์ฐานข้อมูลกำลังถูกใช้งานอยู่ (ถูกล็อก) ไม่ได้บันทึก ...', None)` (รอสูงสุด ~5-10 วินาที)
- เขียนแล้วเปิดแถวนั้นกลับมาเทียบทุกช่อง: ตรง -> `(True, '', row_id)`; ไม่ตรง/อ่านกลับไม่ได้ -> `(False, ข้อความให้ตรวจในแอป ChanaFinance, row_id)` (**row_id มีค่า = แถวถูกเขียนแล้ว** ต้องบอกผู้ใช้ตรง ๆ ห้ามอ้างว่าสำเร็จหรือล้มเหลวเงียบ)
- **ข้อควรจำสำหรับ flow:** `finance_db.check_schema` จะรายงานไฟล์ที่ถูกล็อกเป็นข้อความ "อ่านตาราง ... ไม่ได้: database is locked" ใน list ปัญหา; ตอนสลับไฟล์ในเมนูแก้ไข ถ้าปัญหามีคำว่า `locked`/`busy` ให้แจ้งว่าไฟล์กำลังถูกใช้งาน ไม่ใช่โครงสร้างผิด (finance_write จัดการแล้วเฉพาะตอนเขียน)

## 3. ผู้ช่วยตัดสินใจเพิ่มในขั้น 2 (ผู้ใช้ยังไม่ได้ทักท้วง)
- ไม่ทำ fuzzy/substring กับชื่อหมวดเด็ดขาด (ตามข้อตกลง v16 ข้อ 4.3)
- วันที่ที่ AI ส่งมาอ่านไม่ออก = ถือว่าไม่ได้พูดวัน (แอปถามยืนยัน "วันนี้ใช่ไหม") ไม่ใช่ error
- ชื่อรายการรวมช่องว่างซ้ำเป็นช่องเดียวก่อนเขียน (แอปเดิมใช้ `.strip()` อย่างเดียว) — ถ้าผู้ใช้ไม่ต้องการ ให้เปลี่ยนใน `_prepare` ของ finance_write.py และ `_clean_text` ของ finance_tools.py

## 4. ขั้น 3 (ขั้นถัดไป) — `finance_overlays.py` + `test_finance_overlays.py`
ออกแบบตาม v16 ข้อ 5 และกำหนด API ดังนี้ (เพื่อให้ขั้น 4 เขียน flow ต่อได้ทันที):
- `FinanceConfirmOverlay(title, body, on_ok, on_edit, on_cancel, on_redo)` สืบทอด `overlays._Popup` (4 ปุ่ม: ตกลง เขียว / แก้ไข น้ำเงิน / ไม่เอา เทา / ทำรายการใหม่ เทา; body_height ~190 เพราะข้อความ 7-8 บรรทัด)
- `ListPickOverlay(title, items, on_pick, on_cancel)` โดย `items = [(ข้อความ, ค่า)]` เรียก `on_pick(ค่า)`; ใช้ `ui.TableView` + `ui.ListDataSource` (เก็บ reference ไว้ที่ self; `ds.action = self._row_selected` เป็น bound method รับ sender=ds ดู `ds.selected_row`); แถวสูง ~52 รองรับชื่อยาวสองบรรทัด; การ์ดสูงตามจำนวนแถวแต่ไม่เกินจอ; ปุ่ม "ยกเลิก" ด้านล่าง; ใช้เลือกหมวด (12 รายการ), ประเภทชำระ, ไฟล์ .db, ช่องที่จะแก้
- `TextInputOverlay(title, initial, on_ok, on_cancel, keyboard='default')` ช่องพิมพ์เดียว + ตกลง/ยกเลิก; การ์ดชิดบนจอ (y~80) ไม่ให้คีย์บอร์ดบัง; `keyboard='decimal'` สำหรับจำนวนเงิน; focus ด้วย `ui.delay(self._focus, 0.4)` (bound method, เช็ก `self.superview is not None`); ปิดตัวเองก่อนเรียก callback เหมือน `_Popup`
- ถามวันที่ "ใช่ วันนี้ / ระบุวันที่" ใช้ `overlays.ChoiceOverlay` เดิม ไม่ต้องสร้างใหม่
- `test_finance_overlays.py` (รันบน iPhone): สร้าง host `ui.View` เล็ก ๆ ที่มี `show_overlay(overlay)` เหมือน MainView (`overlay.frame = self.bounds; self.add_subview(overlay)`) แล้วเปิดป๊อปอัปทีละแบบด้วยข้อมูลสมมติ (หมวดจริง 12 รายการ, ข้อความยืนยันตัวอย่าง) ให้ผู้ใช้กดดูหน้าตา พิมพ์ในช่องข้อความ แล้วพิมพ์ผลที่เลือกลง console — **ไม่เขียนฐานข้อมูล ไม่เรียก AI**
- ไฟล์ที่ต้องมีให้ผู้ช่วยดูในขั้นนี้: `overlays.py` ล่าสุด (มีใน v16 ข้อ 8; ถ้าเปิดแชทใหม่ให้แนบ) — ใน `overlays.py` ใช้ได้เลย: `_Popup(title, body, buttons, body_height)`, สี `_BLUE/_GREEN/_GRAY`, `debug_log` จาก `debug_log.py`

## 5. แผน (เหลือ)
- **ขั้น 3** finance_overlays + ทดสอบหน้าตาบนเครื่อง  <- ถัดไป
- ขั้น 4: ขอ `ai_client.py` แล้วเขียน `finance_flow.py` (ask_ai / prepare_actions / FinanceRunner ตาม v16 ข้อ 5; ลำดับ วันที่ -> หมวด -> ประเภทชำระ -> ยืนยัน)
- ขั้น 5: แก้ `app_ui.py` ≤10 บรรทัด (ส่งไฟล์เต็ม) + `modes.ENABLED` เพิ่ม `ACCOUNTS`
- ขั้น 6: ทดสอบบนเครื่องจริง **กับสำเนา .db** ตามรายการใน v16 ข้อ 7
- ถ้าเปิดแชทใหม่ ให้ผู้ใช้แนบ: handoff_v16.md, handoff_v17.md, finance_db.py, finance_tools.py, finance_write.py, overlays.py, modes.py, app_ui.py (ฉบับล่าสุด) และ ai_client.py (ตอนขั้น 4)
