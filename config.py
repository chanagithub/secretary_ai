"""config.py - ค่าตั้งต้นและการตั้งค่าของ AI เลขาส่วนตัว

เก็บ: โมเดลเริ่มต้น, รายการโมเดลที่เคยใช้, โมเดลที่เลือกอยู่ (ไฟล์ settings.json
วางข้างไฟล์นี้) และตัวช่วยเข้าถึง API key ผ่าน keychain (ไม่ฝัง key ในโค้ด)
"""
import json
import os
import re

DEFAULT_MODEL = 'deepseek/deepseek-chat-v3-0324'

KEYCHAIN_SERVICE = 'openrouter'  # ตรงกับ setup_key.py
KEYCHAIN_ACCOUNT = 'api_key'

_SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'settings.json')

# รูปแบบชื่อโมเดลของ OpenRouter: ผู้ให้บริการ/ชื่อโมเดล (ไม่มีช่องว่าง)
_MODEL_ID_PATTERN = re.compile(r'^\S+/\S+$')


def _load():
    try:
        with open(_SETTINGS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}

    models = []
    for m in data.get('models', []):
        if isinstance(m, str) and m.strip() and m.strip() not in models:
            models.append(m.strip())
    if DEFAULT_MODEL not in models:
        models.insert(0, DEFAULT_MODEL)

    current = data.get('current_model')
    if current not in models:
        current = DEFAULT_MODEL
    return models, current


def _save(models, current):
    data = {'models': models, 'current_model': current}
    tmp_path = _SETTINGS_PATH + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, _SETTINGS_PATH)


def get_models():
    """รายการโมเดลที่เคยใช้ (โมเดลเริ่มต้นอยู่ในรายการเสมอ)"""
    return _load()[0]


def get_current_model():
    return _load()[1]


def set_current_model(model):
    """เลือกโมเดลจากรายการที่มีอยู่ คืน True ถ้าสำเร็จ"""
    models, _ = _load()
    if model not in models:
        return False
    _save(models, model)
    return True


def add_model(text):
    """เพิ่มโมเดลใหม่เข้ารายการและเลือกใช้ทันที

    คืน (True, ชื่อโมเดล) หรือ (False, ข้อความอธิบายปัญหา)
    ถ้าชื่อมีอยู่ในรายการแล้ว จะเลือกอันนั้นแทน
    """
    model = (text or '').strip()
    if not _MODEL_ID_PATTERN.match(model):
        return False, 'ต้องเป็นรูปแบบ ผู้ให้บริการ/ชื่อโมเดล เช่น openai/gpt-4o'
    models, _ = _load()
    if model not in models:
        models.append(model)
    _save(models, model)
    return True, model


# ---------- ประวัติคำสั่งที่เคยส่ง (ล่าสุดอยู่บนสุด) ----------
MAX_HISTORY = 50
_HISTORY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'history.json')


def get_history():
    try:
        with open(_HISTORY_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [t for t in data if isinstance(t, str) and t.strip()]


def _save_history(items):
    tmp_path = _HISTORY_PATH + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, _HISTORY_PATH)


def add_history(text):
    """บันทึกคำสั่งที่ส่ง ถ้าซ้ำของเดิมจะย้ายขึ้นบนสุด เก็บล่าสุด MAX_HISTORY รายการ"""
    text = (text or '').strip()
    if not text:
        return
    items = [t for t in get_history() if t != text]
    items.insert(0, text)
    _save_history(items[:MAX_HISTORY])


def remove_history(text):
    _save_history([t for t in get_history() if t != text])


def clear_history():
    _save_history([])


def get_api_key():
    try:
        import keychain
    except ImportError:  # ไม่ได้รันใน Pythonista
        return None
    return keychain.get_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)


def set_api_key(key):
    import keychain
    keychain.set_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT, key.strip())