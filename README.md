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

La traducción necesita la variable de entorno `RAPIDAPI_KEY` con la clave de
DeepTranslate. Configúrala en la terminal o en la configuración de ejecución de
PyCharm antes de iniciar la aplicación. No guardes la clave en el repositorio.

```bash
python cli.py
python cli.py --tema "Python" --idioma inglés
```

## Tests

```bash
pytest
```
