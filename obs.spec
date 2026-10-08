# -*- mode: python ; coding: utf-8 -*-
#
# Compilar:  .\venv\Scripts\python.exe -m PyInstaller obs.spec --noconfirm
#
# El venv también tiene las dependencias de schedule_heatmap.py (numpy,
# matplotlib, pdfplumber...) y PyInstaller las arrastra por importaciones
# opcionales de Pillow y de la biblioteca estándar. Aquí se deja fuera todo
# lo que obs.py no usa.

import os

import PIL
from PyInstaller.utils.hooks import collect_submodules


# --- Módulos de Python ------------------------------------------------------

# websocket._wsdump es la herramienta de consola de websocket-client y lo
# único que importa ssl sin try/except; obs.py no lo usa.
hiddenimports = collect_submodules("obswebsocket") + [
    modulo
    for modulo in collect_submodules("websocket")
    if modulo != "websocket._wsdump"
]

# Formatos de imagen de los logos, los que Pillow carga siempre en preinit y
# los que JPEG necesita internamente (Tiff para EXIF, Mpo para fotos de
# cámara). Pillow ignora los plugins que no encuentra.
PLUGINS_PIL = {"Png", "Jpeg", "Mpo", "Tiff", "WebP", "Gif", "Bmp", "Ppm"}
carpeta_pil = os.path.dirname(PIL.__file__)
plugins_sobrantes = [
    f"PIL.{archivo[:-3]}"
    for archivo in os.listdir(carpeta_pil)
    if archivo.endswith("ImagePlugin.py")
    and archivo[:-len("ImagePlugin.py")] not in PLUGINS_PIL
]

excludes = [
    # Dependencias de schedule_heatmap.py, presentes en el mismo venv.
    "numpy", "matplotlib", "pdfplumber", "pdfminer", "pdf2image",
    "pytesseract", "fitz", "pymupdf", "pypdfium2", "cryptography", "cffi",
    "charset_normalizer", "contourpy", "kiwisolver", "fontTools", "dateutil",
    "pyparsing", "cycler", "six",

    # Partes de Pillow sin uso: AVIF (7,6 MB, va en plugins_sobrantes),
    # perfiles de color, fuentes, dibujo e integraciones con otros toolkits.
    # Los módulos pequeños que usan los plugins (ImageOps, ImageMath,
    # ImageChops...) se mantienen.
    "PIL._avif", "PIL.ImageCms", "PIL._imagingcms", "PIL.ImageFont",
    "PIL._imagingft", "PIL.ImageDraw", "PIL.ImageDraw2", "PIL.ImageMorph",
    "PIL._imagingmorph", "PIL.ImageQt", "PIL.ImageShow", "PIL.ImageGrab",
    "PIL.ImageWin", "PIL.FontFile", "PIL.BdfFontFile", "PIL.PcfFontFile",
    *plugins_sobrantes,

    # La conexión a OBS es ws:// en localhost: no hace falta TLS. hashlib
    # usa entonces sus implementaciones internas (sha1/sha256), suficientes
    # para el handshake y la contraseña de obs-websocket.
    "ssl", "_ssl", "_hashlib", "websocket._wsdump",

    # Biblioteca estándar que no usa la app.
    "unittest", "doctest", "pydoc", "pydoc_data", "pdb", "asyncio",
    "multiprocessing", "concurrent", "xmlrpc", "xml", "ftplib", "http.server",
    "http.cookiejar", "urllib.request", "email", "mailbox", "smtplib",
    "lzma", "_lzma", "bz2", "_bz2", "tarfile", "statistics", "sqlite3",
    "curses", "_pyrepl", "readline", "tkinter.tix", "tkinter.dnd", "turtle",
    "turtledemo", "idlelib", "lib2to3", "distutils", "setuptools",
    "pkg_resources",
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=2,
)


# --- Datos de Tcl/Tk --------------------------------------------------------

# Tkinter trae zonas horarias, traducciones del reloj, decenas de
# codificaciones y paquetes de Tcl que la ventana no usa. Solo se conservan
# las codificaciones que Tcl necesita en Windows.
CODIFICACIONES_TCL = {"ascii.enc", "cp1252.enc", "iso8859-1.enc", "utf-8.enc"}
CARPETAS_TCL_SOBRANTES = (
    "_tcl_data/tzdata/",
    "_tcl_data/msgs/",
    "_tcl_data/http1.0/",
    "_tcl_data/opt0.4/",
    "_tk_data/images/",
    "_tk_data/demos/",
    "tcl8/8.6/http-",
    "tcl8/8.5/tcltest-",
)


def dato_necesario(destino):
    destino = destino.replace("\\", "/")

    if destino.startswith(CARPETAS_TCL_SOBRANTES):
        return False

    if destino.startswith("_tcl_data/encoding/"):
        return os.path.basename(destino) in CODIFICACIONES_TCL

    # Listas de archivos de instalación de los paquetes; no se usan al ejecutar.
    return ".dist-info" not in destino


a.datas = [dato for dato in a.datas if dato_necesario(dato[0])]


pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="obs",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX no está instalado; además suele provocar falsos positivos del
    # antivirus con ejecutables de PyInstaller.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
