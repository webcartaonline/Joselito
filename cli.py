import pyfiglet

wiki_content = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."

LINE = "========================================================="
LINE_ERROR = "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"

def ask_text(question):
    """Pregunta algo y no acepta respuestas vacías."""
    while True:
        answer = input(question).strip()
        if answer:
            return answer
        print()
        print(LINE_ERROR)
        print("No has escrito nada. Inténtalo de nuevo.")
        print(LINE_ERROR)
        print()


def ask_option(question, options):
    """Pregunta algo y solo acepta las letras de 'options' (da igual mayúscula o minúscula)."""
    valid = " o ".join(options)
    while True:
        answer = input(question).strip().upper()
        if answer == "":
            print()
            print(LINE_ERROR)
            print(f"No has escrito nada. Escribe {valid}.")
            print(LINE_ERROR)
            print()
        elif answer not in options:
            print()
            print(LINE_ERROR)
            print(f"'{answer}' no es una opción válida. Escribe {valid}.")
            print(LINE_ERROR)
            print()
        else:
            return answer


print()
print(pyfiglet.figlet_format("Hola, soy", font="larry3d"))
print(pyfiglet.figlet_format("Joselito", font="larry3d"))

print(LINE)
topic = ask_text("¿Qué tema quieres investigar? ")
print(LINE)
language = ask_text("¿A qué idioma quieres traducirlo? ")
print(LINE)

print()

print(f"# Buscando '{topic}' y traduciendo a {language}...")

print()

print(LINE)
print(f"# Esto es lo que he encontrado en referencia a {topic}:")
print()

print(wiki_content)
print()

print(LINE)
print("¿Quieres exportar la investigación?")
export = ask_option("Y/N: ", ["Y", "N"])
print(LINE)

if export == "Y":
    formats = {"P": "PDF", "T": "TXT"}
    print("¿Prefieres exportarlo en PDF o TXT?")
    export_format = formats[ask_option("PDF (P) / TXT (T): ", formats)]
    print(LINE)

    print()
    print(f"# Exportando investigación en formato {export_format}...")
    print()

print(LINE)
print("Mi trabajo aquí ha terminado, nos vemos cuando quieras.")
print(LINE)

print()
print(pyfiglet.figlet_format("Ha sido un placer", font="larry3d"))