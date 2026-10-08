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


def _system_prompt():
    now = datetime.datetime.now()
    return (
        'คุณคือเลขาส่วนตัวของผู้ใช้ ตอบเป็นภาษาไทย กระชับ ตรงประเด็น\n'
        'ขณะนี้คือ %s ที่ %s เวลา %s น. (ปี ค.ศ.)\n'
        'ตอนนี้ยังไม่มีเครื่องมือสร้างการเตือนหรือบันทึกรายการใด ๆ '
        'ถ้าผู้ใช้สั่งให้ทำสิ่งเหล่านี้ ให้บอกตรง ๆ ว่ายังทำไม่ได้ '
        'ห้ามบอกว่าทำให้แล้ว'
        % (_WEEKDAYS_TH[now.weekday()], now.strftime('%Y-%m-%d'),
           now.strftime('%H:%M')))


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