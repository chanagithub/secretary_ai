# Handoff v18 — AI เลขาส่วนตัว (Pythonista 3 / iPhone 15)
วันที่ 13 ต.ค. 2026 — **ฉบับรวม ใช้แทน v16 + v17 (อ่านฉบับนี้ฉบับเดียวพอ)** เรื่อง Phase 1 / แถบโหมด / ประโยคปลุกผสม ดู v14
ผู้ใช้: Chana — ตอบไทย กระชับ **เครดิตจำกัด (หมดมาแล้ว 2 รอบ) ทำทีละขั้น หยุดรอผู้ใช้ทุกขั้น ทำ handoff ใหม่หลังแต่ละขั้น**

## 1. กติกาทำงาน
- ยืนยันความเข้าใจก่อนเขียนโค้ด แก้เฉพาะจุดที่จำเป็น ส่งไฟล์ฉบับเต็ม บอกว่าแก้ตรงไหน และ **บอกให้วางไฟล์ใหม่ครบทุกไฟล์ที่ส่ง** แล้วปิด Pythonista สนิทก่อนเปิดใหม่ (เคยเด้ง ModuleNotFoundError เพราะวางไม่ครบ)
- **`app_ui.py` (655 บรรทัด) และ `assistant_flow.py` (886 บรรทัด) ยาวมากแล้ว ห้ามให้ยาวขึ้นมาก**: งานโหมดบัญชีอยู่ใน `finance_*.py`; `assistant_flow.py` **ไม่ต้องแก้เลย**; `app_ui.py` แก้ ≤ ~10 บรรทัด (ข้อ 6)
- callback เป็น bound method; เปิดป๊อปอัปถัดไปด้วย `ui.delay(self.do_xxx, 0.3)` (บทเรียน SIGSEGV จาก closure/lambda ใน ui.delay); ป๊อปอัปปิดตัวเองก่อนเรียก callback
- ผู้ช่วยทดสอบตรรกะด้วยโมดูลจำลอง (stub ui) ในเครื่องผู้ช่วยได้ แต่ไม่ใช่ iPhone จริง ต้องบอกผู้ใช้ตรง ๆ
- **ผู้ช่วยยังไม่เคยเห็น `ai_client.py`** (รู้แค่: `ai_client.stream_chat_with_tools(sent_text, on_chunk, token, tools, model=, history=)` คืน `(text, calls)`, calls = `[{'id','name','arguments'}]`; history รับ role `system` ได้) ขอไฟล์นี้ก่อนเขียน `finance_flow.py` เพื่อดู system prompt ที่ฝังอยู่ว่าขัดกับโหมดบัญชีไหม

## 2. สถานะ
- ✔ ขั้น 1 handoff · ✔ ขั้น 2 `finance_write.py` + `finance_tools.py` (ผู้ใช้วางแล้ว) · ✔ ขั้น 3 `finance_overlays.py` + `test_finance_overlays.py` (ผู้ช่วยส่งแล้ว **ผู้ใช้ยังไม่ได้ลองบนเครื่อง**)
- ก่อนหน้า: `finance_db.py`, `check_finance.py` ทำงานบนเครื่องจริงแล้ว (พบ ChanaFinance, `FinStartJune2026.db` ไฟล์เดียว, โครงสร้างครบ)
- **ถัดไป: ขั้น 4 = `finance_flow.py`** (ข้อ 6) แต่ควรให้ผู้ใช้รัน `test_finance_overlays.py` ดูหน้าตาก่อน (ข้อ 4) แล้วค่อยต่อ
- ยังไม่เปิดโหมดบัญชี: `modes.ENABLED = {'reminders'}` (แก้ในขั้น 5)

## 3. ข้อเท็จจริง ChanaFinance (จากโค้ดจริง) และข้อมูลของผู้ใช้
- ตาราง `income(id,date,year,month,detail_id,detail_text,category_id,amount,note)`, `expense` เหมือนกัน + `payment_type_id` หลัง `category_id`; `category_income/category_expense/payment_type(id,name UNIQUE)`; `detail_master(id,detail_name,type)` type='รายรับ'/'รายจ่าย'
- วันที่เก็บ `YYYY-MM-DD` ค.ศ.; `year`/`month` เป็นเลขแยก; SQL แอปเดิม: `INSERT INTO income (date,year,month,detail_id,detail_text,category_id,amount,note)` และ `INSERT INTO expense (date,year,month,detail_id,detail_text,category_id,payment_type_id,amount,note)`; แอปเขียน `detail_id=0` เมื่อไม่ผูกกับ detail_master; amount เป็น float; ไม่มี UNIQUE กันซ้ำ
- รหัส id ของหมวด/ประเภทชำระเป็นของแต่ละไฟล์ .db ห้ามใช้ข้ามไฟล์; คอลัมน์ `detail_text` ถูกเพิ่มทีหลัง ไฟล์เก่าอาจไม่มี (`check_schema` จะบอก และห้ามเขียน)
- ChanaFinance ไม่จำไฟล์ล่าสุด เลขา AI จำเองใน `finance_state.json` (`finance_db.set_last_db_name`)
- ข้อมูลจริงของผู้ใช้ (ผลรัน check_finance): ไฟล์ `FinStartJune2026.db`; ประเภทชำระ 4: บัตรเครดิต/เดบิต, สแกนคิวอาร์โค้ด, เงินสด, โอนเงิน; หมวดรายรับ 9: กำไรจากการขายกองทุน, กำไรจากการขายหุ้น, ค่าเช่าบ้าน, ดอกเบี้ย, รายรับของคลินิก, เงินคืนทุนจากหุ้น, เงินปันผลจากกองทุน, เงินปันผลจากหุ้น, เบี้ยผู้สูงอายุ; หมวดรายจ่าย 12: ของใช้ในบ้าน, ค่าน้ำ ค่าไฟฟ้า ค่าอินเตอร์เน็ต, ค่าน้ำมัน, ค่ายา ค่ารักษาพยาบาล, ค่าอุปกรณ์ช่าง และทำสวน, ค่าใช้จ่ายท่องเที่ยว, ค่าใช้จ่ายส่วนตัว, ทำบุญ, ภาษี, รายจ่ายของคลินิก, อาหาร, อื่น ๆ
- ยังไม่เห็น `monthly_summary.py` / `yearly_summary.py` ของ ChanaFinance (ถ้ามีโอกาสตรวจว่าใช้ `detail_id` หรือ `detail_text`)
- ผู้ใช้จะย้ายทั้งสองโฟลเดอร์ออกจาก iCloud หลังพัฒนาเสร็จ (โค้ดหาโฟลเดอร์แบบสัมพัทธ์อยู่แล้ว)

## 4. ข้อตกลงกับผู้ใช้ (Phase 2) — ครบแล้ว
1. หนึ่งไฟล์ .db ต่อหนึ่งปี; AI เดาไฟล์ = ที่เลขา AI ใช้ล่าสุด ไม่มี = ไฟล์ที่แก้ล่าสุด; แสดงชื่อไฟล์ในป๊อปอัปยืนยันเสมอ
2. ชื่อรายการเก็บเป็นข้อความเต็มใน `detail_text`; `detail_id = 0` เสมอ; ไม่เพิ่มชื่อลง detail_master เอง
3. หมวด/ประเภทชำระ: AI เลือกได้เฉพาะชื่อที่ตรงทุกตัวอักษรกับรายการในไฟล์ ไม่ตรง/ว่าง -> ขึ้นรายการให้ผู้ใช้เลือก ไม่สร้างหมวดใหม่เอง ไม่ทำ fuzzy
4. ไม่ได้พูดวันที่ (รายรับ/รายจ่าย) = ถือเป็นวันนี้ **แต่ต้องถามยืนยัน** "วันนี้ (จันทร์ 12 ต.ค. 2026) ใช่ไหม" ปุ่ม "ใช่ วันนี้" / "ระบุวันที่"; **"ระบุวันที่" ทำเหมือน "ระบุเวลา" เฟส 1**: จบรอบนี้ไม่บันทึก ตั้ง `host._keep_context = True` ให้ผู้ใช้พูดวันในข้อความถัดไป (เช่น เมื่อวาน, 5 ตุลา) แล้ว AI ใช้ความจำแชทเรียกเครื่องมือใหม่
5. ไม่ได้พูดประเภทชำระ (รายจ่าย) -> ขึ้นปุ่มเลือก ห้ามถือเป็นเงินสดอัตโนมัติ (และบอก AI ว่าห้ามเดา)
6. ป๊อปอัปยืนยันสุดท้ายแสดง ไฟล์/วันที่/รายการ/หมวด/(ประเภทชำระ)/จำนวนเงิน/หมายเหตุ ปุ่ม **ตกลง / แก้ไข / ไม่เอา / ทำรายการใหม่**
7. ปุ่ม **แก้ไข** -> เมนูเลือกช่อง (วันที่, รายการ, หมวด, ประเภทชำระ [รายจ่าย], จำนวนเงิน, หมายเหตุ, ไฟล์) แก้ทีละช่องแล้วกลับมาป๊อปอัปยืนยัน (ผู้ใช้อนุมัติแล้ว)
8. กด "ตกลง" -> เขียน -> **อ่านแถวนั้นกลับมาตรวจ** -> ถึงแจ้ง "บันทึกแล้ว ✓" พร้อมชื่อไฟล์; ข้อความ "บันทึกแล้ว" มาจากโค้ดเท่านั้น ไม่ใช่ AI
9. ตัวตรวจจำนวนเงินซ้ำ: ตัวเลขที่ AI ส่งไม่พบในคำพูด -> บรรทัด "⚠" ในป๊อปอัปยืนยัน (เตือนเท่านั้น)
10. ปี ค.ศ. ทั้งหมด; AI ส่งปี >2400 ลบ 543; วันที่นอกช่วง (อนาคต >366 วัน, อดีต >20 ปี) ตรวจไม่ผ่านและแจ้ง
11. ช่วงพัฒนาให้ทดสอบกับ **สำเนา .db** ก่อน (SQLite ใน iCloud เสี่ยงเสียหายถ้าซิงก์ขณะเขียน): copy ไฟล์เป็นชื่อใหม่ในโฟลเดอร์ ChanaFinance ใช้ทดสอบ แล้วลบทิ้ง
12. ยังเปิดอยู่: ปุ่ม "เพิ่มหมวดใหม่" ในป๊อปอัป (ผู้ใช้ยังไม่ขอ); ชื่อรายการรวมช่องว่างซ้ำเป็นช่องเดียวก่อนเขียน (ผู้ช่วยตัดสินใจเอง ถ้าไม่ต้องการแก้ `_prepare` ใน finance_write.py และ `_clean_text` ใน finance_tools.py)

## 5. API ที่ทำเสร็จแล้ว
**finance_tools.py** (ไม่พึ่ง ui): `EXPENSE/INCOME`, `TOOL_NAMES=('record_expense','record_income')`, `KIND_BY_TOOL`, `FinanceToolError` (ข้อความไทยแสดงผู้ใช้ได้เลย)
- `schemas(lists)` -> 2 schema (ใส่รายชื่อหมวดจริงในคำอธิบาย); `system_message(lists, db_name, today=None)` -> `{'role':'system','content':...}` แนบท้าย history
- `validate_record(args, kind, lists, today=None)` -> **rec = {kind, detail, amount, category_id, category_name, payment_id, payment_name, date, note}**; `category_*`/`payment_*`/`date` เป็น None เมื่อว่าง/ไม่ตรง/อ่านวันที่ไม่ออก (แอปต้องถามผู้ใช้); raise `FinanceToolError` เมื่อไม่มีชื่อรายการ/จำนวนเงิน หรือวันที่ผิดปกติ
- `parse_amount(v)` (120, '1,200', '๑๒๐ บาท' -> float ปัด 2 ตำแหน่ง); `parse_date_text(text, today=None)` -> date|None (วันนี้/เมื่อวาน/เมื่อวานซืน/พรุ่งนี้, 2026-10-05, 5/10/2569, 5/10, 5 ตุลาคม, 5 ตุลา, วันที่ 5 ตุลาคม 2569; ไม่บอกปีและอนาคตเกิน 60 วัน = ปีที่แล้ว); `check_date(day, today)`; `format_day_text(day)` ("จันทร์ 12 ต.ค. 2026")
- `amount_warning(amount, source_text)` -> '' หรือข้อความเตือน (รู้จัก 3,000 / ๓๐๐๐ / 3 พัน / 5 หมื่น / 2 แสน / 1 ล้าน / 1.5k; ไม่มีตัวเลขในคำพูดเลย -> เตือน) ใช้ source_text = ข้อความผู้ใช้รอบนี้ + ข้อความผู้ใช้ก่อนหน้าในแชท
- `format_confirm_text(rec, db_name, warning='')` (ต้องมี `rec['date']` เป็น ISO แล้ว), `confirm_title(kind)`, `format_saved_line(rec, db_name)`, `kind_text`, `format_amount`

**finance_write.py**: `save_record(db_path, rec) -> (ok, ข้อความไทย, row_id)` ส่ง rec จาก `validate_record` เข้าไปตรง ๆ ได้ (ใช้ kind, date, detail, category_id, payment_id, amount, note)
- SQL เหมือนแอปเดิม (`detail_id=0`, amount ปัด 2 ตำแหน่ง); ตรวจก่อนเขียน: ไฟล์มีจริง (ไม่สร้างไฟล์เปล่า), `check_schema`, รหัสหมวด/ชำระมีในไฟล์นี้, ค่าผิดทุกแบบ -> `(False, เหตุผล, None)` ไม่เขียน; ไฟล์ถูกล็อก -> `(False, 'ไฟล์ฐานข้อมูลกำลังถูกใช้งานอยู่ (ถูกล็อก) ไม่ได้บันทึก...', None)`
- เขียนแล้วอ่านกลับเทียบทุกช่อง: ตรง -> `(True,'',row_id)`; ไม่ตรง/อ่านกลับไม่ได้ -> `(False, ให้ตรวจในแอป ChanaFinance, row_id)` (**row_id มีค่า = แถวถูกเขียนแล้ว** ต้องบอกผู้ใช้ตรง ๆ)
- `finance_db.check_schema` รายงานไฟล์ที่ถูกล็อกเป็นข้อความ "อ่านตาราง ... ไม่ได้: database is locked" ในรายการปัญหา: ตอนสลับไฟล์ในเมนูแก้ไข ถ้ามี `locked`/`busy` ให้แจ้งว่าไฟล์กำลังถูกใช้งาน ไม่ใช่โครงสร้างผิด

**finance_overlays.py** (ใหม่ ขั้น 3; ใช้ `overlays._Popup`, `_BLUE/_GREEN/_GRAY`)
- `FinanceConfirmOverlay(title, body, on_ok, on_edit, on_cancel, on_redo)` — 4 ปุ่ม (callback ไม่มีอาร์กิวเมนต์)
- `ListPickOverlay(title, items, on_pick, on_cancel)` — items `[(ข้อความ, ค่า)]` -> `on_pick(ค่า)`; TableView + `ui.ListDataSource` (`ds.action = self._row_selected` bound method; ตั้ง `number_of_lines=2` ใน try/except); แถวสูง 52; แถวที่เลือกนอกช่วง/None ถูกละเว้น
- `TextInputOverlay(title, initial, on_ok, on_cancel, keyboard='default'|'decimal')` -> `on_ok(ข้อความ)`; การ์ดชิดบน y=80; return บนคีย์บอร์ด = ตกลง (`self` เป็น delegate); focus ด้วย `ui.delay(self._focus, 0.4)` (ข้ามถ้าปิดไปแล้ว)
- ทุกแบบปิดตัวเองครั้งเดียวก่อนเรียก callback (กดซ้ำไม่เรียกซ้ำ); ถามวันที่ "ใช่ วันนี้ / ระบุวันที่" ใช้ `overlays.ChoiceOverlay(title, [(ข้อความ, ค่า)], on_pick, on_cancel)` เดิม (title 2 บรรทัดพอดี)
- ทดสอบด้วย ui จำลอง: การ์ดอยู่ในจอ iPhone 15 (393x852) และ SE (375x667) ทั้งยืนยัน/เลือก 12 หมวด/ช่องพิมพ์; กดปุ่มแล้วเรียก callback ครั้งเดียวและปิด; **ยังไม่ได้ลองบน Pythonista จริง** — จุดที่อาจต่างบนเครื่องจริง: `ListDataSource.number_of_lines`, แถวสูง/การตัดข้อความชื่อหมวดยาว, การ์ดช่องพิมพ์กับคีย์บอร์ด, ปุ่ม return, focus อัตโนมัติ
- `test_finance_overlays.py` (รันใน Pythonista): หน้าจอมีปุ่ม 7 อัน (ยืนยันรายจ่าย [มีคำเตือน], ยืนยันรายรับ, เลือกหมวด [ใช้หมวดจริงถ้าอ่าน ChanaFinance ได้], เลือกประเภทชำระ, ช่องพิมพ์จำนวนเงิน, ช่องพิมพ์วันที่ [ลอง เมื่อวาน/5 ตุลา], ถามวันที่) ผลแสดงในกล่องข้อความ ไม่เขียนฐานข้อมูล ไม่เรียก AI

## 6. ออกแบบขั้นถัดไป (ยังไม่ได้เขียน)
**ขั้น 4 `finance_flow.py`** — API เหมือน `assistant_flow` ทุกฟังก์ชันที่ app_ui เรียก: `ask_ai(sent_text, on_chunk, token, model, history)`, `prepare_actions(calls, host)`, `run_actions(host, actions, on_done)`; `FinanceRunner` ใช้ bound methods + `ui.delay(...,0.3)`; `on_done(lines, redo, saved)`
- `ask_ai`: `finance_db.find_finance_folder/guess_default_db/check_schema/read_lists` -> มีปัญหาคืน `('', [{'id':None,'name':'_note','local_note':ข้อความ,'arguments':{}}])`; กรอง role `system` เดิมออกจาก history แล้วต่อ `finance_tools.system_message` ท้าย history; เรียก `ai_client.stream_chat_with_tools(..., finance_tools.schemas(lists), ...)`; ผูก `call['finance_ctx']` (ไฟล์+รายการ) และ `call['source_text']` (ข้อความผู้ใช้ + ข้อความผู้ใช้ก่อนหน้า) ใน calls ให้ `prepare_actions` ใช้; AI ตอบเป็นข้อความ (เช่น ถามจำนวนเงิน) คืน `(text, [])`; ถ้าข้อความหลุดเป็น pseudo call (`record_` + `(`) คืน note ขออภัยแบบเฟส 1
- ลำดับป๊อปอัปต่อรายการ: **วันที่ (ถ้าไม่ได้พูด) -> หมวด (ว่าง/ไม่ตรง) -> ประเภทชำระ (รายจ่าย ว่าง) -> ยืนยันสุดท้าย** (ถามวันก่อน เพราะ "ระบุวันที่" จบรอบ จะไม่เสียเวลาเลือกหมวดซ้ำ); ยกเลิกระหว่างเลือก = ยกเลิกรายการนั้น; ถ้า "ระบุวันที่" แล้วมีรายการค้างในคิว ให้เติมบรรทัด "ยังไม่ได้บันทึก ... กรุณาสั่งใหม่"
- ผู้ใช้กด "ใช่ วันนี้" -> เติม `rec['date']=วันนี้ ISO` ก่อน `format_confirm_text`; "แก้ไข" -> เมนูช่อง (ListPickOverlay) -> ช่องข้อความใช้ TextInputOverlay + `parse_date_text`/`parse_amount` (อ่านไม่ออก: hud error แล้วกลับป๊อปอัปยืนยัน); เปลี่ยนไฟล์: ตรวจโครงสร้างไฟล์ใหม่ + อ่านรายการใหม่ + จับคู่หมวด/ชำระเดิมด้วยชื่อ ไม่เจอตั้ง None แล้วบังคับเลือกใหม่
- กด "ตกลง" -> `finance_write.save_record` -> ok: `format_saved_line` + `set_last_db_name`, `saved=True`; ไม่ ok: แสดงข้อความของ save_record ตรง ๆ (มี row_id = บอกให้ตรวจในแอป ChanaFinance)

**ขั้น 5 จุดเชื่อมใน `app_ui.py` (≤ ~10 บรรทัด)**: `import finance_flow`, `import modes`; `__init__` เพิ่ม `self._active_flow = assistant_flow`; บนสุดของ `begin_request_unchecked` เพิ่ม
```
self._active_flow = finance_flow if self.mode_ctl.mode == modes.ACCOUNTS else assistant_flow
if self._active_flow is finance_flow:
    self.start_request(text, text)
    return
```
แล้วเปลี่ยน 3 จุดในสายนี้เป็น `self._active_flow`: `ask_ai` ใน `worker()` ของ `start_request`, `prepare_actions` ใน `_on_done`, `run_actions` ใน `_start_action_flow` (เส้นทาง local ของเฟส 1 ยังเรียก assistant_flow เพราะมีเฉพาะโหมดเตือน) + แก้ `modes.ENABLED` เพิ่ม `ACCOUNTS`

## 7. ข้อควรระวัง
- `_memory_messages` รีเซ็ตความจำหลังรอบที่เป็น tool; `host._keep_context=True` ทำให้รอบนั้นยังเป็นความจำ (ใช้กับ "ระบุวันที่" / AI ถามกลับ); คำตอบสั้นอย่าง "เมื่อวาน" ไม่ผ่านตัวตรวจโหมด (`guardrails.detect_mode` คืน None) -> เข้าโหมดปัจจุบันตามปกติ
- `sqlite3.connect()` สร้างไฟล์ใหม่ถ้าไม่มี -> ตรวจ `os.path.isfile` ก่อนเสมอ (finance_write ทำแล้ว)
- งานค้างเดิมจาก v14: "บ่ายโมง" ไม่มีเลขในประโยคปลุกยังถามกลับ; คำตอบสั้นหลังถามกลับในประโยคผสมยังไม่รู้งานไหน; ความจำวัน 3 ข้อความ; ผลทดสอบประโยคผสม/คำตอบเวลาต่อเนื่องผู้ใช้ยังไม่รายงานชัด; Phase 3 หลักทรัพย์ยังไม่เริ่ม

## 8. แผนที่เหลือ (ทีละขั้น)
- ผู้ใช้ลอง `test_finance_overlays.py` บนเครื่อง รายงานหน้าตา/ปัญหา (ภาพหน้าจอ + ข้อความ) -> แก้ถ้าจำเป็น
- ขั้น 4 `finance_flow.py` (ขอ `ai_client.py` ก่อน) · ขั้น 5 แก้ app_ui + เปิดโหมด · ขั้น 6 ทดสอบบนเครื่อง **กับสำเนา .db**: "จ่ายค่าข้าว 120 บาท" (ไม่พูดวัน/ชำระ), "ได้รับเงินปันผลจากกองทุน AAA เป็นเงิน 3000 วันที่ 5 ตุลาคม", ปุ่มแก้ไขทุกช่อง, "ระบุวันที่" แล้วตอบ "เมื่อวาน", ไม่เอา/ทำรายการใหม่, เปิดแอป ChanaFinance ดูว่าเห็นรายการและยอดถูก
- แล้วค่อยงานค้างข้อ 7 และ Phase 3
- แชทใหม่: แนบ handoff_v18.md, finance_db.py, finance_tools.py, finance_write.py, finance_overlays.py, overlays.py, modes.py, app_ui.py (ล่าสุด) และ ai_client.py
