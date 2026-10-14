from dotenv import load_dotenv
import os

load_dotenv()

# Mostrar configuración sin revelar el token completo
token = os.getenv('HF_TOKEN', 'NO CONFIGURADO')
model = os.getenv('HF_MODEL', 'NO CONFIGURADO')

print("=== CONFIGURACIÓN ACTUAL ===")
print(f"HF_TOKEN: {'CONFIGURADO (primeros 10 caracteres): ' + token[:10] + '...' if token != 'NO CONFIGURADO' else 'NO CONFIGURADO'}")
print(f"HF_MODEL: {model}")
print()

# Verificar el modelo configurado frente al valor por defecto del código.
# El valor por defecto está en src/wiki_enrichment/bootstrap.py (DEFAULT_HF_MODEL)
# y es el que usa el router de Hugging Face: un 402 significa que el modelo
# es aceptado pero la cuenta no tiene créditos; "model_not_supported"
# significa que el modelo no es válido en el router.
DEFAULT_MODEL = 'openai/gpt-oss-120b'
if model == DEFAULT_MODEL:
    print(f"[OK] Modelo por defecto del proyecto: {model}")
    print("   -> Si Hugging Face responde 402, el modelo es aceptado pero no hay creditos.")
elif model == 'NO CONFIGURADO':
    print("[INFO] No tienes HF_MODEL configurado")
    print(f"   -> El codigo usara '{DEFAULT_MODEL}' por defecto.")
else:
    print(f"[OK] Modelo configurado: {model}")
    print("   -> Validalo con 'python prueba_hf.py': si responde 'model_not_supported',")
    print("     ese modelo no es valido en el router.")
