import time
import unicodedata
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
from wiki_enrichment.domain.exceptions import (
    ProviderTimeoutError,
    ResourceNotFoundError,
    WikiEnrichmentError,
)
from wiki_enrichment.domain.models import ArticleContent, EnrichedContent

WIKIPEDIA_LANGUAGE = "es"
BANNER_FONT = "larry3d"
PENDING_STEP_SECONDS = 1

TOPIC_QUESTION = "¿Qué tema quieres investigar?"
LANGUAGE_QUESTION = "¿A qué idioma quieres traducirlo?"
EXPORT_QUESTION = "¿Quieres exportar la investigación? (Y/N)"
FORMAT_QUESTION = "¿PDF (P) o TXT (T)?"
FILE_NAME_QUESTION = "¿Con qué nombre quieres guardar el archivo?"

YES, NO = "Y", "N"
EXPORT_FORMATS = {"P": "PDF", "T": "TXT"}
ENRICH_ERROR = (
    "No he podido enriquecer el texto con IA. Revisa que tienes HF_TOKEN en el archivo "
    ".env, que tu cuenta de Hugging Face tiene créditos y que hay conexión a internet. "
    "El documento se guardará sin el texto enriquecido."
)
EXTENSIONS = {"PDF": ".pdf", "TXT": ".txt"}
EXPORT_FOLDER = "output"
NOT_EXPORTED = "No"
NO_FILE = "-"

FORBIDDEN_CHARACTERS = '\\/:*?"<>|'
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{device}{number}" for device in ("COM", "LPT") for number in range(1, 10)
}
MAX_FILE_NAME_LENGTH = 100

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


def _casefold(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def _normalize_yes_no(answer: str) -> str | None:
    """Map common affirmative/negative answers to canonical Y/N."""

    key = _casefold(answer.strip())
    if key in {"y", "yes", "si", "sí"}:
        return YES
    if key in {"n", "no"}:
        return NO
    return None


def ask_option(question: str, options: list[str] | dict[str, str]) -> str:
    valid_options = " o ".join(options)
    is_yes_no = isinstance(options, list) and options == [YES, NO]
    while True:
        raw = prompt_user(question).strip()
        if not raw:
            print()
            show_error(f"No has escrito nada. Escribe {valid_options}.")
            continue

        if is_yes_no:
            normalized = _normalize_yes_no(raw)
            if normalized is None:
                print()
                show_error(
                    f"'{raw.strip().upper()}' no es una opción válida. "
                    f"Escribe {valid_options}."
                )
            else:
                return normalized
            continue

        answer = raw.upper()
        if isinstance(options, dict):
            if answer not in options:
                print()
                show_error(
                    f"'{answer}' no es una opción válida. Escribe {valid_options}."
                )
            else:
                return answer
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
    orchestrator: WikiEnrichmentOrchestrator, topic: str
) -> tuple[ArticleContent, str]:
    while True:
        try:
            print()
            [article] = run_steps([
                (f"Buscando '{topic}' en Wikipedia...", lambda: orchestrator.fetch_article(topic)),
            ])
            return article, topic
        except ResourceNotFoundError:
            print()
            show_error(
                f"No he encontrado nada sobre '{topic}' en Wikipedia. "
                "Prueba con otro tema."
            )
            topic = ask_text(TOPIC_QUESTION)
        except WikiEnrichmentError:
            print()
            show_error(
                "No he podido conectar con Wikipedia. Revisa tu conexión a internet "
                "e inténtalo más tarde."
            )
            raise typer.Exit(code=1)


def file_name_error(name: str) -> Optional[str]:
    """Return why a file name is not valid, or None if it can be used."""
    if not name:
        return "No has escrito nada. Inténtalo de nuevo."
    forbidden = sorted({char for char in name if char in FORBIDDEN_CHARACTERS})
    if forbidden:
        return f"El nombre no puede llevar estos símbolos: {' '.join(forbidden)}"
    if name.endswith("."):
        return "El nombre no puede terminar en punto."
    if name.upper() in RESERVED_NAMES:
        return f"'{name}' es un nombre reservado por el sistema. Elige otro."
    if len(name) > MAX_FILE_NAME_LENGTH:
        return f"El nombre es demasiado largo (máximo {MAX_FILE_NAME_LENGTH} caracteres)."
    return None


def remove_extension(name: str, extension: str) -> str:
    if name.lower().endswith(extension):
        return name[: -len(extension)].strip()
    return name


def ask_file_name(export_format: str) -> str:
    extension = EXTENSIONS[export_format]
    while True:
        name = remove_extension(prompt_user(FILE_NAME_QUESTION).strip(), extension)
        error = file_name_error(name)
        if error is None:
            return f"{name}{extension}"
        print()
        show_error(error)


def show_article(article: ArticleContent) -> None:
    print()
    console.print(
        Panel(
            article.full_text,
            title=f"Resultados sobre {article.title}",
            border_style="green",
        )
    )


def translate_article(
    orchestrator: WikiEnrichmentOrchestrator,
    article: ArticleContent,
    language: str,
) -> str:
    """Translate and display article text, reporting expected provider failures."""

    try:
        [translated_text] = run_steps(
            [
                (
                    f"Traduciendo a {language} con Google Translate...",
                    lambda: orchestrator.translate_article(article, language),
                ),
            ]
        )
    except ProviderTimeoutError:
        print()
        show_error("Google Translate ha tardado demasiado. Inténtalo de nuevo más tarde.")
        raise typer.Exit(code=1) from None
    except WikiEnrichmentError as exc:
        print()
        show_error(f"No he podido traducir el contenido con Google Translate: {exc}")
        raise typer.Exit(code=1) from exc

    print()
    console.print(Panel(translated_text, title=f"Traducción al {language}", border_style="green"))
    return translated_text


def enrich_article(orchestrator: WikiEnrichmentOrchestrator, article: ArticleContent) -> str:
    """Return the AI-enriched text, or an empty text if the AI is not available."""
    try:
        print()
        [enriched] = run_steps([
            ("Enriqueciendo con IA...", lambda: orchestrator.enrich_article(article)),
        ])
        return enriched.ai_summary
    except WikiEnrichmentError:
        print()
        show_error(ENRICH_ERROR)
        return ""


def show_enriched(ai_summary: str) -> None:
    print()
    console.print(Panel(ai_summary, title="Texto enriquecido con IA", border_style="magenta"))


def build_content(
    article: ArticleContent, ai_summary: str, translated_summary: str
) -> EnrichedContent:
    """Group the original, enriched and translated contents to export."""
    return EnrichedContent(
        original_article=article,
        ai_summary=ai_summary,
        translated_summary=translated_summary,
    )


def export_research(
    orchestrator: WikiEnrichmentOrchestrator, content: EnrichedContent
) -> tuple[str, str]:
    if ask_option(EXPORT_QUESTION, [YES, NO]) == NO:
        return NOT_EXPORTED, NO_FILE
    export_format = EXPORT_FORMATS[ask_option(FORMAT_QUESTION, EXPORT_FORMATS)]
    file_name = ask_file_name(export_format)
    path = f"{EXPORT_FOLDER}/{file_name}"
    try:
        print()
        run_steps([(
            f"Exportando {file_name}...",
            lambda: orchestrator.export_document(content, export_format, path),
        )])
    except WikiEnrichmentError:
        print()
        show_error("No he podido guardar el archivo. Revisa que tienes permisos y espacio en disco.")
        return NOT_EXPORTED, NO_FILE
    return export_format, path


def show_summary(topic: str, language: str, export_format: str, file_name: str) -> None:
    print()
    table = Table(title="Resumen")
    table.add_column("Dato", style="cyan")
    table.add_column("Valor", style="green")
    table.add_row("Tema", topic)
    table.add_row("Idioma", language)
    table.add_row("Exportado", export_format)
    table.add_row("Archivo", file_name)
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
    article, topic = research_topic(orchestrator, topic)
    show_article(article)
    ai_summary = enrich_article(orchestrator, article)
    if ai_summary:
        show_enriched(ai_summary)
    translated_summary = translate_article(orchestrator, article, language)
    content = build_content(article, ai_summary, translated_summary)
    export_format, file_name = export_research(orchestrator, content)

    show_summary(topic, language, export_format, file_name)
    say_goodbye()


if __name__ == "__main__":
    app()
