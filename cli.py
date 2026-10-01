import time
from typing import Optional

import pyfiglet
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

console = Console()
app = typer.Typer()

wiki_content = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."


def show_banner(text):
    """Muestra un texto grande y en color."""
    console.print(pyfiglet.figlet_format(text, font="larry3d"), style="bold cyan")


def show_error(message):
    """Muestra un error en rojo dentro de un recuadro."""
    console.print(Panel(message, border_style="red", title="Error"))


def ask_text(question):
    """Pregunta algo y no acepta respuestas vacías."""
    while True:
        answer = Prompt.ask(f"[bold]{question}[/]").strip()
        if answer:
            return answer
        show_error("No has escrito nada. Inténtalo de nuevo.")


def ask_option(question, options):
    """Pregunta algo y solo acepta las letras de 'options' (da igual mayúscula o minúscula)."""
    valid = " o ".join(options)
    while True:
        answer = Prompt.ask(f"[bold]{question}[/]").strip().upper()
        if answer == "":
            show_error(f"No has escrito nada. Escribe {valid}.")
        elif answer not in options:
            show_error(f"'{answer}' no es una opción válida. Escribe {valid}.")
        else:
            return answer


def run_steps(steps):
    """Muestra una barra de progreso que avanza un paso cada vez."""
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Empezando...", total=len(steps))
        for step in steps:
            progress.update(task, description=step)
            time.sleep(1)  # Aquí irá la llamada real (Wikipedia, IA, traducción...)
            progress.advance(task)


def show_summary(topic, language, export_format):
    """Muestra un resumen final en forma de tabla."""
    table = Table(title="Resumen")
    table.add_column("Dato", style="cyan")
    table.add_column("Valor", style="green")
    table.add_row("Tema", topic)
    table.add_row("Idioma", language)
    table.add_row("Exportado", export_format)
    console.print(table)


@app.command()
def main(
    tema: Optional[str] = typer.Option(None, help="Tema a investigar"),
    idioma: Optional[str] = typer.Option(None, help="Idioma de la traducción"),
):
    """Joselito: investiga un tema en Wikipedia, lo enriquece y lo traduce."""
    show_banner("Hola, soy")
    show_banner("Joselito")

    # Si no lo pasaron al arrancar, lo preguntamos
    topic = tema or ask_text("¿Qué tema quieres investigar?")
    language = idioma or ask_text("¿A qué idioma quieres traducirlo?")

    run_steps([
        f"Buscando '{topic}' en Wikipedia...",
        "Enriqueciendo con IA...",
        f"Traduciendo a {language}...",
    ])

    console.print(Panel(wiki_content, title=f"Resultados sobre {topic}", border_style="green"))

    export_format = "No"
    if ask_option("¿Quieres exportar la investigación? (Y/N)", ["Y", "N"]) == "Y":
        formats = {"P": "PDF", "T": "TXT"}
        export_format = formats[ask_option("¿PDF (P) o TXT (T)?", formats)]
        run_steps([f"Exportando en {export_format}..."])

    show_summary(topic, language, export_format)
    console.print("[bold]Mi trabajo aquí ha terminado, nos vemos cuando quieras.[/]")
    show_banner("Ha sido un placer")


if __name__ == "__main__":
    app()