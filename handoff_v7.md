# Handoff v7.0 — AI เลขาส่วนตัว (Pythonista)

วันที่ 10 ต.ค. 2026 — ต่อจาก Handoff v6.0 (ผู้ใช้: Chana, ตอบภาษาไทย กระชับ, ทดสอบบน iPhone เอง)

## 1. กติกาการทำงานกับผู้ใช้
- ก่อนเขียนโค้ดใหม่ให้ยืนยันความต้องการก่อน แก้เฉพาะจุดที่จำเป็น ห้ามลองแก้แบบเดา ต้องมีหลักฐาน (debug.log / .ips / ภาพ error)
- ส่งไฟล์ฉบับเต็มพร้อมชื่อไฟล์และสิ่งที่เปลี่ยน ผู้ใช้แทนไฟล์เองในโฟลเดอร์ iCloud `secretary_ai`
  (`/Users/chanaimac/Library/Mobile Documents/iCloud~com~omz-software~Pythonista3/Documents/secretary_ai`)
- `app_ui.py` ยาวแล้ว งานใหม่ให้แยกเป็นโมดูลใหม่
- ทำทีละเรื่อง
- ฐานที่ผู้ใช้ยืนยันว่าทำงานได้: `app_ui.py`, `assistant_flow.py` (`_ActionRunner`, bound method, `ui.delay(...,0.3)`) ห้ามใช้ lambda/closure กับ callback ที่ซับซ้อน

## 2. สถานะ Phase 1
ทำงานแล้ว: สร้างเตือนลงลิสต์ "เลขา AI", ป๊อปอัปยืนยัน (ตกลง/ไม่เอา/ทำรายการใหม่), กันวันที่ซ้ำ (`date_guard.py`), ความจำแชท

### เรื่องที่ตัดสินใจแล้ว
- **เสียงนาฬิกาปลุก (สวิตช์ "ฉุกเฉิน" iOS 26.2)**: ผู้ใช้ทดสอบแล้วว่า Alarm ผ่านโมดูล `reminders` เป็นแจ้งเตือนธรรมดา ไม่พบ API ตั้งค่านี้ ผู้ใช้ **ไม่เอา** ทำใน Reminders ให้แจ้งเตือนปกติ ส่วนเสียงปลุกจริงจะทำ **โมดูลใหม่ให้ AI ตั้งนาฬิกาปลุกในแอป Clock** ภายหลัง (ยังไม่ได้เริ่ม ต้องหาวิธีก่อน เช่น Shortcuts)
- **ไม่ระบุเวลา**: บันทึกแบบ all-day ผ่าน EventKit (`objc_util`) ใน `reminders_tool._create_all_day` ยืนยันด้วย test_allday.py แล้วว่าสวิตช์เวลาปิด (iOS แจ้งเตือน 09:00 ตามตั้งค่าเครื่อง)

## 3. บั๊กที่เพิ่งพบและแก้ (รอผู้ใช้ทดสอบ)
อาการ: เลือก "ไม่ระบุเวลา" แล้วแอปเด้งไป Home ไม่บันทึก
- หลักฐาน: log หยุดที่ `flow: showing ConfirmOverlay` ทุกครั้ง; `.ips` = SIGSEGV ใน `-[SUIButton invokeAction:]` (ตอนแตะปุ่ม ไม่ใช่ ui.delay)
- ลองเปลี่ยนเป็นป๊อปอัปเดียว `NoTimeConfirmOverlay` (4 ปุ่ม: ตกลง(ไม่ระบุเวลา) / ระบุเวลา / ไม่เอา / ทำรายการใหม่) ผลคือเปลี่ยนจากเด้งเป็น Python exception ที่เห็นชัด:
  `AttributeError: 'NoTimeConfirmOverlay' object has no attribute 'remove_from_superview'` ที่ `overlays.py` `_Popup._close` (ConfirmOverlay เดิมก็เกิด error เดียวกันเมื่อกด)
- สาเหตุตามหลักฐาน: `ui.View` ใน Pythonista ที่ใช้อยู่ไม่มีเมธอด `remove_from_superview`
- แก้แล้ว (ส่งให้ผู้ใช้): `overlays.py` ฉบับล่าสุด `_close` ใช้เฉพาะ `self.superview.remove_subview(self)` พร้อมตัวกันปิดซ้ำ `_is_closing`
- **ต้องตรวจต่อ**: (ก) ไฟล์ overlays.py ที่ผู้ใช้ใช้ก่อนหน้า (ที่ไม่มี error นี้) อาจต่างจากสำเนาที่ผมใช้ ขอให้ผู้ใช้ส่งไฟล์ปัจจุบันถ้ายังมีปัญหา (ข) ทดสอบ 4 อย่าง: ตกลง(ไม่ระบุเวลา) ว่าไม่เด้งและสวิตช์เวลาใน Reminders ปิด, ระบุเวลา แล้วพิมพ์เวลา, ไม่เอา, ทำรายการใหม่ (ค) กดปุ่ม "ตกลง" ของการเตือนที่มีเวลาปกติ
- ถ้ายังเด้ง: ขอ `debug.log` ท้ายไฟล์ + `.ips` ล่าสุด log ใหม่มีบรรทัด `flow: showing NoTimeConfirmOverlay`, `on_ok button pressed`, `on_set_time button pressed`, `do_set_time running`, `reminders: saving all-day via EventKit`, `reminders: all-day saved`

## 4. ไฟล์ที่ส่งไปแล้ว (ฉบับแก้ไขนี้)
- `tools.py` (has_time, ข้อความ "(ไม่ระบุเวลา)"), `ai_client.py` (prompt: วันที่อย่างเดียวถ้าไม่มีเวลา, ไม่ถามเวลาเอง, ตอบเวลาต่อจากระบบถาม), `reminders_tool.py` (all-day EventKit), `assistant_flow.py` (ป๊อปอัปเดียว + `on_set_time`/`do_set_time`, `_keep_context`), `overlays.py` (`NoTimeConfirmOverlay`, `_close` ใหม่), `app_ui.py` (`_keep_context` ใน `_on_actions_done`)
- สคริปต์ทดสอบ: test_notime.py, test_allday.py (ใช้ได้), test_alarm.py

## 5. งานค้าง (ทำทีละเรื่อง)
1. ยืนยันบั๊กด้านบนผ่าน แล้วตรวจเรื่องวันเลื่อนข้ามวันของเวลาเย็น (เช่น 18:30 ใน GMT+7) ซึ่งยังไม่ได้ยืนยัน
2. **ดู/จัดการเตือนเดิม**: ดูของวันนี้/พรุ่งนี้/เดือน/ช่วงวัน จากลิสต์ "เลขา AI", ไม่แสดงรายการที่เสร็จแล้ว, ไม่ถามปี; ให้โค้ดตรวจเจตนาแล้วบังคับ `tool_choice` เรียก `list_reminders` (fallback auto เพราะ gemini-2.5-flash-lite เลือกเครื่องมือไม่เสถียรและเคยแต่งลิสต์เอง); แสดงทีละรายการเป็นป๊อปอัป "n/N": ตกลงเข้าใจแล้ว / งานนี้ยกเลิกแล้ว (ติ๊กเสร็จ) / ลบทิ้ง (ยืนยันซ้ำ) / หยุดดูต่อ — ต้องสร้างบนรูปแบบ `_ActionRunner` ที่ยืนยันแล้ว (bound method, `ui.delay` 0.3) และระวังไม่เปิดป๊อปอัปซ้อนในจังหวะเดียวกัน; ภายหลังอาจทำหน้าจอลิสต์แบบตาราง
3. ข้อความปิดงานทั่วไป ("จัดการให้เรียบร้อยแล้วครับ จะให้ช่วยเรื่องอะไรต่อไหมครับ") รวมกรณีไม่ใช่งานเตือน
4. โมดูลตั้งนาฬิกาปลุกในแอป Clock (ภายหลัง)
5. Phase 2 รายรับรายจ่าย (ตรวจโครงสร้างแอปเดิมก่อน ห้ามทำของเดิมเสีย) → Phase 3 หลักทรัพย์ → Phase 4

## 6. ข้อควรระวังทางเทคนิค
- Pythonista `ui.View` ไม่มี `remove_from_superview` ให้ใช้ `parent.remove_subview(view)`
- SIGSEGV จาก callback ของ Pythonista จับด้วย try/except ไม่ได้ ใช้ log + `.ips` เป็นหลักฐาน
- โมดูล `reminders` ของ Pythonista: due_date เป็นวันล้วนจะกลายเป็น 00:00 (สวิตช์เวลาเปิด) ต้องใช้ EventKit สำหรับ all-day
- API key อยู่ใน Keychain (`service=openrouter`, `account=api_key`), โมเดลเริ่มต้น `google/gemini-2.5-flash-lite`
