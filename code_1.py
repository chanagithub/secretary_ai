# test_ai_tools.py
"""ทดสอบ tool calling ด้วยมือผ่าน console (ยังไม่ต่อ ConfirmOverlay จริง)
พิมพ์ประโยคสั่ง ดูว่า AI เรียก create_reminder ถูกไหม
และตัวตรวจค่าใน tools.py ทำงานถูกไหม
"""
import ai_client
import tools

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
        print('--- AI เรียกเครื่องมือ:', call['name'], '---')
        print('อาร์กิวเมนต์ดิบ:', call['arguments'])
        if call['name'] == 'create_reminder':
            try:
                validated = tools.validate_create_reminder(call['arguments'])
            except tools.ToolValidationError as e:
                print('ตรวจค่าไม่ผ่าน:', e)
                continue
            print(tools.format_confirm_text(validated))