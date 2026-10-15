"""Quick validation for the DeepSeek API key without running Joselito."""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
model = os.getenv("DEEPSEEK_MODEL") or "deepseek-chat"
base_url = os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1"

print(f"DeepSeek key: {'CONFIGURADO [OK]' if api_key else 'NO CONFIGURADO [X]'}")
print(f"Modelo: {model}")
print(f"Base URL: {base_url}")
print()

if not api_key:
    print("ERROR: No tienes DEEPSEEK_API_KEY en tu .env")
    print("Solucion: agrega DEEPSEEK_API_KEY=sk-... en tu archivo .env")
    raise SystemExit(1)

try:
    response = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": "Hola"}],
            "max_tokens": 50,
        },
        timeout=60,
    )
    response.raise_for_status()
    print("[OK] EXITOSA:", response.json()["choices"][0]["message"]["content"])
except Exception as error:
    print("[X] ERROR:", type(error).__name__, "-", error)
    print()
    print("Posibles causas:")
    print("1. La key no es valida o no tiene saldo (401/402).")
    print("2. El modelo no existe en la API (usa deepseek-chat o deepseek-reasoner).")
