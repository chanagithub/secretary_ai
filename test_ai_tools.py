# test_ai_tools.py
"""ทดสอบ tool calling ด้วยมือผ่าน console แบบครบวงจร

พิมพ์/พูดประโยคสั่ง -> AI ตีความ (หรือถามกลับ) -> ตรวจค่า -> ถามยืนยัน -> บันทึกจริงถ้าตอบ "ใช่"

- ออกจากโปรแกรมด้วยการพิมพ์ q หรือ "ออก" เท่านั้น (ช่องว่างจะไม่ออก)
- คำตอบยืนยันโค้ดเป็นคนอ่านเอง (ไม่ผ่าน AI):
    ใช่ / ตกลง / บันทึก / ยืนยัน / y  -> บันทึก
    ไม่ / ยกเลิก / n                  -> ไม่บันทึก
    ทำใหม่ (เช่น "ไม่บันทึก ทำใหม่")   -> ไม่บันทึก แล้วแสดงคำสั่งเดิมให้แก้
  พูดอย่างอื่นจะถามซ้ำ ไม่เดา
- ประวัติแชทส่งให้ AI เฉพาะช่วงที่ AI ถามกลับ (ตอบคำถามต่อได้) และล้างทุกครั้ง
  ที่จบรอบที่มีการเรียกเครื่องมือ
"""
import ai_client
import config
import tools
import reminders_tool

EXIT_WORDS = ('q', 'quit', 'exit', 'ออก')

_NEGATIVE = ('ไม่', 'ยกเลิก', 'หยุด')
_POSITIVE = ('ใช่', 'ตกลง', 'บันทึก', 'ยืนยัน', 'โอเค', 'เอาเลย')


def classify_answer(text):
    """แปลคำตอบยืนยันเป็น 'yes' / 'no' / 'redo' หรือ None ถ้าไม่เข้าใจ

    ถ้ามีคำปฏิเสธปนอยู่ ถือเป็น 'no' เสมอ (ปลอดภัยไว้ก่อน ไม่บันทึกผิดพลาด)
    """
    t = (text or '').strip().lower().replace(' ', '')
    if not t:
        return None
    if 'ทำใหม่' in t or 'แก้คำสั่ง' in t:
        return 'redo'
    if t in ('n', 'no') or any(w in t for w in _NEGATIVE):
        return 'no'
    if t in ('y', 'yes', 'ok') or any(w in t for w in _POSITIVE):
        return 'yes'
    return None


def ask_confirm():
    while True:
        decision = classify_answer(
            input('บันทึกไหม (ใช่ / ไม่ / ทำใหม่): '))
        if decision:
            return decision
        print('ไม่เข้าใจคำตอบ ตอบว่า "ใช่" "ไม่" หรือ "ทำใหม่"')


def handle_tool_calls(user_text, tool_calls):
    for call in tool_calls:
        if call['name'] != 'create_reminder':
            print('(AI เรียกเครื่องมือที่ไม่รู้จัก: %s ข้ามไป)' % call['name'])
            continue
        try:
            validated = tools.validate_create_reminder(call['arguments'])
        except tools.ToolValidationError as e:
            print('ตรวจค่าไม่ผ่าน:', e)
            continue

        print(tools.format_confirm_text(validated))
        decision = ask_confirm()
        if decision == 'yes':
            try:
                reminders_tool.create_reminder(
                    title=validated['title'],
                    due_date=validated['due_date'],
                    notes=validated['notes'],
                )
            except Exception as e:
                print('บันทึกไม่สำเร็จ:', e)
                continue
            print('บันทึกเรียบร้อย เช็กในแอป Reminders ได้เลย')
        elif decision == 'redo':
            print('ยกเลิก ไม่บันทึก คำสั่งเดิมคือ: %s' % user_text)
            print('(แก้แล้วพิมพ์ส่งใหม่ได้เลย)')
        else:
            print('ยกเลิก ไม่บันทึก')


def main():
    history = []
    while True:
        user_text = input(
            '\nพิมพ์คำสั่ง (พิมพ์ q หรือ "ออก" เพื่อจบ): ').strip()
        if not user_text:
            print('(ช่องว่าง ยังไม่ส่ง)')
            continue
        if user_text.lower() in EXIT_WORDS:
            print('จบการทดสอบ')
            break

        token = ai_client.CancelToken()

        def on_chunk(piece):
            print(piece, end='', flush=True)

        try:
            text, tool_calls = ai_client.stream_chat_with_tools(
                user_text, on_chunk, token, tools.ALL_TOOLS, history=history)
        except ai_client.AIError as e:
            print('\nเกิดข้อผิดพลาด:', e)
            continue

        print()
        if not tool_calls:
            print('(AI ตอบเป็นข้อความ ยังไม่ได้สร้างการเตือนใด ๆ '
                  'ถ้า AI ถามกลับ ตอบต่อได้เลย)')
            if text.strip():
                history.append({'role': 'user', 'content': user_text})
                history.append({'role': 'assistant', 'content': text})
                history = history[-2 * config.MEMORY_PAIRS:]
            continue

        handle_tool_calls(user_text, tool_calls)
        history = []


if __name__ == '__main__':
    main()