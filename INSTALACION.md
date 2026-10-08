# Guía de instalación de Joselito (desde cero)

Esta guía es para alguien que **nunca ha instalado un proyecto de programación**.
Síguela **en orden**, sin saltarte pasos.

Joselito es un programa que se usa escribiendo en una **terminal** (una ventana negra donde se escriben órdenes). Busca un tema en Wikipedia, lo mejora con inteligencia artificial y lo traduce.

---

## Índice

0. [Antes de empezar: cosas básicas](#0-antes-de-empezar-cosas-básicas)
1. [Instalar los programas necesarios](#1-instalar-los-programas-necesarios-solo-una-vez)
2. [Descargar e instalar el proyecto](#2-descargar-e-instalar-el-proyecto-solo-una-vez)
3. [Poner tu clave de inteligencia artificial](#3-poner-tu-clave-de-inteligencia-artificial-solo-una-vez)
4. [Usar Joselito](#4-usar-joselito)
5. [Abrir el proyecto otro día](#5-abrir-el-proyecto-otro-día)
6. [Abrirlo con Visual Studio Code](#6-abrirlo-con-visual-studio-code)
7. [Abrirlo con PyCharm](#7-abrirlo-con-pycharm)
8. [Atajo opcional: escribir `wiki` y listo](#8-atajo-opcional-escribir-wiki-y-listo)
9. [Si algo falla](#9-si-algo-falla)

---

## 0. Antes de empezar: cosas básicas

### ¿Qué es cada terminal?

En Windows hay varias terminales. Hacen lo mismo, pero **cada una habla un "idioma" un poco distinto**. Por eso, en esta guía, cuando un comando cambia según la terminal, verás un apartado para cada una.

| Terminal | Cómo abrirla |
|---|---|
| **PowerShell** | Pulsa la tecla Windows ⊞, escribe `PowerShell` y pulsa Enter. |
| **CMD** | Pulsa la tecla Windows ⊞, escribe `cmd` y pulsa Enter. |
| **Git Bash** | Pulsa la tecla Windows ⊞, escribe `Git Bash` y pulsa Enter. *(Solo existe después de instalar Git en el paso 1).* |

> 👉 **Consejo:** si no sabes cuál elegir, usa **PowerShell**. Es la que usan por dentro VS Code y PyCharm.

### Cómo pegar un comando

1. Copia el comando de esta guía (selecciónalo y pulsa `Ctrl + C`).
2. Pégalo en la terminal:
   - **PowerShell y CMD:** `Ctrl + V` o clic derecho.
   - **Git Bash:** `Shift + Insert` o clic derecho → *Paste*. ⚠️ En Git Bash, `Ctrl + V` **no funciona**.
3. Pulsa **Enter**.
4. **Espera** a que termine. Sabrás que ha terminado cuando vuelva a aparecer la línea para escribir (por ejemplo `PS C:\Users\Ana>`).

### Reglas de oro

- Pega **un recuadro gris cada vez** (todo lo que haya dentro) y espera a que termine antes de pegar el siguiente.
- Las líneas que empiezan por `#` son **explicaciones**. No hace falta pegarlas.
- Si ves texto en **rojo** o la palabra `error`, para y mira el apartado [9. Si algo falla](#9-si-algo-falla).
- Donde ponga `<algo entre símbolos>`, tienes que cambiarlo por tu dato real (sin los símbolos `<` `>`).

### Dónde va a quedar el proyecto

En esta guía el proyecto se guarda en:

```
C:\Users\<TuUsuario>\Proyectos\Joselito
```

No hace falta que escribas tu usuario: los comandos lo ponen solos.

> Si ya tienes el proyecto en otra carpeta (por ejemplo `D:\Clase\manu\WikiCoders\Repositorio`), cambia esa ruta en todos los comandos de esta guía.

---

## 1. Instalar los programas necesarios (solo una vez)

Necesitas 4 programas:

| Programa | Para qué sirve |
|---|---|
| **Python** | Es el lenguaje en el que está hecho Joselito. Sin él no funciona. |
| **Git** | Sirve para descargar el proyecto desde GitHub. También instala **Git Bash**. |
| **Visual Studio Code** | Editor para ver y cambiar el código. |
| **PyCharm** | Otro editor, especializado en Python. |

### 1.1 Instalar Python, Git y VS Code

1. Abre **PowerShell**.
2. Pega estos comandos **uno a uno** (un recuadro cada vez). Si te pregunta algo, escribe `Y` y pulsa Enter. Si Windows pregunta "¿Quieres permitir que esta aplicación haga cambios?", pulsa **Sí**.

```powershell
winget install -e --id Python.Python.3.13
```
```powershell
winget install -e --id Git.Git
```
```powershell
winget install -e --id Microsoft.VisualStudioCode
```

3. **Cierra PowerShell** y vuelve a abrirlo. Esto es obligatorio para que reconozca los programas nuevos.

> ❓ Si sale `winget no se reconoce como un comando`: abre la **Microsoft Store**, busca **"Instalador de aplicaciones"** (App Installer), pulsa **Actualizar** y vuelve a intentarlo.
>
> También puedes instalarlos desde sus webs, con el botón de descarga y "Siguiente, Siguiente…":
> - Python: https://www.python.org/downloads/ → ⚠️ en la primera pantalla marca la casilla **"Add python.exe to PATH"**.
> - Git: https://git-scm.com/download/win
> - VS Code: https://code.visualstudio.com/

### 1.2 Instalar PyCharm

1. Entra en https://www.jetbrains.com/pycharm/download/ y descarga la versión gratuita para Windows.
2. Abre el archivo descargado.
3. Pulsa **Next** en todas las pantallas. En la pantalla de opciones **marca estas casillas**:
   - ✅ Create Desktop Shortcut (acceso directo en el escritorio)
   - ✅ Add "bin" folder to the PATH
4. Pulsa **Install** y luego **Finish**.

### 1.3 Comprobar que todo está bien

En **PowerShell** (recién abierto), pega estos comandos uno a uno:

```powershell
py --version
```
```powershell
git --version
```
```powershell
code --version
```

✅ **Está bien si** cada uno muestra un número de versión. Por ejemplo, `Python 3.13.5` o `git version 2.51.0`.
❌ **Está mal si** sale `no se reconoce como nombre de un cmdlet`. En ese caso, reinicia el ordenador y vuelve a probar.

> ℹ️ Usamos `py` y no `python` a propósito. En Windows, escribir `python` a veces abre la Microsoft Store en vez de Python. `py` siempre funciona.

---

## 2. Descargar e instalar el proyecto (solo una vez)

👉 **Elige UNA terminal y sigue SOLO su apartado.** No mezcles comandos de apartados distintos.

### Qué vas a hacer (para que entiendas cada paso)

1. **Crear una carpeta** `Proyectos` donde guardar el proyecto.
2. **Descargar** (clonar) el proyecto desde GitHub.
3. **Crear un entorno virtual** (`.venv`). Es como una **caja** solo para este proyecto, donde se guardan sus librerías. Así no se mezclan con las de otros proyectos.
   *Ejemplo:* es como tener una mochila para cada asignatura en vez de meter todos los libros en la misma.
4. **Activar** el entorno, es decir, "abrir la mochila". Sabrás que está activado porque aparece **`(.venv)`** al principio de la línea.
5. **Instalar las librerías** (las piezas que el proyecto necesita para funcionar) dentro de la caja.

> 🔐 Si el proyecto es privado, al descargarlo se abrirá una ventana para **iniciar sesión en GitHub**. Inicia sesión con tu cuenta (debe tener acceso al repositorio).

---

### Opción A: PowerShell

```powershell
# 1. Permitir que PowerShell active entornos (solo la primera vez; si pregunta, escribe S y Enter)
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
```powershell
# 2. Crear la carpeta Proyectos y entrar en ella
mkdir $HOME\Proyectos -Force
cd $HOME\Proyectos
```
```powershell
# 3. Descargar el proyecto y entrar en su carpeta
git clone https://github.com/webcartaonline/Joselito.git
cd Joselito
```
```powershell
# 4. Crear el entorno virtual (la "caja")
py -m venv .venv
```
```powershell
# 5. Activar el entorno → debe aparecer (.venv) al principio de la línea
.\.venv\Scripts\Activate.ps1
```
```powershell
# 6. Instalar las librerías (tarda un par de minutos; es normal ver mucho texto)
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e ".[test]"
```

➡️ Ahora ve al [paso 3](#3-poner-tu-clave-de-inteligencia-artificial-solo-una-vez).

---

### Opción B: CMD

```cmd
:: 1. Crear la carpeta Proyectos y entrar en ella
mkdir "%USERPROFILE%\Proyectos"
cd /d "%USERPROFILE%\Proyectos"
```
*(Si dice "Ya existe el subdirectorio", no pasa nada: sigue.)*

```cmd
:: 2. Descargar el proyecto y entrar en su carpeta
git clone https://github.com/webcartaonline/Joselito.git
cd Joselito
```
```cmd
:: 3. Crear el entorno virtual (la "caja")
py -m venv .venv
```
```cmd
:: 4. Activar el entorno → debe aparecer (.venv) al principio de la línea
.venv\Scripts\activate.bat
```
```cmd
:: 5. Instalar las librerías (tarda un par de minutos)
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e ".[test]"
```

> En CMD, las líneas que empiezan por `::` son explicaciones (como `#` en las otras terminales).

➡️ Ahora ve al [paso 3](#3-poner-tu-clave-de-inteligencia-artificial-solo-una-vez).

---

### Opción C: Git Bash

⚠️ Recuerda: en Git Bash se pega con `Shift + Insert` o clic derecho → *Paste*.

```bash
# 1. Crear la carpeta Proyectos y entrar en ella
mkdir -p ~/Proyectos
cd ~/Proyectos
```
```bash
# 2. Descargar el proyecto y entrar en su carpeta
git clone https://github.com/webcartaonline/Joselito.git
cd Joselito
```
```bash
# 3. Crear el entorno virtual (la "caja")
py -m venv .venv
```
```bash
# 4. Activar el entorno → debe aparecer (.venv) encima o al principio de la línea
source .venv/Scripts/activate
```
```bash
# 5. Instalar las librerías (tarda un par de minutos)
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e ".[test]"
```

➡️ Ahora ve al [paso 3](#3-poner-tu-clave-de-inteligencia-artificial-solo-una-vez).

---

## 3. Poner tu clave de inteligencia artificial (solo una vez)

Joselito usa una inteligencia artificial de **Hugging Face**. Para usarla necesita una **clave** (token), que es como una contraseña.

### 3.1 Conseguir la clave

1. Entra en https://huggingface.co y crea una cuenta (o inicia sesión).
2. Arriba a la derecha, pulsa en tu foto → **Settings** → **Access Tokens**.
3. Pulsa **Create new token**.
4. Ponle un nombre (por ejemplo `joselito`) y **marca el permiso "Make calls to Inference Providers"**.
5. Pulsa **Create token** y **copia** el texto que aparece (empieza por `hf_`).
   ⚠️ Solo se muestra una vez. Si lo pierdes, tendrás que crear otro.

### 3.2 Guardar la clave en el proyecto

Sigue en la **misma terminal** que antes (dentro de la carpeta `Joselito`).

**1) Crea el archivo `.env`, copiando el de ejemplo:**

| Terminal | Comando |
|---|---|
| PowerShell | `Copy-Item .env.example .env` |
| CMD | `copy .env.example .env` |
| Git Bash | `cp .env.example .env` |

**2) Ábrelo con el Bloc de notas** (este comando es igual en las 3 terminales):

```
notepad .env
```

**3) Cambia esta línea:**
```
HF_TOKEN=your_token_here
```
por tu clave real, **sin espacios ni comillas**. Por ejemplo:
```
HF_TOKEN=hf_AbCdEf123456
```

**4) Guarda** con `Ctrl + S` y cierra el Bloc de notas.

> 🔒 El archivo `.env` **nunca se sube a GitHub**. No compartas tu clave con nadie.

---

## 4. Usar Joselito

Con el entorno **activado** (ves `(.venv)`) y dentro de la carpeta `Joselito`, el comando es igual en las 3 terminales:

```
python cli.py
```

Joselito te irá haciendo preguntas: qué tema buscar, a qué idioma traducir y si quieres guardar el resultado.

**Otros comandos útiles:**

| Qué quieres hacer | Comando |
|---|---|
| Buscar un tema directamente, sin preguntas | `python cli.py --tema "Python" --idioma inglés` |
| Ver la ayuda | `python cli.py --help` |
| Pasar los tests (comprobar que todo funciona) | `pytest` |
| Salir del entorno virtual ("cerrar la caja") | `deactivate` |

📁 Los archivos que exportes (PDF o TXT) se guardan en la carpeta **`output`**, dentro del proyecto.

---

## 5. Abrir el proyecto otro día

La instalación **solo se hace una vez**. Los demás días solo tienes que hacer 2 cosas:

1. **Ir a la carpeta** del proyecto.
2. **Activar el entorno** (abrir la caja).

### PowerShell
```powershell
cd $HOME\Proyectos\Joselito
.\.venv\Scripts\Activate.ps1
python cli.py
```

### CMD
```cmd
cd /d "%USERPROFILE%\Proyectos\Joselito"
.venv\Scripts\activate.bat
python cli.py
```

### Git Bash
```bash
cd ~/Proyectos/Joselito
source .venv/Scripts/activate
python cli.py
```

### Para traer los últimos cambios del equipo

Con el entorno activado, dentro de la carpeta del proyecto:

```
git pull
pip install -r requirements.txt
pip install -e ".[test]"
```

*(Las dos últimas líneas solo instalan las librerías nuevas, si las hay. Si no hay nada nuevo, no pasa nada.)*

---

## 6. Abrirlo con Visual Studio Code

### La primera vez

1. **Abre el proyecto.** Desde cualquier terminal, escribe:
   - PowerShell: `code $HOME\Proyectos\Joselito`
   - CMD: `code "%USERPROFILE%\Proyectos\Joselito"`
   - Git Bash: `code ~/Proyectos/Joselito`

   *(O abre VS Code y ve a **Archivo → Abrir carpeta…** → elige `Proyectos\Joselito`.)*
2. Si pregunta **"¿Confía en los autores de los archivos de esta carpeta?"**, pulsa **Sí, confío en los autores**.
3. **Instala la extensión de Python.** Pulsa `Ctrl + Shift + X`, busca **Python** (la de Microsoft) y pulsa **Instalar**.
4. **Elige el entorno del proyecto.** Pulsa `Ctrl + Shift + P`, escribe `Python: Select Interpreter` y pulsa Enter. Elige la opción que ponga **`.venv`**.
5. **Abre la terminal de VS Code:** menú **Terminal → Nueva terminal** (o `Ctrl + ñ`). Aparecerá abajo y debería salir `(.venv)` solo.
6. Escribe `python cli.py`.

> Si `(.venv)` no aparece, cierra esa terminal (icono de la papelera 🗑️) y abre una nueva.

### Los demás días

Abre VS Code. Normalmente se abre solo con el último proyecto. Si no, ve a **Archivo → Abrir reciente → Joselito**. Abre una terminal y escribe `python cli.py`.

---

## 7. Abrirlo con PyCharm

### La primera vez

1. Abre **PyCharm** (desde el icono del escritorio).
2. Pulsa **Open** (Abrir) y elige la carpeta `C:\Users\<TuUsuario>\Proyectos\Joselito`. Pulsa **OK**.
3. Si pregunta **"Trust project?"**, pulsa **Trust Project**.
4. **Elige el entorno del proyecto:**
   1. Ve a **File → Settings** (o pulsa `Ctrl + Alt + S`).
   2. En el menú de la izquierda: **Project: Joselito → Python Interpreter**.
   3. Pulsa **Add Interpreter → Add Local Interpreter**.
   4. Elige **Select existing** (usar uno existente).
   5. En la ruta, pon: `C:\Users\<TuUsuario>\Proyectos\Joselito\.venv\Scripts\python.exe` (o búscala con el botón de la carpeta 📁).
   6. Pulsa **OK** y luego **OK** otra vez.

   *(Los nombres de los botones pueden cambiar un poco según la versión de PyCharm.)*
5. **Abre la terminal de PyCharm:** pulsa `Alt + F12` (o menú **View → Tool Windows → Terminal**). Debería salir `(.venv)`.
6. Escribe `python cli.py`.

### Los demás días

Abre PyCharm. Aparecerá **Joselito** en la lista de proyectos recientes: haz clic en él. Abre la terminal (`Alt + F12`) y escribe `python cli.py`.

---

## 8. Atajo opcional: escribir `wiki` y listo

Esto es **opcional**. Sirve para que, en vez de escribir la ruta y el comando de activar, solo escribas `wiki` desde cualquier sitio. Haz solo el apartado de la terminal (o terminales) que uses.

### PowerShell

Pega esto **una sola vez**:

```powershell
if (!(Test-Path $PROFILE)) { New-Item -ItemType File -Path $PROFILE -Force | Out-Null }
Add-Content -Path $PROFILE -Value 'function wiki { Set-Location "$HOME\Proyectos\Joselito"; .\.venv\Scripts\Activate.ps1 }'
```

Cierra PowerShell, ábrelo otra vez y escribe `wiki`.

### Git Bash

Pega esto **una sola vez**:

```bash
echo 'alias wiki="cd ~/Proyectos/Joselito && source .venv/Scripts/activate"' >> ~/.bashrc
```

Cierra Git Bash, ábrelo otra vez y escribe `wiki`.
*(Si la primera vez sale un aviso `WARNING: Found ~/.bashrc but no ~/.bash_profile`, es normal: Git Bash lo arregla solo.)*

### CMD

**1) Crea una carpeta para atajos y abre un archivo nuevo** (en CMD):

```cmd
mkdir "%USERPROFILE%\atajos"
notepad "%USERPROFILE%\atajos\wiki.bat"
```

Si el Bloc de notas pregunta *"¿Desea crear un nuevo archivo?"*, pulsa **Sí**.

**2) Pega esto en el Bloc de notas**, guarda (`Ctrl + S`) y ciérralo:

```
@echo off
cd /d "%USERPROFILE%\Proyectos\Joselito"
call .venv\Scripts\activate.bat
```

**3) Dile a Windows dónde está el atajo.** Este paso se hace en **PowerShell**, no en CMD. Pega esto una sola vez:

```powershell
[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path","User") + ";$env:USERPROFILE\atajos", "User")
```

Cierra CMD, ábrelo otra vez y escribe `wiki`.

### Después del atajo

En cualquiera de las tres terminales:

```
wiki
python cli.py
```

---

## 9. Si algo falla

| Mensaje o problema | Qué significa | Solución |
|---|---|---|
| `... no se reconoce como nombre de un cmdlet` / `no se reconoce como un comando interno` | La terminal no encuentra ese programa. | Cierra y vuelve a abrir la terminal. Si sigue igual, reinicia el ordenador. Si aun así falla, vuelve a instalar ese programa (paso 1). |
| Al escribir `python` se abre la Microsoft Store | Windows tiene un "falso" Python que lleva a la tienda. | Usa `py` en vez de `python` **para crear el entorno**. Una vez activado (ves `(.venv)`), `python` ya funciona. |
| Error rojo al activar en PowerShell: `la ejecución de scripts está deshabilitada` | PowerShell bloquea la activación por seguridad. | Ejecuta `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, responde `S` y vuelve a activar. |
| `ModuleNotFoundError: No module named ...` | El entorno no está activado, o faltan librerías. | Comprueba que ves `(.venv)`. Si no, actívalo (paso 5). Si sí lo ves, repite la instalación de librerías (paso 2, último bloque). |
| `fatal: destination path 'Joselito' already exists` | Ya descargaste el proyecto antes. | No hace falta volver a descargarlo. Entra con `cd Joselito` y sigue. |
| `Repository not found` o pide contraseña al descargar | No tienes acceso al repositorio. | Pide al dueño del proyecto que te dé acceso en GitHub e inicia sesión con esa cuenta. |
| Joselito dice que no ha podido enriquecer el texto con IA | Falla la clave o la conexión. | Revisa que `.env` tiene tu `HF_TOKEN` bien copiado (paso 3), que tienes internet y que tu cuenta de Hugging Face tiene créditos. |
| En Git Bash no puedo pegar | `Ctrl + V` no funciona en Git Bash. | Usa `Shift + Insert` o clic derecho → *Paste*. |
| No aparece `(.venv)` | El entorno no está activado. | Ejecuta el comando de activar de tu terminal (paso 5). |

---

## Resumen ultrarrápido (para cuando ya lo tengas instalado)

| | PowerShell | CMD | Git Bash |
|---|---|---|---|
| Ir al proyecto | `cd $HOME\Proyectos\Joselito` | `cd /d "%USERPROFILE%\Proyectos\Joselito"` | `cd ~/Proyectos/Joselito` |
| Activar entorno | `.\.venv\Scripts\Activate.ps1` | `.venv\Scripts\activate.bat` | `source .venv/Scripts/activate` |
| Ejecutar | `python cli.py` | `python cli.py` | `python cli.py` |
| Tests | `pytest` | `pytest` | `pytest` |
| Salir del entorno | `deactivate` | `deactivate` | `deactivate` |
