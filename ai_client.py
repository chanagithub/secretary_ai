"""ai_client.py - คุยกับ OpenRouter (เฟส 0)

รับคำตอบแบบ streaming เพื่อให้กดหยุดได้จริง: เมื่อ cancel() จะปิดการเชื่อมต่อ
ทันที AI จึงหยุดสร้างคำตอบต่อ (ยังไม่มี tool calling - จะเพิ่มในเฟส 1)
"""
import datetime
import json
import threading

import requests

import config

API_URL = 'https://openrouter.ai/api/v1/chat/completions'

_WEEKDAYS_TH = ['วันจันทร์', 'วันอังคาร', 'วันพุธ', 'วันพฤหัสบดี',
                'วันศุกร์', 'วันเสาร์', 'วันอาทิตย์']


class AIError(Exception):
    """ข้อผิดพลาดที่มีข้อความภาษาไทยพร้อมแสดงให้ผู้ใช้อ่าน"""


def _close_quietly(response):
    try:
        response.close()
    except Exception:
        pass


class CancelToken:
    """ใช้สั่งหยุดงานที่กำลังรอ AI อยู่ (เรียก cancel() จาก thread ไหนก็ได้)"""

    def __init__(self):
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._response = None

    @property
    def cancelled(self):
        return self._event.is_set()

    def attach(self, response):
        with self._lock:
            self._response = response
            already = self._event.is_set()
        if already:
            _close_quietly(response)

    def cancel(self):
        with self._lock:
            self._event.set()
            response = self._response
        if response is not None:
            # ปิดใน thread แยก กันหน้าจอค้างถ้าการปิดใช้เวลา
            threading.Thread(target=_close_quietly, args=(response,),
                             daemon=True).start()


def _calendar_lines(now, days=14):
    """ตารางวัน 'days' วันข้างหน้า (ชื่อวันไทย + วันที่จริง) ให้โค้ดคำนวณแทน AI"""
    labels = {0: 'วันนี้', 1: 'พรุ่งนี้', 2: 'มะรืนนี้'}
    lines = []
    for i in range(days):
        d = now.date() + datetime.timedelta(days=i)
        prefix = labels[i] + ' = ' if i in labels else ''
        lines.append('- %s%s %s' % (prefix, _WEEKDAYS_TH[d.weekday()],
                                    d.strftime('%Y-%m-%d')))
    return '\n'.join(lines)


def _system_prompt(tools_enabled=False):
    now = datetime.datetime.now()
    header = (
        'คุณคือเลขาส่วนตัวของผู้ใช้ ตอบเป็นภาษาไทย กระชับ ตรงประเด็น\n'
        'ขณะนี้คือ %s ที่ %s เวลา %s น. (ปี ค.ศ.)\n'
        'ปฏิทิน 14 วันข้างหน้า (ใช้ตารางนี้แปลงชื่อวันเป็นวันที่จริง ห้ามคำนวณเอง):\n'
        '%s\n'
        % (_WEEKDAYS_TH[now.weekday()], now.strftime('%Y-%m-%d'),
           now.strftime('%H:%M'), _calendar_lines(now))
    )
    if tools_enabled:
        return header + (
            'คุณมีเครื่องมือ create_reminder, list_reminders, reschedule_reminder, '
            'complete_reminder และ delete_reminder สำหรับจัดการรายการจริงใน Reminders '
            'กติกา:\n'
            '1. ถ้ารู้เรื่องที่ต้องทำและวัน ให้เรียก create_reminder ทันที '
            '(ใส่เวลาเฉพาะเมื่อผู้ใช้บอกเวลา ถ้าผู้ใช้ไม่ได้บอกเวลา ให้ใส่เฉพาะวัน YYYY-MM-DD '
            'ห้ามเดาเวลา และห้ามถามเรื่องเวลา เพราะระบบจะถามผู้ใช้เอง) '
            'ห้ามพิมพ์สรุปเป็นข้อความแทนการเรียกเครื่องมือ\n'
            '2. ถ้าไม่รู้เรื่องที่ต้องทำหรือไม่รู้วัน ให้ถามกลับสั้น ๆ หนึ่งคำถาม ห้ามเดา\n'
            '3. ถ้าผู้ใช้พูดชื่อวันที่ตรงกับวันนี้ ให้ถามก่อนว่าหมายถึงวันนี้หรือสัปดาห์หน้า '
            'เว้นแต่ผู้ใช้พูดชัดว่า "วันนี้" หรือ "สัปดาห์หน้า" '
            'หรือมีวงเล็บ "(หมายถึง ... วันที่ YYYY-MM-DD)" ต่อท้าย ให้ใช้วันที่ในวงเล็บนั้นทันที\n'
            '4. สำหรับวันที่ไม่ใช่วันนี้ "...ที่จะถึง" หรือ "...นี้" หมายถึงวันนั้นที่ใกล้ที่สุดในอนาคตตามตาราง '
            'ส่วนชื่อวันที่ตรงกับวันนี้ให้ใช้ข้อ 3 เท่านั้น และ "สัปดาห์หน้า" คือวันเดียวกันของสัปดาห์ถัดไป\n'
            '5. เวลาแบบไทย: บ่ายโมง = 13:00, บ่ายสอง (โมง) = 14:00, บ่าย 3 โมง = 15:00, '
            'บ่ายสี่โมง = 16:00, 5 โมงเย็น = 17:00, 1 ทุ่ม = 19:00, ตี 1 = 01:00, เที่ยง = 12:00 '
            '(บ่าย N โมง = 12+N) และเวลาแบบ "13.00 น." หรือ "13:00" = 13:00\n'
            '6. ห้ามบอกว่าสร้างให้แล้ว จนกว่าระบบจะยืนยันว่าสร้างสำเร็จ '
            '(ผู้ใช้จะเห็นหน้ายืนยันก่อนบันทึกเสมอ)\n'
            '7. เมื่อรู้วัน (และเวลาถ้าผู้ใช้บอก) ให้เรียก create_reminder เสมอ แม้วันนั้นอาจเป็นอดีต '
            'ห้ามพิมพ์ข้อความแจ้งข้อผิดพลาดเอง เพราะระบบตรวจค่าและแจ้งผู้ใช้เอง '
            'ปีไทย (พ.ศ.) ให้ลบ 543 เป็น ค.ศ. เช่น 2569 = 2026\n'
            '8. ถ้าผู้ใช้ถามรายการของวันใด ให้เรียก list_reminders ด้วย date เป็น YYYY-MM-DD; '
            'ถ้าถามทั้งเดือนให้ส่ง month เป็น YYYY-MM และ status ตามที่ขอ\n'
            '9. ถ้าในประวัติแชทระบบเพิ่งขอให้ผู้ใช้บอกเวลาของงานหนึ่ง และผู้ใช้ตอบเวลามา '
            'ให้เรียก create_reminder ทันทีด้วยชื่อเรื่องและวันเดิมจากประวัติ พร้อมเวลาที่ผู้ใช้ตอบ\n'
            '10. เมื่อผู้ใช้ขอดูงาน ให้เรียก list_reminders ก่อนเสมอ ห้ามแต่งรายการจากความจำ\n'
            '11. หลังระบบแสดงรายการเป็นหมายเลขแล้ว หากผู้ใช้สั่งเลื่อน/เสร็จหรือยกเลิก/ลบ '
            'ให้เรียกเครื่องมือที่ตรงกันโดยอ้าง number จากรายการล่าสุดเท่านั้น ห้ามเดาหมายเลข\n'
            '12. การเลื่อนนัด: ส่ง new_time รูปแบบ HH:MM เมื่อผู้ใช้ระบุเวลา และส่ง new_date เฉพาะเมื่อเปลี่ยนวัน '
            'ถ้าไม่ชัดว่าหมายถึงรายการใด ให้ถามกลับก่อนเรียกเครื่องมือ\n'
            '13. ใช้ complete_reminder สำหรับเสร็จหรือยกเลิก (กู้คืนได้) และ delete_reminder '
            'เฉพาะเมื่อผู้ใช้ขอลบทิ้งถาวร ระบบจะแสดงหน้าต่างยืนยันก่อนทำจริง\n'
            '14. ถ้าผู้ใช้ขอรายการที่เสร็จแล้ว ให้ใช้ status=completed. '
            'รายการค้างใช้ status=incomplete. ถ้าขอทั้งหมด ใช้ status=all. '
            'ห้ามตอบเป็นอังกฤษและห้ามพิมพ์รายชื่อเองเมื่อเรียกเครื่องมือแล้ว'
        )
    return header + (
        'ตอนนี้ยังไม่มีเครื่องมือสร้างการเตือนหรือบันทึกรายการใด ๆ '
        'ถ้าผู้ใช้สั่งให้ทำสิ่งเหล่านี้ ให้บอกตรง ๆ ว่ายังทำไม่ได้ '
        'ห้ามบอกว่าทำให้แล้ว'
    )


def _http_error_message(response):
    status = response.status_code
    detail = ''
    try:
        err = response.json().get('error', {})
        detail = err.get('message', '') if isinstance(err, dict) else str(err)
    except Exception:
        pass

    if status == 401:
        msg = 'API key ไม่ถูกต้องหรือถูกยกเลิก ตรวจ key ใน keychain อีกครั้ง'
    elif status == 402:
        msg = 'เครดิต OpenRouter ไม่พอ'
    elif status in (400, 404):
        msg = 'ชื่อโมเดลอาจไม่ถูกต้อง หรือโมเดลนี้ใช้ไม่ได้ตอนนี้ ลองเลือกโมเดลอื่น'
    elif status == 429:
        msg = 'เรียกถี่เกินโควต้า รอสักครู่แล้วลองใหม่'
    else:
        msg = 'OpenRouter ตอบกลับผิดปกติ (HTTP %d)' % status
    if detail:
        msg += '\n(%s)' % detail
    return msg


def stream_chat(user_text, on_chunk, token, model=None, history=None):
    """ส่งข้อความหนึ่งข้อความให้ AI แล้วรับคำตอบเป็นช่วง ๆ

    on_chunk(text) ถูกเรียกทุกครั้งที่ได้ข้อความใหม่ (เรียกจาก thread ที่เรียกฟังก์ชันนี้)
    คืนข้อความทั้งหมดที่ได้รับ ถ้าถูก cancel จะคืนเท่าที่ได้ก่อนหยุด
    history = รายการ {'role': 'user'|'assistant', 'content': ...} ที่ให้ AI จำ (เรียงเก่าไปใหม่)
    ถ้ามีปัญหาจะ raise AIError
    """
    key = config.get_api_key()
    if not key:
        raise AIError('ไม่พบ API key ใน keychain (รัน setup_key.py ก่อน)')
    model = model or config.get_current_model()

    payload = {
        'model': model,
        'stream': True,
        'messages': (
            [{'role': 'system', 'content': _system_prompt()}]
            + list(history or [])
            + [{'role': 'user', 'content': user_text}]
        ),
    }
    headers = {
        'Authorization': 'Bearer ' + key,
        'Content-Type': 'application/json',
    }

    try:
        resp = requests.post(API_URL, headers=headers, json=payload,
                             stream=True, timeout=(10, 60))
    except requests.exceptions.Timeout:
        raise AIError('เชื่อมต่อ OpenRouter ไม่ทัน ลองใหม่อีกครั้ง')
    except requests.exceptions.RequestException:
        raise AIError('เน็ตมีปัญหา เชื่อมต่อ OpenRouter ไม่ได้')

    token.attach(resp)
    if token.cancelled:
        return ''

    if resp.status_code != 200:
        try:
            raise AIError(_http_error_message(resp))
        finally:
            _close_quietly(resp)

    parts = []
    try:
        # chunk_size เล็ก เพื่อให้ข้อความแสดงทันและกดหยุดได้เร็ว (ค่าเริ่มต้น 512 จะรอสะสมก่อน)
        for raw in resp.iter_lines(chunk_size=16):
            if token.cancelled:
                break
            if not raw:
                continue
            line = raw.decode('utf-8', errors='replace').strip()
            if not line.startswith('data:'):  # รวมบรรทัด keep-alive ที่ขึ้นต้นด้วย ':'
                continue
            data = line[5:].strip()
            if data == '[DONE]':
                break
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            if obj.get('error'):
                err = obj['error']
                text = err.get('message', '') if isinstance(err, dict) else str(err)
                raise AIError('AI ตอบกลับผิดพลาดระหว่างทาง: %s' % text)
            choices = obj.get('choices') or []
            if not choices:
                continue
            piece = (choices[0].get('delta') or {}).get('content')
            if piece:
                parts.append(piece)
                on_chunk(piece)
    except AIError:
        raise
    except Exception:
        # ตอนกดหยุดเราปิดการเชื่อมต่อเอง อาจเกิด error ปลายทาง ถือว่าปกติ
        if not token.cancelled:
            raise AIError('การเชื่อมต่อขาดระหว่างรับคำตอบ ลองใหม่อีกครั้ง')
    finally:
        _close_quietly(resp)
    return ''.join(parts)


def stream_chat_with_tools(user_text, on_chunk, token, tools, model=None, history=None):
    """เหมือน stream_chat แต่เปิดให้ AI เรียกเครื่องมือ (tool calling) ได้

    tools: list ของ tool schema (เช่น tools.ALL_TOOLS จาก tools.py)
    คืนค่า: (text, tool_calls)
      text = ข้อความที่ AI พิมพ์ตอบปกติ (อาจว่างถ้า AI เลือกเรียกเครื่องมือล้วน ๆ)
      tool_calls = list ของ dict {'id':.., 'name':.., 'arguments': dict}
    ถ้ามีปัญหาจะ raise AIError เหมือน stream_chat
    """
    key = config.get_api_key()
    if not key:
        raise AIError('ไม่พบ API key ใน keychain (รัน setup_key.py ก่อน)')
    model = model or config.get_current_model()

    payload = {
        'model': model,
        'stream': True,
        'tools': tools,
        'tool_choice': 'auto',
        'messages': (
            [{'role': 'system', 'content': _system_prompt(tools_enabled=True)}]
            + list(history or [])
            + [{'role': 'user', 'content': user_text}]
        ),
    }
    headers = {
        'Authorization': 'Bearer ' + key,
        'Content-Type': 'application/json',
    }

    try:
        resp = requests.post(API_URL, headers=headers, json=payload,
                             stream=True, timeout=(10, 60))
    except requests.exceptions.Timeout:
        raise AIError('เชื่อมต่อ OpenRouter ไม่ทัน ลองใหม่อีกครั้ง')
    except requests.exceptions.RequestException:
        raise AIError('เน็ตมีปัญหา เชื่อมต่อ OpenRouter ไม่ได้')

    token.attach(resp)
    if token.cancelled:
        return '', []

    if resp.status_code != 200:
        try:
            raise AIError(_http_error_message(resp))
        finally:
            _close_quietly(resp)

    parts = []
    tool_acc = {}  # index -> {'id':.., 'name':.., 'arguments': str สะสม}
    try:
        for raw in resp.iter_lines(chunk_size=16):
            if token.cancelled:
                break
            if not raw:
                continue
            line = raw.decode('utf-8', errors='replace').strip()
            if not line.startswith('data:'):
                continue
            data = line[5:].strip()
            if data == '[DONE]':
                break
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            if obj.get('error'):
                err = obj['error']
                text = err.get('message', '') if isinstance(err, dict) else str(err)
                raise AIError('AI ตอบกลับผิดพลาดระหว่างทาง: %s' % text)
            choices = obj.get('choices') or []
            if not choices:
                continue
            delta = choices[0].get('delta') or {}
            piece = delta.get('content')
            if piece:
                parts.append(piece)
                on_chunk(piece)
            for tc in (delta.get('tool_calls') or []):
                idx = tc.get('index', 0)
                slot = tool_acc.setdefault(idx, {'id': None, 'name': None, 'arguments': ''})
                if tc.get('id'):
                    slot['id'] = tc['id']
                fn = tc.get('function') or {}
                if fn.get('name'):
                    slot['name'] = fn['name']
                if fn.get('arguments'):
                    slot['arguments'] += fn['arguments']
    except AIError:
        raise
    except Exception:
        if not token.cancelled:
            raise AIError('การเชื่อมต่อขาดระหว่างรับคำตอบ ลองใหม่อีกครั้ง')
    finally:
        _close_quietly(resp)

    tool_calls = []
    for idx in sorted(tool_acc.keys()):
        slot = tool_acc[idx]
        if not slot['name']:
            continue
        try:
            args = json.loads(slot['arguments']) if slot['arguments'] else {}
        except ValueError:
            args = {}
        # บาง provider เติม namespace เช่น default_api. ให้เก็บเฉพาะชื่อท้าย
        # เพื่อให้ตรงกับ schema ที่แอปลงทะเบียนไว้
        normalized_name = slot['name'].rsplit('.', 1)[-1]
        tool_calls.append({'id': slot['id'], 'name': normalized_name, 'arguments': args})

    return ''.join(parts), tool_calls
