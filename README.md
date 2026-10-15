# Joselito

Herramienta de terminal que busca un tema en Wikipedia, lo enriquece con IA y lo
traduce. La arquitectura está explicada en [docs/architecture.md](docs/architecture.md).

## Instalación

Con el entorno virtual activado, desde la carpeta del proyecto:

```bash
pip install -r requirements.txt
pip install -e .
```

`pip install -e .` instala el paquete `wiki_enrichment` (carpeta `src`) para que
`cli.py` y los tests puedan importarlo. Solo hace falta hacerlo una vez.

## Uso

La traducción usa Google Cloud Translation Basic (v2) y necesita la variable de
entorno `GOOGLE_TRANSLATE_API_KEY` con una clave de API de Google Cloud de un
proyecto que tenga habilitada la
[Cloud Translation API](https://console.cloud.google.com/apis/library/translate.googleapis.com).
Puedes definirla en un archivo `.env` en la raíz del proyecto (UTF-8), exportarla
en la terminal o configurarla en PyCharm antes de iniciar la aplicación. El
arranque carga `.env` sin sobrescribir variables ya definidas. Usa
[.env.example](.env.example) como plantilla:

```bash
GOOGLE_TRANSLATE_API_KEY=your_key_here
```

`.env` está en `.gitignore`: no guardes la clave en el repositorio. La clave se
envía en la cabecera `x-goog-api-key`, nunca en la URL.

```bash
python cli.py
python cli.py --tema "Python" --idioma inglés
```

## Tests

```bash
pytest
```
