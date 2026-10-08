# test_ai_tools.py (อัปเดต)
"""ทดสอบ tool calling ด้วยมือผ่าน console แบบครบวงจร
พิมพ์ประโยคสั่ง -> AI ตีความ -> ตรวจค่า -> ถามยืนยัน -> บันทึกจริงถ้า y
"""
import ai_client
import tools
import reminders_tool

token = ai_client.CancelToken()

while True:
    user_text = input('\nพิมพ์คำสั่ง (ว่างเพื่อออก): ').strip()
    if not user_text:
        break

    def on_chunk(piece):
        print(piece, end='', flush=True)

    try:
        text, tool_calls = ai_client.stream_chat_with_tools(
            user_text, on_chunk, token, tools.ALL_TOOLS)
    except ai_client.AIError as e:
        print('\nเกิดข้อผิดพลาด:', e)
        continue

    print()
    if not tool_calls:
        print('(AI ไม่ได้เรียกเครื่องมือใด ๆ)')
        continue

    for call in tool_calls:
        if call['name'] != 'create_reminder':
            continue
        try:
            validated = tools.validate_create_reminder(call['arguments'])
        except tools.ToolValidationError as e:
            print('ตรวจค่าไม่ผ่าน:', e)
            continue

        print(tools.format_confirm_text(validated))
        answer = input('ยืนยันสร้างจริงไหม (y/n): ').strip().lower()
        if answer == 'y':
            reminders_tool.create_reminder(
                title=validated['title'],
                due_date=validated['due_date'],
                notes=validated['notes'],
            )
            print('บันทึกเรียบร้อย เช็กในแอป Reminders ได้เลย')
        else:
            print('ยกเลิก ไม่บันทึก')