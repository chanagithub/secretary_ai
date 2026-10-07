import console
import keychain

key = console.password_alert("OpenRouter API key", "วาง key ที่นี่")
keychain.set_password("openrouter", "api_key", key)
print("บันทึกแล้ว")