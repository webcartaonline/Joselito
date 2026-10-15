from dotenv import dotenv_values, load_dotenv
import os

# load_dotenv() no sobrescribe variables que ya existen en el entorno.
# Por eso comparamos el .env con lo que ve el proceso.
env_before = {key: os.environ.get(key) for key in ('DEEPSEEK_API_KEY', 'DEEPSEEK_MODEL', 'DEEPSEEK_SUMMARIZER_MODEL')}
load_dotenv()

# Mostrar configuración sin revelar la key completa
api_key = os.getenv('DEEPSEEK_API_KEY', 'NO CONFIGURADO')
model = os.getenv('DEEPSEEK_MODEL', 'NO CONFIGURADO')
summary_model = os.getenv('DEEPSEEK_SUMMARIZER_MODEL', 'NO CONFIGURADO')

print("=== CONFIGURACIÓN ACTUAL ===")
print(f"DEEPSEEK_API_KEY: {'CONFIGURADO (primeros 6 caracteres): ' + api_key[:6] + '...' if api_key != 'NO CONFIGURADO' else 'NO CONFIGURADO'}")
print(f"DEEPSEEK_MODEL: {model} (por defecto: deepseek-chat)")
print(f"DEEPSEEK_SUMMARIZER_MODEL: {summary_model} (por defecto: DEEPSEEK_MODEL)")
print()

if api_key == 'NO CONFIGURADO':
    print("[INFO] No tienes DEEPSEEK_API_KEY configurado")
    print("   -> La IA no funcionara; el programa exporta sin enriquecer.")
    print("   -> Valida tu key con 'python prueba_deepseek.py'.")
else:
    print("[OK] Key de DeepSeek configurada.")
    print("   -> Valida tu key con 'python prueba_deepseek.py'.")

print()
print("=== ORIGEN DE LA CONFIGURACION ===")
try:
    file_values = dotenv_values('.env')
except OSError:
    file_values = {}
for key in ('DEEPSEEK_API_KEY', 'DEEPSEEK_MODEL', 'DEEPSEEK_SUMMARIZER_MODEL'):
    in_env = env_before.get(key)
    in_file = file_values.get(key)
    if in_env and in_file and in_env != in_file:
        print(f"[AVISO] {key} viene del entorno y el .env se ignora para esa variable.")
    elif in_env and not in_file:
        print(f"[INFO] {key} viene del entorno (no esta en el .env).")
    elif in_file and not in_env:
        print(f"[OK] {key} se lee del .env.")
    elif not in_env and not in_file:
        print(f"[INFO] {key} no esta ni en el entorno ni en el .env.")
    else:
        print(f"[OK] {key}: entorno y .env coinciden.")

print()
print("=== PAQUETE USADO ===")
try:
    import wiki_enrichment
    print(f"wiki_enrichment se importa desde: {wiki_enrichment.__file__}")
    print("   -> Si no apunta a tu repo (src/), usas otro venv o un 'pip install .' no editable,")
    print("      y el .env puede no encontrarse. Compruebalo con otro interprete si hace falta.")
except ImportError as error:
    print(f"No se pudo importar wiki_enrichment: {error}")
