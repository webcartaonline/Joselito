import pyfiglet

print()
print(pyfiglet.figlet_format("Hola, soy", font="larry3d"))
print(pyfiglet.figlet_format("Joselito", font="larry3d"))

print("=========================================================")
tema = input("¿Qué tema quieres investigar? ")
print("=========================================================")
idioma = input("¿A qué idioma quieres traducirlo? ")
print("=========================================================")

print()
print(f"Buscando '{tema}' y traduciendo a {idioma}...")
print()