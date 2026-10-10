# Handoff v10.0 — AI เลขาส่วนตัว (Pythonista + OpenRouter)

วันที่: 10 ต.ค. 2026  
ผู้ใช้: Chana  
เอกสารนี้รวมบริบทสำคัญจาก Handoff v1.0 และสถานะงานปัจจุบันเรื่อง Urgent Reminder เพื่อให้ผู้รับช่วงต่อเริ่มทำงานได้จากจุดล่าสุด

## 1. เป้าหมายโปรเจกต์และหลักการจาก v1.0

สร้างแอป AI เลขาส่วนตัวใน Pythonista บน iPhone รับข้อความ/Dictation ภาษาไทย และใช้ OpenRouter ช่วยแปลเจตนา โดยให้โค้ดเป็นผู้ตรวจและทำงานจริง:

1. Reminders: สร้าง อ่าน ค้นหา และจัดการรายการเตือน
2. รายรับรายจ่าย: เชื่อมแอปค่าใช้จ่ายเดิม
3. การลงทุน: เชื่อมไฟล์และบัญชีลงทุนเดิมภายหลัง

หลักการที่ยังใช้:

- AI แปลภาษาและเลือกเครื่องมือ; โค้ดอ่าน/ตรวจ/คำนวณ/บันทึกจากข้อมูลจริง
- ยืนยันก่อนเขียนข้อมูล
- AI ห้ามแต่งว่าบันทึกสำเร็จถ้ายังไม่มีผลยืนยันจากระบบ
- ส่งข้อมูลส่วนตัวให้ OpenRouter เท่าที่จำเป็น และเก็บ API key ใน Keychain
- ทำทีละเฟส: Reminders ก่อน แล้วรายรับรายจ่าย แล้วการลงทุน
- Pythonista ทำงานเบื้องหลังไม่ได้; การเตือนให้ใช้ Reminders ของ iPhone

Handoff v1.0 ลงวันที่ 7 ต.ค. 2026 ระบุว่าโครงการยังไม่เริ่มเขียนโค้ด ณ วันนั้น แต่สถานะปัจจุบันพัฒนาไปไกลแล้ว จึงใช้ v1.0 เป็นบริบท/หลักการตั้งต้น ไม่ใช่สถานะปัจจุบัน

## 2. สถานะการใช้งานที่ยืนยันภายหลัง

- โครงแอป Pythonista, OpenRouter, tool calling, UI ยืนยัน และประวัติคำสั่งมีแล้ว
- การสร้าง/อ่าน/ค้นและจัดการ Reminders พัฒนาต่อจาก v1.0 แล้ว
- มีไฟล์พจนานุกรมคำค้น `search_terms.py` และไฟล์ข้อมูล `search_terms.json` พร้อมเมนูจัดการ
- การเข้าใจเวลาไทยดีขึ้น รวมคำอย่าง “ตีห้า” และ “หกโมงเช้า” แต่ยังควรยืนยันจากการใช้งานจริงเมื่อมีปัญหา
- โปรเจกต์มีไฟล์สำเนาใต้ `outputs/`; การเปลี่ยนไฟล์เหล่านั้นไม่อัปเดตโฟลเดอร์ Pythonista บน iPhone อัตโนมัติ

## 3. ข้อตกลงเรื่องการปลุก

- ใช้ **Urgent Reminder** ที่มีเสียงปลุกยาวเฉพาะเมื่อผู้ใช้สั่งให้ปลุกโดยตรง เช่น “ช่วยปลุกผมพรุ่งนี้ตีห้า”
- Reminder งาน/นัดหมายทั่วไปให้เป็นการเตือนปกติ แม้มีวันเวลา ห้ามเปิด Urgent โดยอัตโนมัติ
- สร้าง Urgent ผ่าน Apple Shortcut ชื่อ **`สร้าง Urgent Reminder`**
- ผู้ใช้เลือก **Always Allow** สำหรับการเรียก Shortcut แล้ว และทดสอบ Shortcut สร้าง Urgent ได้
- ปัญหาก่อนหน้าคือแอปแสดงข้อความว่าส่งคำสั่งแล้ว แต่บางครั้ง Reminder ไม่ถูกสร้าง/แอปกลับ Home Screen; log เก่าพิสูจน์เพียงว่าเปิด Shortcut ไม่ได้ยืนยันว่าบันทึกสำเร็จ จึงควรทดสอบ end-to-end และอย่ารายงานว่าสร้างแล้วโดยไม่มีหลักฐาน

## 4. ข้อมูลที่ Pythonista ส่งเข้า Shortcut

โค้ดเรียก Shortcut ด้วย **ชื่อ Shortcut** `สร้าง Urgent Reminder` และส่ง Shortcut Input เป็น JSON Dictionary ตัวอย่าง:

```json
{"title":"ปลุกผม","due":"2026-10-11 05:00","notes":""}
```

ความหมาย:

- `title` คือ key ใน JSON; ค่าของมันคือข้อความชื่อ Reminder เช่น `ปลุกผม`
- `due` คือ key ใน JSON; ค่าของมันคือวันและเวลา
- `notes` คือ key รายละเอียด (อาจว่าง)
- Pythonista ไม่ได้ส่ง Magic Variable ชื่อ `ReminderData`; มันส่งข้อมูล JSON ผ่าน Shortcut Input

## 5. ชื่อ Dictionary ใน Shortcut — แก้ความสับสนให้ชัด

- `Get Dictionary from Shortcut Input` แปลง Shortcut Input เป็น Dictionary
- ผู้ใช้ตั้งชื่อ Magic Variable ของ Dictionary นี้ว่า **`ReminderData`**
- ชิปที่เห็นเป็น `R...` ในภาพคือ Magic Variable **`ReminderData`** (UI ตัดชื่อให้สั้น) ไม่ใช่ key และไม่ใช่ Reminder ที่สร้างแล้ว
- ทั้งสองการ์ด `Get Value` ต้องอ่านจาก Dictionary เดียวกันนี้:
  - `Get Value for title in ReminderData`
  - `Get Value for due in ReminderData`
- `title` และ `due` ในช่อง `for` คือ key ภายใน Dictionary
- ผลจาก `Get Value for title` คือข้อความที่จะกลายเป็นชื่อ Reminder
- ผลจาก `Get Value for due` ถูกส่งเข้า `Get dates from due` เพื่อแปลงข้อความเป็นวันที่/เวลา
- อย่าเปลี่ยนชื่อ Dictionary หรือเรียกมันว่า `title`; นั่นทำให้สับสนกับ key `title`
- สี/ไอคอนของ Magic Variable อาจมาจากแอ็กชันต้นทาง อย่าใช้สีอย่างเดียวตัดสินชนิดหรือเนื้อหาของตัวแปร

## 6. โครงสร้าง Shortcut ล่าสุดตามภาพผู้ใช้

ลำดับที่ผู้ใช้ตั้งไว้:

1. `Receive Apps and 18 more from Nowhere` — คงไว้เพื่อรับ Shortcut Input
2. `Get Dictionary from Shortcut Input`
3. `Get Value for title in ReminderData`
4. `Get Value for due in ReminderData`
5. `Get dates from due`
6. `Add [ผลจาก Get Value for title] to [Launch Date] with [Alert At Time] [ผล Dates]`
7. `Stop and Output New Reminder` — คงไว้เพื่อคืนผลจาก Shortcut

### หลักฐานจากภาพ

- ภาพทดสอบ `New Reminder` วันที่ 10 ต.ค. แสดง `Launch Date` + `Alert At Time` และเปิดสวิตช์ `Urgent` อยู่
- ภาพ Shortcut หลักช่วง 23:20–23:21 แสดงการ์ด `Add` ตั้ง `Launch Date`, `Alert At Time`, และเลือกผล `Dates`; Dynamic Island แสดงสัญลักษณ์ปลุก
- ภาพ 22:48 ของการ์ด `Add ... with Dates` แบบเดิมแสดงเพียง `Flag` และไม่มี `Urgent`; ต้องใช้รูปแบบ Launch Date + Alert At Time เพื่อให้ตัวเลือก Urgent แสดง
- ภาพ 23:36 ผู้ใช้ยืนยันว่า `R...` คือ `ReminderData`; สองการ์ด Get Value อ้างตัวแปรนี้แล้ว

### จุดที่ยังต้องยืนยันก่อนบอกว่าเสร็จ

ภาพรวมล่าสุดดูถูกทิศทาง แต่ภาพไม่แสดงการ์ด Add ทั้งหมดในภาพเดียว จึงยังต้องตรวจ/ทดสอบว่า:

- ช่องชื่อใน `Add` ใช้ผลลัพธ์จาก `Get Value for title` (ข้อความจาก key `title`)
- ลิสต์ปลายทางคือ `เลขา AI`
- Launch Date/Alert At Time ใช้ผล `Dates` จาก `Get dates from due` และเวลาถูกต้อง
- สวิตช์ `Urgent` เปิดอยู่
- `Stop and Output New Reminder` คืนผลหลังสร้าง
- เรียกจาก Pythonista ด้วย JSON จริงแล้วรายการปรากฏใน Reminders และ Urgent ทำงาน

อย่าให้ผู้ใช้ลบ/เพิ่มการ์ดที่ตั้งถูกแล้วโดยไม่มีหลักฐานจากภาพ ตรวจทีละประเด็นและใช้ชื่อ action ภาษาอังกฤษตรงตามหน้าจอผู้ใช้

## 7. สถานะโค้ดและการแก้ปัญหา

ไฟล์ที่เกี่ยวข้องใน `outputs/` ได้แก่ `assistant_flow.py`, `tools.py`, `ai_client.py`, `reminders_tool.py` และเอกสารตั้งค่า Shortcut/ทดสอบ ผู้ใช้ติดตั้งหรือคัดลอกไฟล์ไป Pythonista ด้วยตนเองตามวิธีเดิม สำเนาใน `outputs/` ไม่ได้แก้ไฟล์บน iPhone โดยอัตโนมัติ

งานที่ค้างในตอนรับช่วงต่อคือการทดสอบ Shortcut end-to-end หลังจัด mapping ตัวแปร ไม่ใช่รื้อระบบค้น Reminder หรือแก้โค้ดส่วนอื่นโดยไม่มีปัญหาใหม่

## 8. วิธีสื่อสารต่อจากนี้

- ตอบภาษาไทย กระชับ และยึดชื่อ action ภาษาอังกฤษที่เห็นจริงใน Shortcuts
- ผู้ใช้เหนื่อยและสับสนจากคำแนะนำที่ขัดกัน ให้ขอโทษสั้น ๆ แล้วให้ทีละขั้น
- แยกให้ชัดระหว่าง **ชื่อ Shortcut**, **Shortcut Input**, **Dictionary/Magic Variable `ReminderData`**, **key `title`/`due`**, และ **ค่าที่ดึงออกมา**
- อย่าบอกว่า `title` เป็นชื่อ Dictionary; Dictionary ชื่อ `ReminderData`, ส่วน `title` เป็น key และค่าที่ดึงจาก key นี้เป็นชื่อ Reminder
- ไม่ต้องถามให้ผู้ใช้ยืนยันสิ่งที่ภาพแสดงชัดอยู่แล้ว; หากภาพไม่พอ ให้ขอเฉพาะภาพ/ข้อมูลที่จำเป็นต่อขั้นนั้น

