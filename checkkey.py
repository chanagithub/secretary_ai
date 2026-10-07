import keychain
k = keychain.get_password("openrouter", "api_key")
print("มี key" if k else "ไม่พบ key", len(k) if k else 0)