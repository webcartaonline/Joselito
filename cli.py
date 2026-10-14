import os
import time
from pathlib import Path
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
from wiki_enrichment.domain.models import ArticleContent, BriefSummary, EnrichedContent

WIKIPEDIA_LANGUAGE = "es"
BANNER_FONT = "larry3d"
PENDING_STEP_SECONDS = 1

TOPIC_QUESTION = "¿Qué tema quieres investigar?"
LANGUAGE_QUESTION = "¿A qué idioma quieres traducirlo?"
SUMMARY_QUESTION = "¿Quieres un resumen breve? (Y/N)"
EXPORT_QUESTION = "¿Quieres exportar la investigación? (Y/N)"
FORMAT_QUESTION = "¿PDF (P) o TXT (T)?"
SUMMARY_FORMAT_QUESTION = "¿Resumen en PDF (P) o TXT (T)?"
FILE_NAME_QUESTION = "¿Con qué nombre quieres guardar el archivo?"

YES, NO = "Y", "N"
EXPORT_FORMATS = {"P": "PDF", "T": "TXT"}
ENRICH_ERROR = (
    "No he podido enriquecer el texto con IA. Revisa que tienes HF_TOKEN en el archivo "
    ".env, que tu cuenta de Hugging Face tiene créditos y que hay conexión a internet. "
    "El documento se guardará sin el texto enriquecido."
)
SUMMARY_ERROR = (
    "No he podido generar el resumen breve. Revisa que tienes HF_TOKEN en el archivo "
    ".env y que hay conexión a internet. El documento se guardará sin resumen."
)
EXTENSIONS = {"PDF": ".pdf", "TXT": ".txt"}
EXPORT_FOLDER = "output"
LAST_ERROR_FILE = "ultimo_error_ia.txt"
SUMMARY_SUFFIX = "_summary"
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


def resolve_export_path(file_name: str) -> str:
    """Return the export path as an absolute path next to the repo root.

    ``EXPORT_FOLDER`` may be overridden in tests with an absolute tmp path.
    """
    base = Path(EXPORT_FOLDER)
    if not base.is_absolute():
        base = Path(__file__).resolve().parent / base
    return str(base / file_name)


def log_ai_error(detail: str) -> str:
    """Save the AI error detail so it is not lost after the long article panel.

    Best effort: never raises. Returns the path used.
    """
    path = Path(resolve_export_path(LAST_ERROR_FILE))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(detail, encoding="utf-8")
    except OSError:
        pass
    return str(path)


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
            show_error(f"No he encontrado nada sobre '{topic}' en Wikipedia. Prueba con otro tema.")
            topic = ask_text(TOPIC_QUESTION)
        except WikiEnrichmentError:
            print()
            show_error("No he podido conectar con Wikipedia. Revisa tu conexión a internet e inténtalo más tarde.")
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
    console.print(Panel(article.full_text, title=f"Resultados sobre {article.title}", border_style="green"))


def enrich_article(orchestrator: WikiEnrichmentOrchestrator, article: ArticleContent) -> str:
    """Return the AI-enriched text, or an empty text if the AI is not available."""
    try:
        print()
        [enriched] = run_steps([
            ("Enriqueciendo con IA...", lambda: orchestrator.enrich_article(article)),
        ])
        return enriched.ai_summary
    except WikiEnrichmentError as error:
        print()
        detail = str(error)
        error_path = log_ai_error(f"Enriquecimiento con IA fallido.\nDetalle: {detail}\n")
        show_error(f"{ENRICH_ERROR}\n\nDetalle: {detail}\n\nHe guardado el detalle en {error_path}")
        return ""


def show_enriched(ai_summary: str) -> None:
    print()
    console.print(Panel(ai_summary, title="Texto enriquecido con IA", border_style="magenta"))


def translate_text(language: str) -> str:
    """Return the translated text.

    TODO: call the orchestrator once the translation adapter exists.
    """
    print()
    run_steps([(f"Traduciendo a {language}...", None)])
    return ""


def build_content(
    article: ArticleContent, ai_summary: str, translated_summary: str
) -> EnrichedContent:
    """Group the original, enriched and translated contents to export."""
    return EnrichedContent(
        original_article=article,
        ai_summary=ai_summary,
        translated_summary=translated_summary,
    )


class BriefSummaryFlow:
    """Handle the optional brief summary in the terminal."""

    def __init__(self, orchestrator: WikiEnrichmentOrchestrator) -> None:
        """Keep the orchestrator that summarizes and translates the text."""
        self._orchestrator = orchestrator

    def request(
        self, content: EnrichedContent, language: str
    ) -> Optional[BriefSummary]:
        """Ask for a brief summary, generate it and show it before exporting."""
        if ask_option(SUMMARY_QUESTION, [YES, NO]) == NO:
            return None
        try:
            print()
            [summary] = run_steps([(
                f"Resumiendo y traduciendo a {language}...",
                lambda: self._orchestrator.summarize(content, language),
            )])
        except WikiEnrichmentError as error:
            print()
            detail = str(error)
            error_path = log_ai_error(f"Resumen breve fallido.\nDetalle: {detail}\n")
            show_error(f"{SUMMARY_ERROR}\n\nDetalle: {detail}\n\nHe guardado el detalle en {error_path}")
            return None
        self.show(summary)
        return summary

    @staticmethod
    def show(summary: BriefSummary) -> None:
        """Show the translated summary in a panel."""
        print()
        console.print(
            Panel(summary.translated_text, title=f"Resumen breve de {summary.title}", border_style="blue")
        )

    @staticmethod
    def ask_format() -> str:
        """Ask in which format the summary is saved, apart from the enriched text."""
        return EXPORT_FORMATS[ask_option(SUMMARY_FORMAT_QUESTION, EXPORT_FORMATS)]


def summary_path(path: str, summary_format: str) -> str:
    """Return the summary path, next to the enriched text file."""
    base, _ = os.path.splitext(path)
    return f"{base}{SUMMARY_SUFFIX}{EXTENSIONS[summary_format]}"


def export_research(
    orchestrator: WikiEnrichmentOrchestrator,
    content: EnrichedContent,
    summary: Optional[BriefSummary] = None,
) -> tuple[str, str]:
    if ask_option(EXPORT_QUESTION, [YES, NO]) == NO:
        return NOT_EXPORTED, NO_FILE
    export_format = EXPORT_FORMATS[ask_option(FORMAT_QUESTION, EXPORT_FORMATS)]
    file_name = ask_file_name(export_format)
    # Se mantiene la ruta relativa ("output/...") porque los tests y el
    # resumen la esperan así; para evitar abrir un TXT viejo, tras exportar
    # se muestra la ruta absoluta real donde se escribió el archivo.
    path = f"{EXPORT_FOLDER}/{file_name}"
    steps: list[Step] = [(
        f"Exportando {file_name}...",
        lambda: orchestrator.export_document(content, export_format, path),
    )]
    if summary:
        summary_format = BriefSummaryFlow.ask_format()
        summary_file = summary_path(path, summary_format)
        steps.append((
            f"Exportando {os.path.basename(summary_file)}...",
            lambda: orchestrator.export_summary(summary, summary_format, summary_file),
        ))
    try:
        print()
        run_steps(steps)
    except WikiEnrichmentError:
        print()
        show_error("No he podido guardar el archivo. Revisa que tienes permisos y espacio en disco.")
        return NOT_EXPORTED, NO_FILE
    console.print(f"[dim]Archivo guardado en {Path(path).resolve()}[/]")
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
    translated_summary = translate_text(language)
    content = build_content(article, ai_summary, translated_summary)
    summary = None
    if ai_summary:
        summary = BriefSummaryFlow(orchestrator).request(content, language)
    export_format, file_name = export_research(orchestrator, content, summary)

    show_summary(topic, language, export_format, file_name)
    say_goodbye()


if __name__ == "__main__":
    app()
