import logging
import math
import os
import select
import sys
import time
from dataclasses import dataclass
from pathlib import Path
import unicodedata
from typing import Callable, Optional

import pyfiglet
import typer
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from application.wiki_enrichment_orchestrator import WikiEnrichmentOrchestrator
from bootstrap import build_orchestrator
from domain.exceptions import (
    ProviderTimeoutError,
    RateLimitError,
    ResourceNotFoundError,
    WikiEnrichmentError,
)
from domain.models import (
    ArticleContent,
    BriefSummary,
    EnrichedContent,
    SearchResult,
)
from infrastructure.logging_config import (
    LOGGER_NAME,
    configure_logging,
    generate_run_id,
)

logger = logging.getLogger(f"{LOGGER_NAME}.cli")

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
CONFIRM_QUESTION = "¿Era esto lo que buscabas? (Y/N)"
CHOOSE_QUESTION = "¿Cuál de estos buscabas? Escribe su número"
RETYPE_OPTION = "Volver a escribir el tema"
NO_DESCRIPTION = "(Wikipedia no cuenta con una descripción de este artículo)"
RETRY_QUESTION = "¿Quieres reintentar? (Y/N)"
RETRY_DOWNLOAD_QUESTION = "Wikipedia sigue tardando. ¿Quieres reintentar la descarga? (Y/N)"

MAX_CONNECTION_ATTEMPTS = 3
MAX_SLOW_ATTEMPTS = 3
SLOW_ATTEMPTS_BEFORE_NEW_TOPIC = 2
DEFAULT_RETRY_WAIT_SECONDS = 60  # Used when Wikipedia does not say how long to wait.
COUNTDOWN_TICK_SECONDS = 0.1
IS_WINDOWS = os.name == "nt"
EMPTY_ANSWER_ERROR = "No has escrito nada. Inténtalo de nuevo."
MAX_TOPIC_LENGTH = 300  # Longest search that Wikipedia accepts.

YES, NO = "Y", "N"
EXPORT_FORMATS = {"P": "PDF", "T": "TXT"}
ENRICH_ERROR = (
    "No he podido enriquecer el texto con IA. Revisa que tienes DEEPSEEK_API_KEY en el archivo "
    ".env, que tu cuenta de DeepSeek tiene saldo y que hay conexión a internet. "
    "El documento se guardará sin el texto enriquecido."
)
ENRICH_TIMEOUT_ERROR = (
    "La IA está tardando demasiado en responder. Inténtalo de nuevo más tarde. "
    "El documento se guardará sin el texto enriquecido."
)
WIKIPEDIA_RETRYING = "Wikipedia está tardando demasiado. Lo intento otra vez..."
WIKIPEDIA_SLOW_NEW_TOPIC = (
    "Wikipedia sigue tardando demasiado con '{topic}'. Prueba a escribir el tema de otra "
    "manera, por ejemplo con menos palabras o sin faltas de ortografía."
)
WIKIPEDIA_SLOW_CHOOSE_OTHER = "Wikipedia sigue tardando demasiado con '{title}'. Elige otro resultado."
WIKIPEDIA_TIMEOUT_ERROR = (
    "Wikipedia no está respondiendo a tiempo. Seguramente tiene problemas ahora mismo. "
    "Vuelve a abrir el programa dentro de unos minutos."
)
CONNECTION_ERROR = (
    "No he podido conectar con Wikipedia (intento {attempt} de {total}). "
    "Revisa tu conexión a internet."
)
CONNECTION_FINAL_ERROR = (
    "No he podido conectar con Wikipedia después de {total} intentos. Puede que no tengas "
    "internet o que Wikipedia no esté funcionando ahora mismo. Revisa tu conexión y vuelve "
    "a abrir el programa más tarde."
)
RATE_LIMIT_ERROR = (
    "Wikipedia ha recibido demasiadas peticiones y hay que esperar antes de volver a "
    "intentarlo (intento {attempt} de {total})."
)
COUNTDOWN_MESSAGE = "Podrás reintentar en {seconds} segundos..."
COUNTDOWN_DONE = "Ya puedes volver a intentarlo."
PATIENCE_MESSAGE = "Paciencia, si no Wikipedia bloqueará esta IP"
NO_RETRY_MESSAGE = "De acuerdo, no lo vuelvo a intentar. Vuelve a abrir el programa cuando quieras."
CANCELLED_MESSAGE = "Has cancelado la investigación. Puedes volver a empezar cuando quieras."
UNEXPECTED_ERROR = (
    "Ha ocurrido un error inesperado y no he podido continuar. "
    "Inténtalo de nuevo y, si se repite, avisa al equipo."
)
SUMMARY_ERROR = (
    "No he podido generar el resumen breve. Revisa que tienes DEEPSEEK_API_KEY en el archivo "
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


def topic_error(topic: str) -> Optional[str]:
    """Return why a topic is not valid, or None if it can be searched."""
    if not topic:
        return EMPTY_ANSWER_ERROR
    if len(topic) > MAX_TOPIC_LENGTH:
        return f"El tema es demasiado largo (máximo {MAX_TOPIC_LENGTH} caracteres)."
    return None


def language_error(language: str) -> Optional[str]:
    """Return why a language is not valid, or None if it can be used."""
    if not language:
        return EMPTY_ANSWER_ERROR
    if not all(char.isalpha() or char.isspace() for char in language):
        return f"'{language}' no es un idioma válido. Escribe solo letras, por ejemplo: inglés."
    return None


def ask_text(
    question: str,
    validate: Callable[[str], Optional[str]],
    answer: Optional[str] = None,
) -> str:
    """Ask until the answer is valid.

    ``answer`` is a value the user already gave (for example, with --tema).
    """
    while True:
        if answer is None:
            answer = prompt_user(question)
        answer = answer.strip()
        error = validate(answer)
        if error is None:
            return answer
        print()
        show_error(error)
        answer = None


def ask_topic(answer: Optional[str] = None) -> str:
    """Ask for a topic until it is valid and log which one was chosen."""
    topic = ask_text(TOPIC_QUESTION, topic_error, answer)
    logger.info("Topic selected: %s", topic)
    return topic


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


def one_line(text: str) -> str:
    """Join the lines of a text so it can be cut to a single line on screen."""
    return " ".join(text.split())


def show_first_result(result: SearchResult) -> None:
    """Show the first result with Wikipedia's summary, or a note if it has none."""
    print()
    console.print(Panel(
        result.summary or NO_DESCRIPTION,
        title=f"Primer resultado: {result.title}",
        border_style="cyan",
    ))


def show_options(results: list[SearchResult]) -> None:
    """Show the other results numbered, plus a last option to write the topic again.

    Each summary is cut to one line so the whole list fits on the screen.
    """
    lines = []
    for number, result in enumerate(results, start=1):
        lines.append(Text.assemble((f"{number}. ", "bold cyan"), (result.title, "green")))
        description = one_line(result.summary) or NO_DESCRIPTION
        lines.append(Text(f"   {description}", style="dim", no_wrap=True, overflow="ellipsis"))
    lines.append(Text.assemble((f"{len(results) + 1}. ", "bold cyan"), RETYPE_OPTION))
    print()
    console.print(Panel(Group(*lines), title="Otros resultados", border_style="cyan"))


def ask_choice(results: list[SearchResult]) -> Optional[SearchResult]:
    """Return the result the user picks, or None if they want to write the topic again."""
    logger.info("Showing other results: count=%d", len(results))
    logger.debug("Other results: %s", [result.title for result in results])
    show_options(results)
    options = [str(number) for number in range(1, len(results) + 2)]
    index = int(ask_option(CHOOSE_QUESTION, options)) - 1
    if index >= len(results):
        logger.info("The user wants to write the topic again")
        return None
    logger.info("Result chosen from the list: title=%s", results[index].title)
    return results[index]


def prefetch_article(
    orchestrator: WikiEnrichmentOrchestrator, title: str
) -> Optional[ArticleContent]:
    """Download the first result before asking, so a "yes" needs no second download.

    If it fails, nothing is lost and it does not count as a failure: the
    article is downloaded later, only if the user confirms it.
    """
    try:
        return orchestrator.fetch_article_by_title(title)
    except WikiEnrichmentError:
        return None


@dataclass
class WikipediaFailures:
    """Failures in a row while talking to Wikipedia.

    "No connection" and "too slow" are counted apart, and both go back to
    zero as soon as something works.
    """

    connection: int = 0
    slow: int = 0

    def reset(self) -> None:
        """Start counting again after a success."""
        self.connection = 0
        self.slow = 0


def key_was_pressed() -> bool:
    """Return True if the user pressed a key, and throw that key away.

    Windows reads each key at once (msvcrt). Mac and Linux see what was typed
    after Enter (select). If the input is not a real keyboard (for example, in
    tests) nothing is read.
    """
    if IS_WINDOWS:
        import msvcrt

        pressed = False
        while msvcrt.kbhit():
            msvcrt.getwch()
            pressed = True
        return pressed
    if not sys.stdin.isatty():
        return False
    pressed = False
    while select.select([sys.stdin], [], [], 0)[0]:
        if not sys.stdin.readline():
            break
        pressed = True
    return pressed


def discard_typed_keys() -> None:
    """Throw away anything typed during the wait, so it does not answer the next question."""
    if IS_WINDOWS:
        key_was_pressed()
    elif sys.stdin.isatty():
        import termios

        termios.tcflush(sys.stdin, termios.TCIFLUSH)


def countdown_view(message: str, impatient: bool) -> Group:
    """Return the countdown line, plus the patience message if the user pressed a key."""
    lines = [Text(message, style="yellow")]
    if impatient:
        lines.append(Text(PATIENCE_MESSAGE, style="bold red"))
    return Group(*lines)


def wait_with_countdown(seconds: int) -> None:
    """Count down before the user can retry.

    Keys pressed meanwhile have no effect: they only show the patience
    message and the countdown keeps its normal pace.
    """
    deadline = time.monotonic() + seconds
    impatient = False
    with Live(countdown_view(COUNTDOWN_MESSAGE.format(seconds=seconds), impatient), console=console) as live:
        while (remaining := deadline - time.monotonic()) > 0:
            if key_was_pressed():
                impatient = True
            live.update(countdown_view(COUNTDOWN_MESSAGE.format(seconds=math.ceil(remaining)), impatient))
            time.sleep(COUNTDOWN_TICK_SECONDS)
        live.update(countdown_view(COUNTDOWN_DONE, impatient))
    discard_typed_keys()


def stop_without_retrying() -> None:
    """Close the program because the user does not want to try again."""
    print()
    console.print(NO_RETRY_MESSAGE)
    raise typer.Exit(code=1)


def handle_connection_failure(failures: WikipediaFailures, error: WikiEnrichmentError) -> None:
    """Count a failed connection and ask before trying again; close at the limit.

    When Wikipedia asks to wait (too many requests), a countdown runs first.
    """
    failures.connection += 1
    print()
    if failures.connection >= MAX_CONNECTION_ATTEMPTS:
        show_error(CONNECTION_FINAL_ERROR.format(total=MAX_CONNECTION_ATTEMPTS))
        raise typer.Exit(code=1)
    attempt = {"attempt": failures.connection, "total": MAX_CONNECTION_ATTEMPTS}
    if isinstance(error, RateLimitError):
        show_error(RATE_LIMIT_ERROR.format(**attempt))
        wait_with_countdown(error.retry_after_seconds or DEFAULT_RETRY_WAIT_SECONDS)
    else:
        show_error(CONNECTION_ERROR.format(**attempt))
    if ask_option(RETRY_QUESTION, [YES, NO]) == NO:
        stop_without_retrying()


def count_slow_answer(failures: WikipediaFailures) -> int:
    """Count a slow answer and return how many there have been; close at the limit."""
    failures.slow += 1
    if failures.slow >= MAX_SLOW_ATTEMPTS:
        print()
        show_error(WIKIPEDIA_TIMEOUT_ERROR)
        raise typer.Exit(code=1)
    return failures.slow


def say_retrying() -> None:
    """Tell the user that Wikipedia was slow and it is being tried again."""
    print()
    console.print(f"[yellow]{WIKIPEDIA_RETRYING}[/]")


def search_topic(
    orchestrator: WikiEnrichmentOrchestrator, topic: str, failures: WikipediaFailures
) -> tuple[list[SearchResult], Optional[ArticleContent], str]:
    """Search the topic and download its first result in advance.

    Returns the results, that first article (None if it could not be
    downloaded) and the topic, which the user may have written again.
    """
    while True:
        try:
            print()
            [results] = run_steps([
                (f"Buscando '{topic}' en Wikipedia...", lambda: orchestrator.search_articles(topic)),
            ])
        except ResourceNotFoundError:
            print()
            show_error(f"No he encontrado nada sobre '{topic}' en Wikipedia. Prueba con otro tema.")
            topic = ask_topic()
            continue
        except ProviderTimeoutError:
            if count_slow_answer(failures) < SLOW_ATTEMPTS_BEFORE_NEW_TOPIC:
                say_retrying()
            else:
                print()
                show_error(WIKIPEDIA_SLOW_NEW_TOPIC.format(topic=topic))
                topic = ask_topic()
            continue
        except WikiEnrichmentError as error:
            handle_connection_failure(failures, error)
            continue
        failures.reset()
        [first_article] = run_steps([
            (f"Preparando '{results[0].title}'...", lambda: prefetch_article(orchestrator, results[0].title)),
        ])
        return results, first_article, topic


def download_article(
    orchestrator: WikiEnrichmentOrchestrator,
    title: str,
    failures: WikipediaFailures,
    from_list: bool,
) -> Optional[ArticleContent]:
    """Download the chosen article, or return None to show the list again.

    If Wikipedia is slow twice, a result from the list sends the user back
    to the list; the confirmed first result asks whether to try again.
    """
    while True:
        try:
            print()
            [article] = run_steps([
                (f"Descargando '{title}'...", lambda: orchestrator.fetch_article_by_title(title)),
            ])
        except ResourceNotFoundError:
            print()
            show_error(f"No he podido abrir el artículo '{title}'. Elige otro resultado.")
            return None
        except ProviderTimeoutError:
            if count_slow_answer(failures) < SLOW_ATTEMPTS_BEFORE_NEW_TOPIC:
                say_retrying()
            elif from_list:
                print()
                show_error(WIKIPEDIA_SLOW_CHOOSE_OTHER.format(title=title))
                return None
            elif ask_option(RETRY_DOWNLOAD_QUESTION, [YES, NO]) == NO:
                stop_without_retrying()
            continue
        except WikiEnrichmentError as error:
            handle_connection_failure(failures, error)
            continue
        failures.reset()
        return article


def choose_article(
    orchestrator: WikiEnrichmentOrchestrator,
    results: list[SearchResult],
    first_article: Optional[ArticleContent],
    failures: WikipediaFailures,
) -> Optional[ArticleContent]:
    """Return the article the user confirms or picks, or None to write the topic again.

    The results and the article downloaded in advance only live inside this
    function: when it returns, Python frees whatever was not chosen.
    """
    first = results[0]
    logger.info("Confirming the first result: title=%s", first.title)
    show_first_result(first)
    if ask_option(CONFIRM_QUESTION, [YES, NO]) == YES:
        logger.info("First result confirmed: title=%s", first.title)
        article = first_article or download_article(
            orchestrator, first.title, failures, from_list=False
        )
        if article is not None:
            return article
        logger.info("Confirmed result unavailable; showing the other results")
    else:
        logger.info("First result rejected: title=%s", first.title)
    first_article = None  # Not wanted (or not available): forget it right away.
    others = results[1:]
    while True:
        choice = ask_choice(others)
        if choice is None:
            return None
        article = download_article(orchestrator, choice.title, failures, from_list=True)
        if article is not None:
            return article


def research_topic(
    orchestrator: WikiEnrichmentOrchestrator, topic: str
) -> tuple[ArticleContent, str]:
    """Search until the user confirms a result. Nothing is enriched before that."""
    failures = WikipediaFailures()
    while True:
        results, first_article, topic = search_topic(orchestrator, topic, failures)
        article = choose_article(orchestrator, results, first_article, failures)
        if article is not None:
            return article, topic
        topic = ask_topic()


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
    except ProviderTimeoutError:
        print()
        show_error(ENRICH_TIMEOUT_ERROR)
        logger.warning(
            "AI enrichment timed out; exporting without enriched text: title=%s",
            article.title,
        )
        return ""
    except WikiEnrichmentError as error:
        print()
        detail = str(error)
        error_path = log_ai_error(f"Enriquecimiento con IA fallido.\nDetalle: {detail}\n")
        show_error(f"{ENRICH_ERROR}\n\nDetalle: {detail}\n\nHe guardado el detalle en {error_path}")
        logger.error(
            "AI enrichment failed; exporting without enriched text: title=%s",
            article.title,
        )
        return ""
    logger.info(
        "AI enrichment ready: title=%s characters=%d",
        article.title,
        len(enriched.ai_summary),
    )
    return enriched.ai_summary


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
            logger.info("Brief summary declined by the user")
            return None
        logger.info("Brief summary requested: target=%s", language)
        try:
            print()
            [summary] = run_steps([(
                "Resumiendo...",
                lambda: self._orchestrator.summarize(content, language),
            )])
        except WikiEnrichmentError as error:
            print()
            detail = str(error)
            error_path = log_ai_error(f"Resumen breve fallido.\nDetalle: {detail}\n")
            show_error(f"{SUMMARY_ERROR}\n\nDetalle: {detail}\n\nHe guardado el detalle en {error_path}")
            logger.error(
                "Brief summary failed; continuing without it: target=%s", language
            )
            return None
        self.show(summary)
        logger.info("Brief summary ready: title=%s", summary.title)
        return summary

    @staticmethod
    def show(summary: BriefSummary) -> None:
        """Show the brief summary in a panel."""
        print()
        console.print(
            Panel(summary.text, title=f"Resumen breve de {summary.title}", border_style="blue")
        )

    @staticmethod
    def ask_format() -> str:
        """Ask in which format the summary is saved, apart from the enriched text."""
        summary_format = EXPORT_FORMATS[ask_option(SUMMARY_FORMAT_QUESTION, EXPORT_FORMATS)]
        logger.info("Summary export format selected: %s", summary_format)
        return summary_format


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


def run_app(tema: Optional[str], idioma: Optional[str]) -> None:
    """Run the whole research, from the greeting to the goodbye."""
    show_banner("Hola, soy")
    show_banner("Joselito")

    topic = ask_topic(tema)
    language = ask_text(LANGUAGE_QUESTION, language_error, idioma)
    logger.info("Target language selected: %s", language)

    orchestrator = build_orchestrator(wikipedia_language=WIKIPEDIA_LANGUAGE)
    article, topic = research_topic(orchestrator, topic)
    show_article(article)
    ai_summary = enrich_article(orchestrator, article)
    if ai_summary:
        show_enriched(ai_summary)
    translated_summary = translate_article(orchestrator, article, language)
    content = build_content(article, ai_summary, translated_summary)
    summary = None
    if ai_summary:
        summary = BriefSummaryFlow(orchestrator).request(content, language)
    else:
        logger.info("No enriched text available; the brief summary is not offered")
    export_format, file_name = export_research(orchestrator, content, summary)
    logger.info("Export result: format=%s file=%s", export_format, file_name)

    show_summary(topic, language, export_format, file_name)
    say_goodbye()


@app.command()
def main(
    tema: Optional[str] = typer.Option(None, help="Tema a investigar"),
    idioma: Optional[str] = typer.Option(None, help="Idioma de la traducción"),
):
    """Joselito: investiga un tema en Wikipedia, lo enriquece y lo traduce."""
    configure_logging(run_id=generate_run_id())
    logger.info("Application started")
    try:
        run_app(tema, idioma)
    except typer.Exit:
        logger.info("Application finished with errors")
        raise
    except (KeyboardInterrupt, EOFError):
        logger.info("Application cancelled by the user")
        print()
        show_error(CANCELLED_MESSAGE)
        raise typer.Exit(code=1)
    except Exception:
        logger.critical("Unexpected error", exc_info=True)
        print()
        show_error(UNEXPECTED_ERROR)
        raise typer.Exit(code=1)
    logger.info("Application finished")


if __name__ == "__main__":
    app()
