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

# Verificar si el modelo es un nombre falso
if model == 'openai/gpt-oss-120b':
    print("❌ ALERTA: 'openai/gpt-oss-120b' NO ES UN MODELO REAL DE HUGGING FACE")
    print("   → Solución: cambia a un modelo real como: Qwen/Qwen2.5-72B-Instruct")
elif model == 'NO CONFIGURADO':
    print("❌ ALERTA: No tienes HF_MODEL configurado")
    print("   → El código usará 'openai/gpt-oss-120b' por defecto, que no existe")
    print("   → Solución: agrega HF_MODEL=Qwen/Qwen2.5-72B-Instruct en tu .env")
else:
    print(f"✅ Modelo configurado: {model}")
