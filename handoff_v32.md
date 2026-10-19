# Handoff v32 — AI เลขาส่วนตัว (Pythonista 3 / iPhone) — โหมดโน้ต: เขียนโมดูล 3 ไฟล์แล้ว เหลือเชื่อมเข้าแอป (ขั้น 4)
วันที่ 19 ต.ค. 2026 ~18:30 — ต่อจาก handoff_v31.md (อ่าน v31, v30, v29, v28 ประกอบ: กติกา แผนทีละขั้น ข้อตกลงออกแบบโหมดโน้ต; ที่ขัดกัน ใช้ไฟล์นี้)
ผู้ใช้: Chana — ตอบไทย กระชับ ทำทีละเรื่อง ยืนยันความเข้าใจก่อนเขียนโค้ด แก้เฉพาะจุด ห้ามแก้ไฟล์ ChanaFinance ผู้ใช้ทดสอบบน iPhone เอง เครดิตหมดบ่อย: จบแต่ละขั้นให้เขียน handoff ใหม่
ความเป็นส่วนตัว: โน้ตของผู้ใช้มีข้อมูลส่วนตัว (บัญชี รหัส โทเค็น) ขอให้ผู้ใช้ครอบ/เบลอภาพคอนโซล ห้ามคัดลอกชื่อโน้ตจริงลง handoff

## 1. ข้อตกลงที่ใช้อยู่ (สรุป)
- เครื่องผู้ใช้ iOS 27 · ใช้เฉพาะโน้ตใน On My iPhone โฟลเดอร์ **เลขา AI** (มีเว้นวรรค) ไม่ใช้ iCloud ไม่ใช้โฟลเดอร์ย่อย (Shortcuts ไม่มี action ลิสต์โฟลเดอร์; Find Notes ตัวกรอง Folder is ไม่รวมโฟลเดอร์ย่อย)
- ต้องลิสต์โน้ตให้ได้จำนวนมากที่สุด (ปิดสวิตช์ Limit แล้ว)
- ต่อโน้ตเดิม: **ชื่อโน้ตมาจากรายการจริงที่ผู้ใช้เลือกเท่านั้น AI ไม่กำหนดชื่อ** (ผู้ใช้เสนอ); ชื่อซ้ำ/ซ้อนกัน -> แอปเตือนและไม่ส่ง (เพราะ Shortcut ใช้ Name **contains** ซึ่งเปลี่ยนเป็น is ไม่ได้) ทางเลือกอนาคต: แก้ Shortcut ให้เทียบชื่อตรงตัวเอง (ยังไม่ได้ลอง)
- สร้างใหม่: AI เสนอชื่อ -> ใช้ชื่อนี้ / พิมพ์ชื่อเอง -> หน้ายืนยัน; ต่อท้ายใส่หัวข้อวันที่ เช่น "19 ต.ค. 2026" นำหน้า สร้างใหม่ไม่ใส่วันที่
- ผลลัพธ์ข้อความกลาง ๆ "ส่งคำสั่งไปยัง Shortcut แล้ว" (Python ยืนยันว่าโน้ตถูกสร้างไม่ได้)

## 2. Shortcut ในเครื่องผู้ใช้ (ยืนยันแล้วบนเครื่องจริง)
- `AI SaveToNote`: ทาง `new` = Create note (Name = TITLE, เนื้อหา = BODY, โฟลเดอร์ เลขา AI, **Open When Run ปิดแล้ว**) ใช้ได้; ทางอื่น = Find Note (Name contains TITLE, Folder is เลขา AI, Latest First, Limit 1) + Append (BODY) to Note ใช้ได้ (ผู้ใช้เลือกตัวแปร Dictionary Value ใหม่เองให้ตรง TITLE/BODY แล้ว); Stop and output อยู่ท้ายสุดหลัง End If ใช้ได้
- `ทดสอบรายชื่อโน้ต`: Find Notes (Folder is เลขา AI, Limit ปิด) -> ชื่อ -> คัดลอกคลิปบอร์ด ใช้ได้ (ทดสอบกับโน้ต 2 รายการ ยังไม่ทดสอบกับจำนวนมาก; ถ้าติด ให้เปิด Settings -> Shortcuts -> Advanced -> Allow Sharing Large Amounts of Data)
- ชื่อ Shortcut ต้องตรงทุกตัวอักษรรวมวรรณยุกต์ (ตัวที่ใช้ในโค้ดสะกด "ทดสอบรายชื่อโน้ต"); ตั้งเป็นค่าคงที่บนสุดของ `notes_shortcut.py` ถ้าผู้ใช้เปลี่ยนชื่อ ให้แก้ที่นั่นที่เดียว

## 3. ไฟล์ที่ส่งให้ผู้ใช้แล้ว (วางในโฟลเดอร์ secretary_ai)
| ไฟล์ | หน้าที่ | ทดสอบ |
|---|---|---|
| `notes_shortcut.py` | `NoteListReader(on_done,on_error).start()` อ่านรายชื่อโน้ตผ่านคลิปบอร์ด (ไม่บล็อกหน้าจอ ใช้ ui.delay, รอ 30 วินาที), `send_save(mode,title,body)` ส่ง JSON key MODE/TITLE/BODY ตัวใหญ่, `build_save_url`, `parse_names` | บนเครื่อง: อ่านรายชื่อ OK; send_save เดี่ยว ๆ OK |
| `notes_tools.py` | schema เครื่องมือ `save_note(content,title)`, `system_prompt`, `validate_call` (เนื้อหา AI ต้องเป็นส่วนของคำพูดผู้ใช้และครอบคลุม >=70% ไม่งั้นใช้คำพูดผู้ใช้ตัดคำสั่งนำหน้า), `strip_command`, `build_body`, `find_conflicts/conflict_text`, ข้อความหน้ายืนยัน, `SENT_LINE` | บนเครื่อง: `test_notes_tools.py` ผ่าน |
| `notes_flow.py` | `ask_ai`, `prepare_actions`, `run_actions(host, actions, on_done(lines, redo, saved))` ลำดับ: ใหม่/ต่อ -> (ใหม่: ใช้ชื่อ/พิมพ์ชื่อ) (ต่อ: อ่านรายชื่อ -> เลือกโน้ตจาก ListPickOverlay -> ตรวจซ้ำ/ซ้อน) -> ConfirmOverlay -> ส่ง Shortcut ใช้ ChoiceOverlay/ConfirmOverlay (overlays.py) และ ListPickOverlay/TextInputOverlay (finance_overlays.py) | **ทดสอบในเครื่องผู้ช่วยด้วยป๊อปอัปจำลองเท่านั้น ยังไม่เคยรันบน iPhone** |
- สคริปต์ทดสอบ: `test_notes_shortcut.py` (DO_SAVE=False อ่านรายชื่อ / True ต่อด้วยสร้างโน้ตทดสอบ), `test_notes_save_only.py`, `test_notes_tools.py`
- **ผลค้าง:** `test_notes_shortcut.py` ตอน DO_SAVE=True (อ่านรายชื่อ แล้วเรียก send_save ทันที) **ไม่สร้างโน้ต** ทั้งที่ send_save เดี่ยว ๆ สร้างได้ สมมติฐาน (ยังไม่พิสูจน์): เรียก Shortcut ซ้อนติดกันหลังกลับจาก Shortcut แรก iOS ไม่รับ ในแอปจริงมีป๊อปอัปคั่นหลายวินาที ให้ตรวจซ้ำตอนทดสอบทั้งระบบ ถ้ายังไม่สร้าง ลองหน่วงก่อนส่ง (เช่น ui.delay 1-2 วินาที)

## 4. ขั้นถัดไป: ขั้น 4 เชื่อมเข้าแอป (ส่งฉบับเต็มทีละไฟล์ ให้ผู้ใช้วางครบแล้วปิด Pythonista สนิท)
ผู้ช่วยเห็นไฟล์จริงของผู้ใช้แล้ว (ต้องขอฉบับล่าสุดจากผู้ใช้อีกครั้งในแชทใหม่ก่อนแก้): modes.py, mode_bar.py, mode_flow.py, guardrails.py, app_ui.py (BUILD v31), reminders_tool.py, overlays.py, ai_client.py, finance_flow.py, finance_overlays.py
1. `modes.py`: เพิ่ม `NOTES = 'notes'`, ใน KEYS, LABELS (เสนอชื่อ "โน้ต"), ENABLED (ตอนนี้ `{REMINDERS, ACCOUNTS}`)
2. `mode_bar.py`: ตอนนี้หาร `modes.KEYS` เท่ากัน ใช้ฟอนต์ 13 -> ลอง 4 ปุ่มก่อน ถ้า "รายรับรายจ่าย" ถูกตัด ลดฟอนต์ หรือใช้ปุ่ม "•••" เป็นเมนูแยก (ยังไม่ได้ตกลงกับผู้ใช้ ถือว่าตกลงตามข้อเสนอ ถ้าไม่ท้วง)
3. `guardrails.py`: เพิ่ม `NOTES`; `mode_hint` ในโหมดโน้ต **ไม่เตือนสลับโหมดเลย** (เนื้อโน้ตมีคำอย่าง "นัด" "บาท" ได้); จากโหมดอื่นตรวจโหมดโน้ตเฉพาะคำว่า "โน้ต"/"โน๊ต" (ผู้ใช้สะกดทั้งสองแบบ) ให้ชนะคำการเงิน/เตือน?? (ตัดสินใจตอนเขียน ต้องไม่ทำให้ "เตือน...โน้ต" เพี้ยน ทดสอบด้วยภาษาไทยล้วน)
4. `app_ui.py` ใน `begin_request_unchecked`: ตอนนี้ `self._active_flow = finance_flow if mode == ACCOUNTS else assistant_flow` ต้องเพิ่ม notes_flow ด้วยบรรทัดน้อยที่สุด (import notes_flow; ถ้า mode == NOTES -> `self.start_request(text, text)` ทันที ข้ามเส้นทางเตือนความจำ); `_memory_messages` ใส่สแนปช็อตรายการเตือนเป็น role system ซึ่ง notes_flow.ask_ai ตัดออกให้แล้ว
5. ทดสอบบนเครื่อง (ขั้น 5): สร้างใหม่ (ใช้ชื่อที่เสนอ / พิมพ์ชื่อเอง), ต่อโน้ตเดิม (เลือกจากรายการ), ชื่อซ้อนกัน/ซ้ำ (ต้องเตือนไม่ส่ง), ยกเลิก, ทำรายการใหม่, อ่านรายชื่อล้มเหลว (ไม่กด Allow Paste) ต้องไม่อ้างว่าสำเร็จ, ตรวจผลค้างข้อ 3 (ส่งซ้อนติด)
6. ถ้าผ่านแล้ว: เปลี่ยนชื่อ `ทดสอบรายชื่อโน้ต` เป็นชื่อถาวร (แก้ค่าคงที่), ลบ Shortcut ทดสอบเก่า (`AI TestInput`, "Show Notes Folder")

## 5. ไฟล์ที่ให้ผู้ใช้แนบในแชทใหม่
handoff_v32.md, handoff_v31.md, `modes.py`, `mode_bar.py`, `guardrails.py`, `app_ui.py` (ฉบับที่ติดตั้งอยู่ตอนนั้น), `notes_shortcut.py`, `notes_tools.py`, `notes_flow.py`; (ถ้าต้องดูแบบอ้างอิง) `mode_flow.py`, `overlays.py`, `finance_flow.py`
