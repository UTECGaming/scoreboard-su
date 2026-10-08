import json
import os
import sys
import time
import tkinter as tk
from tkinter import ttk, filedialog

from obswebsocket import obsws, requests

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

OBS_HOST = "localhost"
OBS_PORT = 4455
OBS_PASSWORD = "123456789"

if getattr(sys, "frozen", False):
    DIRECTORIO_BASE = os.path.dirname(os.path.abspath(sys.executable))
else:
    DIRECTORIO_BASE = os.path.dirname(os.path.abspath(__file__))

JSON_PATH = os.path.join(DIRECTORIO_BASE, "torneo_datos.json")
EQUIPOS_PATH = os.path.join(DIRECTORIO_BASE, "equipos.json")
LOGOS_DIR = os.path.join(DIRECTORIO_BASE, "logos")

SIN_EQUIPO = "— Elegir equipo —"

TAMANO_FUENTE_JUGADORES_A = 300
TAMANO_FUENTE_JUGADORES_B = 300

# La distribución se define sobre un lienzo 16:9 de referencia; en otra
# resolución 16:9 (p. ej. 1280x720 o 3840x2160) todo se escala en proporción.
LIENZO_REFERENCIA = (1920, 1080)

# Medidas en píxeles del lienzo de referencia.
ALTURA_FILA = 150                # altura de logos, listas y puntajes
ANCHO_MAX_LISTA = 300            # ancho máximo de cada lista de jugadores
MARGEN = 50                      # distancia a todos los bordes del lienzo
SEPARACION_LOGO_LISTA = 40
SEPARACION_LISTA_PUNTAJE = 40   # mínima; si no se cumple, se avisa
SEPARACION_PUNTAJES = 120       # hueco entre los dos puntajes, en el centro

ESPERA_BBOX_OBS = 0.5

DEBUG_LAYOUT = True

TAMANO_PREVIEW_LOGO = 140

COLOR_FONDO = "#15171c"
COLOR_PANEL = "#1f232b"
COLOR_TEXTO = "#f2f2f2"
COLOR_TEXTO_SUAVE = "#8a93a3"
COLOR_EQUIPO_A = "#2f80ed"
COLOR_EQUIPO_B = "#eb5757"
COLOR_PUNTAJE = "#ffd166"


def tamano_fuente_jugadores(tamano_base, cantidad):
    if cantidad <= 1:
        return tamano_base

    return max(1, round(tamano_base / cantidad))


ALIGN_CENTRO = 0
ALIGN_IZQUIERDA = 1
ALIGN_DERECHA = 2
ALIGN_ARRIBA = 4
ALIGN_ABAJO = 8


FUENTES_ESCENA = (
    "Logo Equipo A",
    "Logo Equipo B",
    "Lista de Jugadores A",
    "Lista de Jugadores B",
    "Puntaje Equipo A",
    "Puntaje Equipo B"
)

# Deshace cualquier rotación o recorte hecho a mano en OBS.
TRANSFORM_NEUTRO = {
    "rotation": 0,
    "cropLeft": 0,
    "cropRight": 0,
    "cropTop": 0,
    "cropBottom": 0
}


def aplicar_transform(ws, escena, item_id, cambios, nombre):
    respuesta = ws.call(
        requests.SetSceneItemTransform(
            sceneName=escena,
            sceneItemId=item_id,
            sceneItemTransform=cambios
        )
    )
    if not respuesta.status:
        raise RuntimeError(
            f"OBS rechazó el transform de '{nombre}': {respuesta.datain}"
        )


def leer_transform_estable(
    ws,
    escena,
    item_id,
    intentos=30,
    pausa=0.1,
    lecturas_estables=3
):
    anterior = None
    estables = 0
    transformacion = None

    for i in range(intentos):
        transformacion = ws.call(
            requests.GetSceneItemTransform(
                sceneName=escena,
                sceneItemId=item_id
            )
        ).getSceneItemTransform()

        actual = tuple(
            transformacion.get(campo)
            for campo in (
                "width",
                "height",
                "sourceWidth",
                "sourceHeight",
                "boundsType",
                "boundsWidth",
                "boundsHeight"
            )
        )

        if actual == anterior:
            estables += 1

            if estables >= lecturas_estables - 1:
                return transformacion, i + 1

        else:
            estables = 0

        anterior = actual

        time.sleep(pausa)

    return transformacion, intentos


def escala_texto(ws, escena, item_id, altura):
    # Devuelve la escala que deja el texto en `altura` px y el ancho resultante.
    transformacion, _ = leer_transform_estable(ws, escena, item_id)
    alto_fuente = transformacion.get("sourceHeight", 0)
    ancho_fuente = transformacion.get("sourceWidth", 0)

    if alto_fuente <= 0:
        return 1, 0

    escala = altura / alto_fuente
    return escala, ancho_fuente * escala


def organizar_escena_activa(ws):
    """Distribuye la fila superior desde cero, sin importar dónde estén
    los objetos:

    |M|Logo A|S|Lista A| ... |Puntaje A|centro|Puntaje B| ... |Lista B|S|Logo B|M|

    Devuelve una lista de avisos (vacía si todo cabe).
    """
    nombre_escena = ws.call(
        requests.GetCurrentProgramScene()
    ).getCurrentProgramSceneName()

    elementos = ws.call(
        requests.GetSceneItemList(sceneName=nombre_escena)
    ).getSceneItems()

    ids = {
        elemento["sourceName"]: elemento["sceneItemId"]
        for elemento in elementos
    }

    faltantes = [nombre for nombre in FUENTES_ESCENA if nombre not in ids]

    if faltantes:
        raise ValueError(
            f"Fuentes no encontradas en la escena activa "
            f"'{nombre_escena}': "
            + ", ".join(faltantes)
        )

    video = ws.call(requests.GetVideoSettings())
    ancho_lienzo = video.getBaseWidth()
    alto_lienzo = video.getBaseHeight()

    avisos = []

    # Las posiciones siempre son en píxeles del lienzo; la salida solo
    # reescala el lienzo completo, pero si no es 16:9 lo deforma.
    ancho_salida = video.getOutputWidth()
    alto_salida = video.getOutputHeight()

    for etiqueta, ancho, alto in (
        ("lienzo", ancho_lienzo, alto_lienzo),
        ("salida", ancho_salida, alto_salida)
    ):
        if ancho * 9 != alto * 16:
            avisos.append(f"La resolución de {etiqueta} {ancho}x{alto} no es 16:9.")

    factor = alto_lienzo / LIENZO_REFERENCIA[1]
    altura = ALTURA_FILA * factor
    margen = MARGEN * factor
    sep_logo = SEPARACION_LOGO_LISTA * factor
    sep_puntaje = SEPARACION_LISTA_PUNTAJE * factor
    sep_centro = SEPARACION_PUNTAJES * factor
    ancho_max_lista = ANCHO_MAX_LISTA * factor
    centro_y = margen + altura / 2

    if altura + 2 * margen > alto_lienzo:
        avisos.append("La fila no cabe en la altura del lienzo.")

    # Los logos usan una caja fija: su tamaño no depende de la imagen,
    # así que no hace falta esperar a que OBS la cargue para medirla.
    caja_logo = {
        **TRANSFORM_NEUTRO,
        "positionY": centro_y,
        "scaleX": 1,
        "scaleY": 1,
        "boundsType": "OBS_BOUNDS_SCALE_INNER",
        "boundsWidth": altura,
        "boundsHeight": altura,
        "boundsAlignment": ALIGN_CENTRO
    }

    escalas = {}
    anchos = {}

    for nombre in FUENTES_ESCENA:
        if nombre.startswith("Logo"):
            continue

        escalas[nombre], anchos[nombre] = escala_texto(
            ws, nombre_escena, ids[nombre], altura
        )

        # Una lista demasiado ancha se reduce entera (sin deformarla) hasta
        # caber; queda más baja que la fila pero igual de centrada.
        if nombre.startswith("Lista") and anchos[nombre] > ancho_max_lista:
            escalas[nombre] *= ancho_max_lista / anchos[nombre]
            anchos[nombre] = ancho_max_lista

    x_lista_a = margen + altura + sep_logo
    x_lista_b = ancho_lienzo - margen - altura - sep_logo

    # Los puntajes van pegados al centro del lienzo, uno a cada lado.
    centro_x = ancho_lienzo / 2
    x_puntaje_a = centro_x - sep_centro / 2
    x_puntaje_b = centro_x + sep_centro / 2

    # Hueco más chico entre una lista y su puntaje, descontando la
    # separación mínima; si es negativo, se están tocando.
    sobrante = min(
        (x_puntaje_a - anchos["Puntaje Equipo A"])
        - (x_lista_a + anchos["Lista de Jugadores A"]),
        (x_lista_b - anchos["Lista de Jugadores B"])
        - (x_puntaje_b + anchos["Puntaje Equipo B"])
    ) - sep_puntaje

    if sobrante < 0:
        avisos.append(
            f"No cabe todo en el ancho: una lista se acerca de más "
            f"a su puntaje ({-sobrante:.0f}px)."
        )

    posiciones = {
        "Logo Equipo A": (margen, ALIGN_IZQUIERDA),
        "Logo Equipo B": (ancho_lienzo - margen, ALIGN_DERECHA),
        "Lista de Jugadores A": (x_lista_a, ALIGN_IZQUIERDA),
        "Lista de Jugadores B": (x_lista_b, ALIGN_DERECHA),
        "Puntaje Equipo A": (x_puntaje_a, ALIGN_DERECHA),
        "Puntaje Equipo B": (x_puntaje_b, ALIGN_IZQUIERDA)
    }

    for nombre, (x, alineacion) in posiciones.items():
        if nombre.startswith("Logo"):
            cambios = {**caja_logo, "positionX": x, "alignment": alineacion}
        else:
            cambios = {
                **TRANSFORM_NEUTRO,
                "positionX": x,
                "positionY": centro_y,
                "alignment": alineacion,
                "scaleX": escalas[nombre],
                "scaleY": escalas[nombre],
                "boundsType": "OBS_BOUNDS_NONE"
            }

        aplicar_transform(ws, nombre_escena, ids[nombre], cambios, nombre)

    if DEBUG_LAYOUT:
        print(
            f"\n[LAYOUT] lienzo={ancho_lienzo}x{alto_lienzo} "
            f"salida={ancho_salida}x{alto_salida} "
            f"factor={factor:.3f} altura={altura:.1f} margen={margen:.1f}"
        )
        for nombre, (x, _) in posiciones.items():
            ancho = altura if nombre.startswith("Logo") else anchos[nombre]
            print(f"  {nombre}: x={x:.1f} ancho={ancho:.1f}")
        print(f"  Espacio libre lista-puntaje: {sobrante:.1f}px")

    return avisos


def enviar_a_obs(datos):
    ws = None

    try:
        ws = obsws(
            OBS_HOST,
            OBS_PORT,
            OBS_PASSWORD
        )

        ws.connect()

        jugadores_a = [
            jugador
            for jugador in datos["jugadoresA"]
            if jugador
        ]

        jugadores_b = [
            jugador
            for jugador in datos["jugadoresB"]
            if jugador
        ]

        texto_jugadores_a = "\n".join(
            jugadores_a
        )

        texto_jugadores_b = "\n".join(
            jugadores_b
        )

        cantidad_jugadores_a = len(
            jugadores_a
        )

        cantidad_jugadores_b = len(
            jugadores_b
        )

        text_map = {
            "Puntaje Equipo A": str(
                datos["puntajeA"]
            ),

            "Puntaje Equipo B": str(
                datos["puntajeB"]
            )
        }

        errores = []

        for source_name, text_value in text_map.items():
            try:
                # Se conserva la tipografía elegida en OBS; solo se fija el
                # tamaño para que al escalar a la altura de la fila no se vea
                # borroso.
                fuente = dict(
                    ws.call(
                        requests.GetInputSettings(inputName=source_name)
                    ).getInputSettings().get("font", {})
                )
                fuente["size"] = ALTURA_FILA

                ws.call(
                    requests.SetInputSettings(
                        inputName=source_name,
                        inputSettings={
                            "text": text_value,
                            "font": fuente
                        }
                    )
                )

            except Exception as e:
                errores.append(
                    f"{source_name}: {e}"
                )

        fuentes_jugadores = {

            "Lista de Jugadores A": (
                texto_jugadores_a,
                cantidad_jugadores_a,
                "tamanoFuenteJugadoresA",
                TAMANO_FUENTE_JUGADORES_A,
                "left"
            ),

            "Lista de Jugadores B": (
                texto_jugadores_b,
                cantidad_jugadores_b,
                "tamanoFuenteJugadoresB",
                TAMANO_FUENTE_JUGADORES_B,
                "right"
            )
        }

        for (
            source_name,
            (
                texto,
                cantidad,
                key,
                tamano_predefinido,
                alineacion
            )
        ) in fuentes_jugadores.items():
            try:
                tamano_base = datos.get(
                    key,
                    tamano_predefinido
                )

                if (
                    not isinstance(
                        tamano_base,
                        (int, float)
                    )
                    or tamano_base <= 0
                ):
                    tamano_base = tamano_predefinido

                datos[key] = int(
                    tamano_base
                )

                tamano = tamano_fuente_jugadores(
                    tamano_base,
                    cantidad
                )

                ws.call(
                    requests.SetInputSettings(
                        inputName=source_name,

                        inputSettings={
                            "text": texto,

                            "font": {
                                "face": "Bebas Neue",
                                "size": tamano
                            },

                            "align": alineacion,

                            "custom_width": 0,
                            "custom_height": 0
                        },

                        overlay=True
                    )
                )

            except Exception as e:
                errores.append(
                    f"{source_name}: {e}"
                )

        image_map = {

            "Logo Equipo A":
                datos["logoA"],

            "Logo Equipo B":
                datos["logoB"]
        }

        for (
            source_name,
            file_path
        ) in image_map.items():
            if not file_path:
                continue

            if not os.path.exists(file_path):
                errores.append(
                    f"{source_name}: "
                    f"no existe el archivo "
                    f"'{file_path}'"
                )

                continue

            try:
                ws.call(
                    requests.SetInputSettings(
                        inputName=source_name,

                        inputSettings={
                            "file": file_path
                        }
                    )
                )

            except Exception as e:
                errores.append(
                    f"{source_name}: {e}"
                )

        time.sleep(ESPERA_BBOX_OBS)

        avisos = []

        try:
            avisos = organizar_escena_activa(
                ws
            )

        except Exception as e:
            errores.append(
                f"Distribución automática: {e}"
            )

        if errores:
            return (
                False,
                "No se pudieron actualizar "
                "algunas fuentes:\n"
                + "\n".join(errores + avisos)
            )

        return (
            True,
            "¡Objetos de OBS actualizados!"
            + "".join(f"\nAviso: {aviso}" for aviso in avisos)
        )

    except Exception as e:
        return (
            False,
            f"Error al conectar con OBS: {e}"
        )

    finally:
        if ws is not None:
            try:
                ws.disconnect()

            except Exception:
                pass


def guardar_y_actualizar():
    jugadores_a = [
        entry.get().strip()
        for entry in entries_j_a
    ]

    jugadores_b = [
        entry.get().strip()
        for entry in entries_j_b
    ]

    datos = {

        "equipoA":
            nombre_equipo("A"),

        "equipoB":
            nombre_equipo("B"),

        "logoA":
            rutas_logo["A"],

        "logoB":
            rutas_logo["B"],

        "puntajeA":
            entry_score_a.get(),

        "puntajeB":
            entry_score_b.get(),

        "jugadoresA":
            jugadores_a,

        "jugadoresB":
            jugadores_b
    }

    exito, mensaje = enviar_a_obs(
        datos
    )

    try:
        with open(
            JSON_PATH,
            "w",
            encoding="utf-8"
        ) as archivo:
            json.dump(
                datos,
                archivo,
                indent=2,
                ensure_ascii=False
            )

    except Exception as e:
        print(
            f"Error al guardar JSON: {e}"
        )

    color = (
        "#28a745"
        if exito
        else "#dc3545"
    )

    lbl_status.config(
        text=mensaje,
        fg=color
    )


def cambiar_logo(source_name, clave_json, file_path):
    ws = None

    try:
        ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
        ws.connect()

        respuesta = ws.call(
            requests.SetInputSettings(
                inputName=source_name,
                inputSettings={"file": file_path}
            )
        )

        if not respuesta.status:
            raise RuntimeError(respuesta.datain)

        avisos = organizar_escena_activa(ws)

        exito, mensaje = True, f"{source_name} actualizado." + "".join(
            f"\nAviso: {aviso}" for aviso in avisos
        )

    except Exception as e:
        exito, mensaje = False, f"No se pudo cambiar {source_name}: {e}"

    finally:
        if ws is not None:
            try:
                ws.disconnect()
            except Exception:
                pass

    if exito:
        try:
            datos = {}
            if os.path.exists(JSON_PATH):
                with open(JSON_PATH, "r", encoding="utf-8") as archivo:
                    datos = json.load(archivo)

            datos[clave_json] = file_path

            with open(JSON_PATH, "w", encoding="utf-8") as archivo:
                json.dump(datos, archivo, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"Error al guardar JSON: {e}")

    lbl_status.config(
        text=mensaje,
        fg="#28a745" if exito else "#dc3545"
    )


def cargar_preview_logo(file_path, tamano=TAMANO_PREVIEW_LOGO):
    if not file_path or not os.path.exists(file_path):
        return None

    try:
        if Image is not None:
            imagen = Image.open(file_path)
            imagen.thumbnail((tamano, tamano))
            return ImageTk.PhotoImage(imagen)

        # Sin Pillow, tkinter solo abre PNG/GIF y únicamente reduce por factor entero.
        imagen = tk.PhotoImage(file=file_path)
        factor = max(1, -(-max(imagen.width(), imagen.height()) // tamano))
        return imagen.subsample(factor)

    except Exception:
        return None


def mostrar_logo(lado):
    etiqueta = labels_logo[lado]
    ruta = rutas_logo[lado]
    imagen = cargar_preview_logo(ruta)

    if imagen is not None:
        etiqueta.config(image=imagen, text="")
    elif ruta and not os.path.exists(ruta):
        etiqueta.config(
            image="",
            text=f"No se encontró\n{os.path.basename(ruta)}"
        )
    elif ruta:
        etiqueta.config(image="", text="Vista previa\nno disponible")
    else:
        etiqueta.config(image="", text="Sin logo")

    # tkinter libera la imagen si nadie guarda una referencia.
    etiqueta.image = imagen


def buscar_logo(lado):
    filename = filedialog.askopenfilename(
        title="Seleccionar Logo",
        filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.webp")]
    )

    if not filename:
        return

    rutas_logo[lado] = filename
    mostrar_logo(lado)
    cambiar_logo(f"Logo Equipo {lado}", f"logo{lado}", filename)


def cargar_equipos():
    if not os.path.exists(EQUIPOS_PATH):
        return {}

    try:
        with open(EQUIPOS_PATH, "r", encoding="utf-8") as archivo:
            return json.load(archivo)
    except Exception as e:
        print(f"Error al leer {EQUIPOS_PATH}: {e}")
        return {}


def ruta_logo_equipo(nombre):
    # "EL-MT" -> logos/elmt.png
    archivo = nombre.lower().replace("-", "").replace(" ", "") + ".png"
    return os.path.join(LOGOS_DIR, archivo)


def nombre_equipo(lado):
    nombre = equipo_seleccionado[lado].get()
    return "" if nombre == SIN_EQUIPO else nombre


def seleccionar_equipo(lado, nombre):
    equipo = equipos.get(nombre)
    if equipo is None:
        return

    equipo_seleccionado[lado].set(nombre)

    jugadores = equipo.get("jugadores", [])
    entries = entries_j_a if lado == "A" else entries_j_b

    for i, entry in enumerate(entries):
        entry.delete(0, tk.END)
        entry.insert(0, jugadores[i] if i < len(jugadores) else "")

    rutas_logo[lado] = equipo.get("logo") or ruta_logo_equipo(nombre)
    mostrar_logo(lado)

    guardar_y_actualizar()


def cambiar_score(entry_target, delta=None, valor=None):
    if valor is None:
        try:
            valor = int(entry_target.get())
        except ValueError:
            valor = 0

        valor = max(0, valor + delta)

    entry_target.delete(0, tk.END)
    entry_target.insert(0, str(valor))

    guardar_y_actualizar()


def boton(padre, texto, comando, color=COLOR_PANEL, **opciones):
    return tk.Button(
        padre,
        text=texto,
        command=comando,
        bg=color,
        fg=COLOR_TEXTO,
        activebackground=color,
        activeforeground=COLOR_TEXTO,
        relief="flat",
        cursor="hand2",
        font=("Arial", 10, "bold"),
        **opciones
    )


def crear_panel_logo(padre, lado, color):
    panel = tk.Frame(padre, bg=COLOR_FONDO)

    tk.Label(
        panel,
        text=f"EQUIPO {lado}",
        bg=COLOR_FONDO,
        fg=COLOR_TEXTO_SUAVE,
        font=("Arial", 8, "bold")
    ).pack()

    selector = tk.OptionMenu(
        panel,
        equipo_seleccionado[lado],
        *(list(equipos) or [SIN_EQUIPO]),
        command=lambda nombre: seleccionar_equipo(lado, nombre)
    )
    selector.config(
        bg=COLOR_PANEL,
        fg=color,
        activebackground=COLOR_PANEL,
        activeforeground=color,
        relief="flat",
        highlightthickness=0,
        cursor="hand2",
        font=("Arial", 12, "bold")
    )
    selector["menu"].config(
        bg=COLOR_PANEL,
        fg=COLOR_TEXTO,
        activebackground=color,
        font=("Arial", 11)
    )
    selector.pack(fill="x", pady=(2, 6))

    marco = tk.Frame(
        panel,
        width=TAMANO_PREVIEW_LOGO + 12,
        height=TAMANO_PREVIEW_LOGO + 12,
        bg=COLOR_PANEL,
        highlightthickness=2,
        highlightbackground=color
    )
    marco.pack_propagate(False)
    marco.pack()

    etiqueta = tk.Label(
        marco,
        bg=COLOR_PANEL,
        fg=COLOR_TEXTO_SUAVE,
        font=("Arial", 9)
    )
    etiqueta.pack(expand=True, fill="both")
    labels_logo[lado] = etiqueta

    boton(
        panel,
        "Cambiar logo",
        lambda: buscar_logo(lado),
        padx=10,
        pady=3
    ).pack(pady=(8, 0), fill="x")

    return panel


def crear_lista_jugadores(padre, lado, iniciales, color):
    panel = tk.Frame(padre, bg=COLOR_FONDO)
    justificacion = "right" if lado == "A" else "left"
    lado_etiqueta = "e" if lado == "A" else "w"

    tk.Label(
        panel,
        text="JUGADORES",
        bg=COLOR_FONDO,
        fg=COLOR_TEXTO_SUAVE,
        font=("Arial", 9, "bold")
    ).grid(row=0, column=0, columnspan=3, sticky=lado_etiqueta, pady=(0, 4))

    entries = []

    def limpiar(entry):
        entry.delete(0, tk.END)
        entry.focus_set()

    for i in range(5):
        numero = tk.Label(
            panel,
            text=str(i + 1),
            bg=COLOR_FONDO,
            fg=color,
            font=("Arial", 10, "bold"),
            width=2
        )

        entry = tk.Entry(
            panel,
            width=22,
            justify=justificacion,
            bg=COLOR_PANEL,
            fg=COLOR_TEXTO,
            insertbackground=COLOR_TEXTO,
            relief="flat",
            font=("Arial", 11)
        )
        entry.insert(0, iniciales[i] if i < len(iniciales) else "")

        borrar = boton(panel, "✕", lambda e=entry: limpiar(e), width=2)

        # El número de jugador queda siempre del lado exterior del marcador
        # y el botón de borrar del lado interior.
        if lado == "A":
            numero.grid(row=i + 1, column=0, padx=(0, 4))
            entry.grid(row=i + 1, column=1, pady=3, ipady=3)
            borrar.grid(row=i + 1, column=2, padx=(4, 0))
        else:
            borrar.grid(row=i + 1, column=0, padx=(0, 4))
            entry.grid(row=i + 1, column=1, pady=3, ipady=3)
            numero.grid(row=i + 1, column=2, padx=(4, 0))

        entries.append(entry)

    boton(
        panel,
        "Limpiar todos",
        lambda: [entry.delete(0, tk.END) for entry in entries]
    ).grid(row=6, column=0, columnspan=3, sticky="ew", pady=(6, 0))

    return panel, entries


def crear_columna_puntaje(padre, valor_inicial, color):
    columna = tk.Frame(padre, bg=COLOR_FONDO)

    entry = tk.Entry(
        columna,
        width=3,
        justify="center",
        bg=COLOR_FONDO,
        fg=COLOR_PUNTAJE,
        insertbackground=COLOR_PUNTAJE,
        relief="flat",
        highlightthickness=0,
        font=("Arial", 56, "bold")
    )
    entry.insert(0, valor_inicial)
    entry.bind("<Return>", lambda _evento: guardar_y_actualizar())
    entry.pack()

    tk.Frame(columna, height=4, bg=color).pack(fill="x", pady=(0, 8))

    botones = tk.Frame(columna, bg=COLOR_FONDO)
    botones.pack()

    boton(
        botones, "−1", lambda: cambiar_score(entry, -1), width=4
    ).pack(side="left", padx=2)
    boton(
        botones, "+1", lambda: cambiar_score(entry, 1), color=color, width=4
    ).pack(side="left", padx=2)

    boton(
        columna, "↺ Reiniciar", lambda: cambiar_score(entry, valor=0)
    ).pack(fill="x", padx=2, pady=(4, 0))

    return columna, entry


root = tk.Tk()
root.title("Panel de Control de Torneo - OBS")
root.configure(bg=COLOR_FONDO)
root.resizable(False, False)

datos_init = {
    "logoA": "",
    "logoB": "",
    "puntajeA": "0",
    "puntajeB": "0",
    "jugadoresA": [""] * 5,
    "jugadoresB": [""] * 5
}

if os.path.exists(JSON_PATH):
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as archivo:
            datos_init = json.load(archivo)
    except Exception:
        pass

rutas_logo = {
    "A": datos_init.get("logoA", ""),
    "B": datos_init.get("logoB", "")
}
labels_logo = {}

equipos = cargar_equipos()
equipo_seleccionado = {
    lado: tk.StringVar(
        root,
        value=datos_init.get(f"equipo{lado}") or SIN_EQUIPO
    )
    for lado in ("A", "B")
}

marcador = tk.Frame(root, bg=COLOR_FONDO, padx=20, pady=20)
marcador.pack(fill="both", expand=True)

panel_logo_a = crear_panel_logo(marcador, "A", COLOR_EQUIPO_A)
panel_jugadores_a, entries_j_a = crear_lista_jugadores(
    marcador, "A", datos_init.get("jugadoresA", [""] * 5), COLOR_EQUIPO_A
)

panel_puntaje = tk.Frame(marcador, bg=COLOR_FONDO)
columna_a, entry_score_a = crear_columna_puntaje(
    panel_puntaje, str(datos_init.get("puntajeA", "0")), COLOR_EQUIPO_A
)
columna_b, entry_score_b = crear_columna_puntaje(
    panel_puntaje, str(datos_init.get("puntajeB", "0")), COLOR_EQUIPO_B
)

columna_a.grid(row=0, column=0, sticky="n")
tk.Label(
    panel_puntaje,
    text=":",
    bg=COLOR_FONDO,
    fg=COLOR_TEXTO_SUAVE,
    font=("Arial", 48, "bold")
).grid(row=0, column=1, sticky="n", padx=6)
columna_b.grid(row=0, column=2, sticky="n")

panel_jugadores_b, entries_j_b = crear_lista_jugadores(
    marcador, "B", datos_init.get("jugadoresB", [""] * 5), COLOR_EQUIPO_B
)
panel_logo_b = crear_panel_logo(marcador, "B", COLOR_EQUIPO_B)

for columna, panel in enumerate((
    panel_logo_a,
    panel_jugadores_a,
    panel_puntaje,
    panel_jugadores_b,
    panel_logo_b
)):
    panel.grid(row=0, column=columna, padx=14)

mostrar_logo("A")
mostrar_logo("B")

btn_actualizar = boton(
    root,
    "⚡ ACTUALIZAR OBS",
    guardar_y_actualizar,
    color="#007bff",
    height=2
)
btn_actualizar.config(font=("Arial", 11, "bold"))
btn_actualizar.pack(fill="x", padx=20, pady=(0, 5))

lbl_status = tk.Label(
    root,
    text="Listo.",
    bg=COLOR_FONDO,
    fg=COLOR_TEXTO_SUAVE,
    font=("Arial", 10, "italic")
)
lbl_status.pack(pady=(0, 10))

root.mainloop()
