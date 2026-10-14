from dotenv import dotenv_values, load_dotenv
import os

# load_dotenv() no sobrescribe variables que ya existen en el entorno.
# Por eso comparamos el .env con lo que ve el proceso.
env_before = {'HF_TOKEN': os.environ.get('HF_TOKEN'), 'HF_MODEL': os.getenv('HF_MODEL')}
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

print()
print("=== ORIGEN DE LA CONFIGURACION ===")
try:
    file_values = dotenv_values('.env')
except OSError:
    file_values = {}
for key in ('HF_TOKEN', 'HF_MODEL'):
    in_env = env_before.get(key)
    in_file = file_values.get(key)
    if in_env and in_file and in_env != in_file:
        print(f"[AVISO] {key} viene del entorno y el .env se ignora para esa variable.")
        print(f"   -> Entorno: {repr(in_env[:8] + '...') if key == 'HF_TOKEN' else repr(in_env)}")
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
