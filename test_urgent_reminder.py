"""ทดสอบสร้าง Reminder แบบ Urgent ผ่าน Apple Shortcuts บน iPhone

ก่อนรัน ต้องสร้าง Shortcut ชื่อ "ทดลองสร้าง Urgent Reminder" ตามคู่มือ
ไฟล์นี้จะเรียก Shortcut และส่งชื่อรายการทดสอบไปให้
"""

try:
    import shortcuts
except ImportError:
    raise SystemExit("ไฟล์นี้ต้องรันใน Pythonista บน iPhone/iPad")

SHORTCUT_NAME = "ทดลองสร้าง Urgent Reminder"
TEST_TITLE = "ทดสอบ Urgent จาก Pythonista"

try:
    shortcuts.open_shortcuts_app(
        name=SHORTCUT_NAME,
        shortcut_input=TEST_TITLE,
    )
    print("เปิด Shortcut แล้ว กรุณาตรวจว่าได้สร้างรายการทดสอบและเปิด Urgent อยู่")
except Exception as error:
    print("เรียก Shortcut ไม่สำเร็จ: {}".format(error))
    print("ตรวจชื่อ Shortcut และเวอร์ชัน iOS แล้วลองอีกครั้ง")
