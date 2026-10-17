# Handoff v30 — AI เลขาส่วนตัว (Pythonista 3 / iPhone) — Shortcut "AI SaveToNote" ทางสร้างโน้ตใหม่ใช้ได้แล้ว
วันที่ 17 ต.ค. 2026 ~12:50 — ต่อจาก handoff_v29.md (ข้อตกลงออกแบบโหมดโน้ต แผนทีละขั้น และกติกาทำงาน อยู่ใน v29 และ v28 ยังใช้ได้ทั้งหมด)
ผู้ใช้: Chana — ตอบไทย กระชับ ทำทีละเรื่อง ห้ามแก้ไฟล์ ChanaFinance ผู้ใช้ทดสอบบน iPhone เอง

## 1. กติกาเพิ่มจากรอบนี้ (ผู้ใช้เสียเวลาไปครึ่งวัน)
- **ขอไฟล์/โค้ดจริงที่ผู้ใช้รันอยู่ก่อนเดาทางแก้เสมอ** รอบนี้ผู้ช่วยเดาฝั่ง Shortcut ซ้ำหลายรอบ ทั้งที่ต้นเหตุอยู่ในไฟล์ Python (ชื่อ key ไม่ตรง) และผู้ช่วยเคยถอนข้อสงสัยที่ผู้ใช้เสนอถูก (key ตัวพิมพ์ใหญ่) โดยเหตุผลไม่พอ
- **ก่อนให้ทดสอบ ต้องบอก "ทำอะไร จุดประสงค์อะไร อ่านผลอย่างไร" และให้ทดสอบทีละอย่างเดียว** (ผู้ใช้เคยงงเพราะให้หลายอย่างปนกัน)
- ผู้ช่วยทดสอบ Shortcut/iPhone เองไม่ได้ ห้ามอ้างว่าชื่อ action หรือเมนูบน iOS 26 ตรงตัวถ้ายังไม่เห็นภาพ

## 2. สถานะ
- **ผู้ใช้ทดสอบแล้ว "ได้ตามต้องการ":** ส่ง JSON `MODE/TITLE/BODY` จาก Python -> Shortcut `AI SaveToNote` -> If แยกทาง `new` กับทางอื่น (ทดสอบ 2 รอบ: `MODE='new'` สร้างโน้ตชื่อ TITLE เนื้อหา BODY; `MODE='append'` เข้าทาง Otherwise ซึ่งตอนนี้เป็นโน้ตทดสอบชื่อ "ทางอื่น (ทดสอบ)" ไม่ใช่การต่อท้ายจริง)
- **ยังไม่ได้ทำ:** ทาง append จริง (ต่อท้ายโน้ตเดิม), โค้ดแอป (โหมดที่ 4, flow, ป๊อปอัป), guardrails
- ยังไม่เปิดโหมดโน้ตในแอป; ไฟล์ของแอปไม่ถูกแก้ในรอบนี้

## 3. ข้อเท็จจริงที่ยืนยันแล้ว (บนเครื่องจริง)
**ทางส่งค่า Python -> Shortcut**
- ใช้ `shortcuts.open_url('shortcuts://x-callback-url/run-shortcut?' + urlencode({name, input:'text', text: payload, 'x-success':'pythonista3://', 'x-cancel':'pythonista3://'}, quote_via=quote))` ใช้ได้; ค่าถึง Shortcut ครบรวมภาษาไทยและขึ้นบรรทัดใหม่ (ทดสอบด้วย Shortcut `AI TestInput` ที่คัดลอกค่าที่ได้รับไปคลิปบอร์ดแล้ว Python อ่านพิมพ์ออกมา)
- **ชื่อ key ใน JSON ที่ Python ส่ง กับชื่อในช่อง "Get Value for" ของ Shortcut ต้องสะกดตรงกันทุกตัวอักษร รวมตัวพิมพ์เล็ก/ใหญ่** ตอนนี้ใช้ตัวใหญ่ทั้งสองฝั่ง: `MODE`, `TITLE`, `BODY` (ไฟล์เดิมส่งตัวเล็กจึงไม่ทำงาน; ไม่เกี่ยวกับชื่อตัวแปร ไม่จำเป็นต้องเปลี่ยนชื่อ Dictionary)
- `ReminderData` ใน Shortcut ปลุกเป็นแค่ป้ายชื่อของ Dictionary ไม่จำเป็นต้องตั้ง

**โครง Shortcut `AI SaveToNote` ที่ใช้ได้ตอนนี้** (ผู้ใช้สร้างตามภาพ; ชื่อ action อาจต่างเล็กน้อยบน iOS 26)
1. Receive ... from Nowhere (If there's no input: Continue) — เหมือน Shortcut ปลุก
2. Get dictionary from **Shortcut Input** (ต้องเป็น Shortcut Input ไม่ใช่ชิป Input สีจาง)
3. Get Value for TITLE / BODY / MODE in Dictionary
4. Get text from (ค่าของ MODE) — **จำเป็น** ไม่งั้น If ขึ้น "File Size/Number MB" หรือมีแค่ "has any value" ไม่มี "is"
5. If Text is `new` -> Create note (ช่อง **Name** = ค่า TITLE, เนื้อหา = BODY) / Otherwise -> (ตอนนี้โน้ตทดสอบ) / End If
- ชื่อตัวแปรอัตโนมัติของ Shortcuts ซ้ำและสับสนง่าย ("Dictionary Value" หลายตัว) ตรวจ input ของแต่ละ Set variable ให้ดีก่อนเชื่อ
- action "Show Result" ไม่มีใน iOS 26 ของผู้ใช้ มี "Show Content" ใช้ตรวจชั่วคราวแทน; วิธีตรวจที่ได้ผลคือ Shortcut ทดสอบที่ Copy to Clipboard แล้ว Python อ่านคลิปบอร์ด
- **ค้างตรวจ:** สวิตช์ "Open When Run" ใน Create note เคยเปิดอยู่ (จะเปิดแอป Notes ทับ ทำให้ไม่กลับ Pythonista เอง) ยังไม่ยืนยันว่าผู้ใช้ปิดแล้ว; action "Stop and output (Create Note)" เคยมีอยู่ใต้ Create note ถ้ายังอยู่ต้องอยู่เฉพาะทาง new หรือลบ

**ทางอ่านรายชื่อโน้ต (จาก v29)** Shortcut `ทดสอบรายชื่อโน้ต` (Find Notes เรียงตามวันที่แก้ไข Limit 30 -> Repeat: Get name of Repeat Item -> หลังลูป Combine Text (Repeat Results, New Lines) -> Copy Combined Text to Clipboard) ใช้ได้ผ่านคลิปบอร์ด ชื่อไทยถูกต้อง; ต้องเปิด Settings -> Shortcuts -> Advanced -> **Allow Sharing Large Amounts of Data** (หรือลดจำนวนโน้ต — ผู้ใช้ยังไม่ได้บอกว่าเลือกทางไหน); iOS ถามสิทธิ์ "paste from Shortcuts" ทุกครั้งต้องกด **Allow Paste**; การส่งผ่านคลิปบอร์ดเขียนทับคลิปบอร์ดเดิมของผู้ใช้

## 4. ขั้นถัดไป (ทีละขั้น หยุดรอผู้ใช้ทุกขั้น)
- **ขั้น 2.5 ทาง append จริงใน `AI SaveToNote`:** แทนโน้ตทดสอบใน Otherwise ด้วย Find Notes (Name **is** TITLE, เรียงตามวันที่แก้ไข, Limit 1) + action ต่อท้ายข้อความโน้ต (ชื่อประมาณ "Append to Note"/"Append Text to Note" — **ยังไม่ได้ตรวจว่ามีบน iOS 26 และต่อท้ายได้จริง**) ทดสอบกับโน้ตทดสอบ "ทดสอบเลขา AI" เท่านั้น ห้ามลองกับโน้ตจริง; ตรวจว่า Find Notes ชื่อ "is" ไม่ไปเจอโน้ตอื่น
  - ข้อเสนอการออกแบบ (ยังไม่ได้ตกลงกับผู้ใช้): ให้ **Python ประกอบเนื้อหาทั้งหมดรวมหัวข้อวันที่** (เช่น "17 ต.ค. 2026\nเพลง ...") แล้วส่งใน BODY; Shortcut ทำแค่สร้าง/ต่อท้ายไม่คิดเอง
- **คำถามที่ยังไม่ได้คำตอบจากผู้ใช้:** มีโน้ตชื่อซ้ำไหม (ถ้าซ้ำ append ด้วยชื่ออาจได้โน้ตผิดตัว ข้อเสนอ: แสดงวันที่แก้ไขต่อท้ายชื่อในปุ่มเลือก หรือหาตัวระบุที่ Shortcut ส่งกลับได้); Allow Sharing Large Amounts of Data เปิดหรือลดจำนวน; จำนวนโน้ตที่ให้ขึ้นเลือก (ตอนนี้ 30); โฟลเดอร์ปลายทางของโน้ตใหม่ (ตอนนี้ใช้ค่าเริ่มต้น)
- **ขั้น 3 โค้ดแอป** (แยกไฟล์ `notes_*.py`): ตัวอ่านรายชื่อโน้ตผ่านคลิปบอร์ด, ตัวส่งไป `AI SaveToNote` (key ตัวใหญ่ MODE/TITLE/BODY), tool schema + ตรวจค่า, ป๊อปอัป ใหม่/ต่อ + เลือกโน้ต + ยืนยันชื่อ + ยืนยันเนื้อหา, flow API เหมือน assistant_flow/finance_flow (`ask_ai`, `prepare_actions`, `run_actions(host, actions, on_done(lines, redo, saved))`) ข้อความผลลัพธ์ต้องกลาง ๆ ("ส่งคำสั่งไปยัง Shortcut แล้ว") เพราะ Python ยืนยันว่าโน้ตถูกสร้างไม่ได้
- **ขั้น 4:** เชื่อมระบบ — modes.py (โหมดที่ 4 + ENABLED), mode_bar.py (ปุ่มที่ 4 / เมนู "•••"), guardrails.py (แยก "บันทึก" โน้ตออกจาก "บันทึกรายจ่าย"), app_ui.py (ขยาย ternary เลือก flow ใน `begin_request_unchecked` ให้น้อยบรรทัดที่สุด)
- **ขั้น 5:** ทดสอบบนเครื่อง: สร้างใหม่, ต่อโน้ตเดิม, ไม่เอาชื่อที่เสนอแล้วพูดเอง, ยกเลิก, Shortcut/คลิปบอร์ดล้มเหลว (ต้องไม่อ้างว่าสำเร็จ)

## 5. ไฟล์และชื่อ
- สคริปต์ทดสอบของผู้ใช้: `test_note_save.py` (ฉบับล่าสุดส่ง key `MODE/TITLE/BODY` ตัวใหญ่ ใช้ได้), `test_notes_list.py` (อ่านรายชื่อโน้ต)
- Shortcut ในเครื่องผู้ใช้: `AI SaveToNote` (ใช้จริง), `AI TestInput` (ทดสอบ คัดลอกค่าที่ได้รับ/ค่า TITLE ไปคลิปบอร์ด ลบได้ภายหลัง), `ทดสอบรายชื่อโน้ต`, `สร้าง Urgent Reminder` (ของเดิม ห้ามแตะ)
- ไฟล์ที่ผู้ช่วยเคยเห็น: modes.py, mode_flow.py, guardrails.py, reminders_tool.py, app_ui.py (BUILD v31) **ยังไม่เคยเห็น `mode_bar.py`**
- แชทใหม่ให้ผู้ใช้แนบ: handoff_v30.md, handoff_v29.md, handoff_v28.md, `modes.py`, `mode_bar.py`, `mode_flow.py`, `guardrails.py`, `app_ui.py`, `reminders_tool.py`, `overlays.py`, `ai_client.py` (ตอนเขียน flow) และ `test_note_save.py` ฉบับปัจจุบัน
