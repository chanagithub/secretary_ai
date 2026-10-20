# บทเรียน: ใช้ค่า Dictionary ใน Shortcut กับเงื่อนไข

เมื่อดึงค่าจาก Dictionary แล้วนำไปใช้ในเงื่อนไขของ Shortcut เช่น `Find Notes` → `Name contains` ให้แทรกแอ็กชัน `Text` เพื่อแปลงค่า `Dictionary Value` เป็นข้อความก่อน แล้วใช้ผลลัพธ์จาก `Text` ในเงื่อนไข

ถ้าใช้ `Dictionary Value` โดยตรง เงื่อนไขอาจไม่กรองตามค่าที่คาดไว้ และ `Find Notes` อาจคืนผลลัพธ์แรกตามการเรียงลำดับแทน

กรณีโหมดโน้ต: ใช้ค่า `TITLE` ที่แปลงเป็น Text ใน `Name contains`; คง `Folder is เลขา AI` ไว้ และให้ `Append to Note` รับโน้ตที่เป็นผลลัพธ์จาก `Find Notes` (คลิปบอร์ดเก็บข้อความชื่อ ไม่ใช่โน้ตปลายทาง)
