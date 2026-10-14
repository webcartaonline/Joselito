from huggingface_hub import InferenceClient
from dotenv import load_dotenv
import os

load_dotenv()

# Diagnosticar configuración
token = os.getenv('HF_TOKEN')
model_env = os.getenv('HF_MODEL')
print(f"Token HF_TOKEN: {'CONFIGURADO ✓' if token else 'NO CONFIGURADO ✗'}")
print(f"Modelo HF_MODEL: {model_env or 'NO CONFIGURADO (usa openai/gpt-oss-120b por defecto)'}")
print()

if not token:
    print("ERROR: No tienes HF_TOKEN en tu .env")
    print("Solución: agrega HF_TOKEN=tu_token_hf_... en tu archivo .env")
    exit(1)

# Probar con el mismo modelo por defecto que usa el código
# (src/wiki_enrichment/bootstrap.py: DEFAULT_HF_MODEL).
model_to_test = model_env or 'openai/gpt-oss-120b'
print(f"Probando con modelo: {model_to_test}")

client = InferenceClient(api_key=token)
try:
    r = client.chat_completion(
        messages=[{'role': 'user', 'content': 'Hola'}],
        model=model_to_test,
        max_tokens=50
    )
    print('✅ EXITOSA:', r.choices[0].message.content)
except Exception as e:
    print('❌ ERROR:', type(e).__name__, '-', e)
    print()
    print("Posibles causas:")
    print("1. El modelo no existe o no soporta chat_completion")
    print("2. No tienes créditos suficientes en Hugging Face")
    print("3. El modelo requiere aceptar licencia (ej: Llama-3.1)")
