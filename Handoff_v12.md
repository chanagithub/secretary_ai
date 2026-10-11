# Handoff v12.0 — AI เลขาส่วนตัว (Pythonista 3 / iPhone)
วันที่ 11 ต.ค. 2026 (ต่อจาก v11.0)

## สถานะ
- Phase 1 (Reminders) ใช้งานได้บนเครื่องจริง: สร้าง/ค้น/ลบ/เลื่อน/ทำเสร็จ, ปลุกแบบ Urgent, ตารางผลค้น
- v12 แก้ 2 เรื่อง: (1) TypeError ตอนแสดงตารางผลค้น 4 รายการขึ้นไป -> ทดสอบแล้ว ไม่ error
  (2) AI ไม่เข้าใจคำถามย้อนหลัง/ก่อนวันที่ -> แก้แล้ว รอทดสอบบนเครื่อง
- Phase 2 (รายรับจ่าย), Phase 3 (หลักทรัพย์) ยังไม่เริ่ม
- หลักการ: โค้ดตรวจและทำจริง AI แค่แปลภาษา/เลือกเครื่องมือ, ยืนยันก่อนเขียน,
  ห้ามอ้างว่าสำเร็จโดยไม่มีหลักฐาน, งานใหม่แยกโมดูล ไม่ยัดเพิ่มใน app_ui.py

## [v12] แก้ TypeError ตารางผลค้น (บันทึกไว้เผื่อเจออีก)
อาการ: ผลค้น >= 4 รายการ ตารางขึ้นได้บางส่วน เลื่อนลงแล้วมีป๊อปอัปแดง
  TypeError: object of type 'int' has no len()
จุดที่ error (results_view.py, คลาส ResultsSource):
  - บรรทัด ~80 tableview_number_of_rows:  return len(self.sections[section][1])
  - บรรทัด ~85 tableview_title_for_header: title, rows = self.sections[section]; len(rows)
  - เกิดที่ section=2 (หมวดที่ 3 ถัดจาก "สิงหาคม") แปลว่าตอนตารางมาเรียก
    self.sections[n] กลายเป็นทูเพิลที่ช่อง [1] เป็นตัวเลข
สาเหตุ: build_sections() สร้างข้อมูลถูกต้องเสมอ (ทุกหมวดเป็น (ชื่อ, list))
  สันนิษฐานว่าชื่อแอตทริบิวต์ "sections" บน data source ถูกแก้หรือทับหลังสร้าง
  (อาจชนชื่อกับฝั่ง ui/native) — ยังไม่ได้ยืนยัน 100% แต่หลังแก้แล้วไม่เกิดอีก
วิธีแก้ (results_view.py -> ResultsSource ทั้งคลาส):
  1. ไม่ใช้ self.sections แล้ว: แยกเก็บเป็น self._titles และ self._rows (ชื่อ private) เป็น tuple แก้ไขไม่ได้
  2. ตรวจโครงสร้างตอน __init__: หมวดที่ผิดรูปจะถูกข้ามและจด log "results: bad section #i"
  3. _rows_of(section) กันพัง: index ผิด/ชนิดผิด -> คืน () พร้อมจด log แทนการ crash
  4. tableview_cell_for_row ตรวจ row อยู่ในช่วงก่อนใช้
  5. @_logged ครอบทุกเมธอด data source: error จะถูกจด traceback ลง debug.log
ถ้าเจออีก ให้ดู debug.log:
  - "results: source built sections=N counts=[...]" = ข้อมูลขาเข้า
  - "results: bad section" = ข้อมูลขาเข้าผิดตั้งแต่ build_sections/ผลค้น
  - "results: _rows_of ..." = มีอะไรไปแก้ข้อมูลทีหลัง
  - "results: <method> failed args=..." + traceback = เมธอดไหนพัง section ไหน
บทเรียน: data source ของ ui.TableView ให้เก็บข้อมูลด้วยชื่อ private (_xxx) และเป็น tuple
  ห้ามใช้ชื่อกลาง ๆ เช่น sections/items/data

## [v12] ค้นย้อนหลัง/ก่อนวันที่ — ให้โค้ดตัดสินเรื่องเวลาเอง
ปัญหาเดิม:
  - "ก่อนวันที่ 11 เดือน 10 2569 ได้ปันผลมากี่รายการ" -> โดน local_list_action แย่ง
    (คำว่า "รายการ" ใน "กี่รายการ", "วันนี้" ใน "ก่อนหน้าวันนี้") -> ตอบรายการรายวันของวันนี้
  - "ก่อนหน้านี้ทั้งหมดได้ปันผลมาเท่าไหร่" -> ไม่ถูกจับเป็นการค้นในเครื่อง ส่งให้ AI
    และ schema search_reminders ไม่มีช่อง when -> ได้ upcoming (ค่าเริ่มต้น) เสมอ
แก้ใน reminder_search.py:
  - _before_date_period: "ก่อน(วันที่) <วัน เดือน ปี>" เช่น ก่อนวันที่ 11 เดือน 10 2569,
    ก่อน 15/9/69, ก่อน 1 ตค 2569 -> period ตั้งแต่ 1900-01-01 ถึงก่อนวันนั้น, when='all'
    (ปี 2 หลัก: >=50 เป็น พ.ศ., <50 เป็น ค.ศ.; ไม่ระบุปี = ปีปัจจุบัน)
  - _PAST_PHRASES + _PAST_RE: ก่อนหน้านี้, ก่อนหน้าวันนี้, ในอดีต, ที่ผ่านมา, ย้อนหลัง,
    จนถึงวันนี้, เคยได้, "ได้...มา" (ยกเว้นประโยคที่มี "จะได้") -> when='past'
    (ฝังในโค้ด เสริมจาก search_terms.json ไม่แทนที่)
  - question_kind(): amount (เท่าไหร่/ยอดรวม/กี่บาท), count (กี่รายการ/กี่ครั้ง), list
  - _QUESTION_WORDS เพิ่ม เท่าไหร่/เท่าไร/กี่รายการ/กี่ครั้ง/กี่บาท/กี่งวด
  - wants_search(text): มีหัวข้อค้น + มีสัญญาณคำถาม/ช่วงเวลา
  - apply_text_hints(args, text): ทับ period/when/ask ที่ AI ส่งมา ด้วยที่โค้ดอ่านได้
  - schema search_reminders เพิ่มช่อง when (enum upcoming/past/all)
  - ask_note(): ถามยอดเงิน -> บอกตรง ๆ ว่ายังรวมยอดไม่ได้ แสดงรายการแทน
  - ลำดับความสำคัญของช่วงเวลา: ก่อน<วันที่> > เดือน+ปีชัดเจน > เดือนที่แล้ว/ปีที่แล้ว
  - รันไฟล์ตรง ๆ จะพิมพ์ผลอ่านประโยคตัวอย่าง (self-test)
แก้ใน assistant_flow.py:
  - local_list_action: ถ้า wants_search() -> None; ตัดวลี ก่อนหน้าวันนี้/ก่อนวันนี้/
    จนถึงวันนี้/ถึงวันนี้/ตั้งแต่วันนี้ ออกก่อนตรวจคำว่า "วันนี้"
  - ask_ai: ส่ง ask ไปกับการค้นในเครื่อง; การค้นที่ผ่าน AI (และ pseudo tool-call)
    ผ่าน apply_text_hints เสมอ; log "flow: local search ..." / "flow: AI search ..."
  - show_search: แนบ ask_note ทั้งแบบข้อความและแบบตาราง
ผลที่คาดหวัง (self-test):
  | ประโยค                                   | when     | period          | ask    |
  | ก่อนวันที่ 11 เดือน 10 2569 ...กี่รายการ    | all      | ก่อน 11/10/2026 | count  |
  | ก่อนหน้านี้ทั้งหมด...เท่าไหร่                | past     | -               | amount |
  | ช่วยหาเงินปันผล ในอดีต                      | past     | -               | list   |
  | ปันผล กย 2569                             | all      | 09/2026         | list   |
  | ปันผลก่อน 15/9/69                         | all      | ก่อน 15/09/2026 | list   |
  | ปันผลวันไหน                               | upcoming | -               | list   |
ยกเลิก: time_hints.py ที่เคยเสนอ — ไม่ต้องสร้าง (รวมไว้ใน reminder_search.py กันโค้ดซ้ำ)

## ปลุก (Urgent) ผ่าน Shortcut (เหมือน v11)
- Shortcut "สร้าง Urgent Reminder" รับ JSON {"title","due":"YYYY-MM-DD HH:MM","notes"}
- Get dictionary from Shortcut Input -> Get Value title/due -> Get dates from due ->
  Add to ลิสต์ "เลขา AI" + Alert At Time = Dates, Urgent ON -> Stop and output
- บั๊กเก่า: ช่อง "to" เป็นชิป Shortcut Input -> Conversion Error; แก้โดย Clear Variable แล้วเลือกลิสต์
- เรียกจาก reminders_tool.create_reminder ผ่าน shortcuts://x-callback-url/run-shortcut?...
  เข้ารหัสด้วย urlencode(..., quote_via=quote) (ช่องว่างต้องเป็น %20)
- แวบไป Shortcuts แล้วกลับ = ปกติ; ข้อความ "ยังยืนยันการสร้างไม่ได้" ตั้งใจ

## ปลุกที่ไม่บอกวัน (assistant_flow.py) (เหมือน v11)
- "ปลุกตอนเจ็ดโมงเช้า" -> ครั้งถัดไปที่จะถึง; ถามวันแล้วตอบสั้น (<=40 ตัวอักษร) รวมกับคำสั่งเดิม (จำ 5 นาที ใช้ครั้งเดียว)

## ค้นรายการ (reminder_search.py)
- when: upcoming (ค่าเริ่มต้น) / past / all; period กรองช่วง
- เดือน+ปีชัดเจน (กย 2569, กันยายน 2026, เดือนเก้าปี 2026, 9/2569) -> ทั้งเดือน when='all'
- [v12] ก่อน<วันที่>, คำบอกอดีต, ชนิดคำถาม (ดูหัวข้อด้านบน)
- ข้อจำกัด: ยอดเงินอยู่ในชื่อรายการแบบข้อความอิสระ ยังไม่รวมยอด
  (รูปแบบชื่อมีหลายแบบ เช่น "X pay dividends 0.25 bahts per unit", "ได้รับปันผลจาก scbpind 27456.78 +4352.63")
  ต้องตกลงรูปแบบดึงตัวเลขก่อน (ผูกกับ Phase 3)

## ตารางผลค้น (results_view.py)
- >= 4 รายการ (TABLE_THRESHOLD = 3) แสดงเป็นตาราง อ่านอย่างเดียว จัดกลุ่มตามเดือน,
  ไม่มีวัน = "ไม่ได้กำหนดวัน", เสร็จแล้วมี ✓ สีเทา, ปุ่ม "ปิด" ปุ่มเดียว
- น้อยกว่านั้นแสดงเป็นข้อความในแชท

## บทเรียนกันล่ม
- SIGSEGV ใน ui.delay/callback ปุ่ม: ใช้ bound method ไม่ใช้ closure/lambda, ไม่ streaming ตอนรอ,
  ui.View ไม่มี remove_from_superview (ใช้ superview.remove_subview + กันปิดซ้ำ), เก็บ view ที่ปิดใน _RETIRED
- [v12] data source ของ TableView: ชื่อแอตทริบิวต์ private + tuple + ตรวจ index (ดูหัวข้อ TypeError)
- ปิดแอปให้สนิทแล้วรันใหม่หลังแทนไฟล์ ไม่งั้นอาจใช้โมดูลเก่าที่โหลดค้าง
- ล่มที่ปุ่ม ConfirmOverlay ครั้งหนึ่งยังไม่ทราบสาเหตุ ไม่เกิดซ้ำ; เก็บ log "popup:" ไว้

## ค้างทำ
1. ทดสอบ v12 บนเครื่อง: รัน reminder_search.py ตรง ๆ เทียบตาราง + ถาม 2 คำถามเดิมในแอป
   ถ้ารูปที่ 1 ยังได้ "ไม่มีรายการเตือนที่ยังไม่เสร็จ..." = app_ui มีตัวดักอื่นก่อน local_list_action
   -> ต้องขอดูส่วนของ app_ui ที่รับข้อความตอนกด "ส่ง"
2. คืนค่า x-error ใน reminders_tool.py โดยไม่กลืนข้อความ error
3. ปรับข้อความแชทหลังส่ง Shortcut (ถ้าต้องการ)
4. ลบ debug log เมื่อเสถียร (รวม @_logged และ log "results: source built" ใน results_view.py,
   log "flow: local/AI search" ใน assistant_flow.py)
5. รวมยอดเงินปันผล (ต้องตกลงรูปแบบดึงตัวเลขก่อน)
6. Phase 2 (รายรับจ่าย — แอปเดิมต้องไม่พัง), Phase 3 (หลักทรัพย์), Phase 4 ขัดเกลา
7. ตารางผลค้นยังอ่านอย่างเดียว (ไม่มีปุ่มแก้/ลบรายแถว)

## ไฟล์ที่เปลี่ยนใน v12
- results_view.py (ResultsSource เขียนใหม่ แก้ TypeError)
- reminder_search.py (ก่อน<วันที่>, คำบอกอดีต, question_kind, wants_search, apply_text_hints, ask_note, schema when)
- assistant_flow.py (local_list_action, ask_ai, show_search)