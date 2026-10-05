import time
from typing import Callable, Optional

import pyfiglet
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

from wiki_enrichment.application.use_cases import WikiEnrichmentOrchestrator
from wiki_enrichment.bootstrap import build_orchestrator
from wiki_enrichment.domain.exceptions import ResourceNotFoundError, WikiEnrichmentError
from wiki_enrichment.domain.models import ArticleContent

WIKIPEDIA_LANGUAGE = "es"
BANNER_FONT = "larry3d"
PENDING_STEP_SECONDS = 1

TOPIC_QUESTION = "¿Qué tema quieres investigar?"
LANGUAGE_QUESTION = "¿A qué idioma quieres traducirlo?"
EXPORT_QUESTION = "¿Quieres exportar la investigación? (Y/N)"
FORMAT_QUESTION = "¿PDF (P) o TXT (T)?"

YES, NO = "Y", "N"
EXPORT_FORMATS = {"P": "PDF", "T": "TXT"}
NOT_EXPORTED = "No"

Step = tuple[str, Optional[Callable[[], object]]]

console = Console()
app = typer.Typer()


def show_banner(text: str) -> None:
    console.print(pyfiglet.figlet_format(text, font=BANNER_FONT), style="bold cyan")


def show_error(message: str) -> None:
    console.print(Panel(message, border_style="red", title="Error"))


class QuestionPrompt(Prompt):
    prompt_suffix = " "


def prompt_user(question: str) -> str:
    console.print()
    console.rule(style="dim")
    return QuestionPrompt.ask(f"[bold yellow]#[/] [bold yellow]{question}[/]\n  [dim]»[/]")


def ask_text(question: str) -> str:
    while True:
        answer = prompt_user(question).strip()
        if answer:
            return answer
        print()
        show_error("No has escrito nada. Inténtalo de nuevo.")


def ask_option(question: str, options: list[str] | dict[str, str]) -> str:
    valid_options = " o ".join(options)
    while True:
        answer = prompt_user(question).strip().upper()
        if not answer:
            print()
            show_error(f"No has escrito nada. Escribe {valid_options}.")
        elif answer not in options:
            print()
            show_error(f"'{answer}' no es una opción válida. Escribe {valid_options}.")
        else:
            return answer


def run_step(action: Optional[Callable[[], object]]) -> object:
    if action is None:
        time.sleep(PENDING_STEP_SECONDS)
        return None
    return action()



def run_steps(steps: list[Step]) -> list[object]:
    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Empezando...", total=len(steps))
        for description, action in steps:
            progress.update(task, description=description)
            results.append(run_step(action))
            progress.advance(task)
    return results


def research_topic(
    orchestrator: WikiEnrichmentOrchestrator, topic: str, language: str
) -> tuple[ArticleContent, str]:
    while True:
        try:
            print()
            article, _, _ = run_steps([
                (f"Buscando '{topic}' en Wikipedia...", lambda: orchestrator.fetch_article(topic)),
                ("Enriqueciendo con IA...", None),
                (f"Traduciendo a {language}...", None),
            ])
            return article, topic
        except ResourceNotFoundError:
            print()
            show_error(f"No he encontrado nada sobre '{topic}' en Wikipedia. Prueba con otro tema.")
            topic = ask_text(TOPIC_QUESTION)
        except WikiEnrichmentError:
            print()
            show_error("No he podido conectar con Wikipedia. Revisa tu conexión a internet e inténtalo más tarde.")
            raise typer.Exit(code=1)


def show_article(article: ArticleContent) -> None:
    print()
    console.print(Panel(article.full_text, title=f"Resultados sobre {article.title}", border_style="green"))


def export_research() -> str:
    if ask_option(EXPORT_QUESTION, [YES, NO]) == NO:
        return NOT_EXPORTED
    export_format = EXPORT_FORMATS[ask_option(FORMAT_QUESTION, EXPORT_FORMATS)]
    print()
    run_steps([(f"Exportando en {export_format}...", None)])
    return export_format


def show_summary(topic: str, language: str, export_format: str) -> None:
    print()
    table = Table(title="Resumen")
    table.add_column("Dato", style="cyan")
    table.add_column("Valor", style="green")
    table.add_row("Tema", topic)
    table.add_row("Idioma", language)
    table.add_row("Exportado", export_format)
    console.print(table)
    print()


def say_goodbye() -> None:
    print("=========================================================")
    console.print("[bold]Mi trabajo aquí ha terminado, nos vemos cuando quieras.[/]")
    print("=========================================================")
    show_banner("Ha sido un placer")


@app.command()
def main(
    tema: Optional[str] = typer.Option(None, help="Tema a investigar"),
    idioma: Optional[str] = typer.Option(None, help="Idioma de la traducción"),
):
    """Joselito: investiga un tema en Wikipedia, lo enriquece y lo traduce."""
    show_banner("Hola, soy")
    show_banner("Joselito")

    topic = tema or ask_text(TOPIC_QUESTION)
    language = idioma or ask_text(LANGUAGE_QUESTION)

    orchestrator = build_orchestrator(wikipedia_language=WIKIPEDIA_LANGUAGE)
    article, topic = research_topic(orchestrator, topic, language)
    show_article(article)
    export_format = export_research()

    show_summary(topic, language, export_format)
    say_goodbye()


if __name__ == "__main__":
    app()
