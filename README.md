# Panel de Control de Torneo para OBS

Aplicación de escritorio (Tkinter) que controla en vivo el marcador de un torneo en OBS Studio: logos, listas de jugadores y puntajes de dos equipos. Se conecta a OBS por WebSocket y, cada vez que se actualiza, **reorganiza la escena desde cero**. No importa dónde se hayan movido o escalado los objetos: siempre quedan con esta distribución en la parte superior del lienzo:

```
|M|[Logo A]|S|[Lista A] ...  [Puntaje A] centro [Puntaje B]  ... [Lista B]|S|[Logo B]|M|
```

---

## Estructura del proyecto

```
obs/
├── main.py                    # Código de la aplicación
├── obs.spec                   # Configuración de PyInstaller (exe optimizado)
├── requirements.txt           # Dependencias
├── equipos_ejemplo.json       # Plantilla de equipos.json
├── torneo_datos_ejemplo.json  # Ejemplo del estado que guarda la app
├── logos/                     # Logos de los equipos (vacía en el repositorio)
├── .gitignore
└── README.md
```

Estos archivos son locales de cada torneo y **no se suben al repositorio** (están en `.gitignore`):

| Ruta | Qué es |
|---|---|
| `equipos.json` | Tus equipos reales. Se crea copiando `equipos_ejemplo.json` (ver [Preparar los equipos](#2-preparar-los-equipos-opcional)). |
| `logos/*.png` | Los logos de tus equipos. |
| `torneo_datos.json` | Estado guardado. Lo crea la app (ver [Estado guardado](#estado-guardado-torneo_datosjson)). |
| `venv/`, `build/`, `dist/` | Entorno virtual y archivos de compilación. |

## Estructura esperada junto al `.exe`

El ejecutable **no lleva dentro** los equipos ni los logos: los busca en su misma carpeta. Para usarlo o distribuirlo, la carpeta debe quedar así:

```
CualquierCarpeta/
├── obs.exe
├── equipos.json       # opcional: sin él, el selector de equipos queda vacío
├── logos/             # opcional: logos por defecto de cada equipo
│   └── *.png
└── torneo_datos.json  # lo crea la app al pulsar "Actualizar OBS"
```

> `dist/` no recibe estos archivos automáticamente. Después de compilar, copia `equipos.json` y `logos/` junto a `obs.exe`. Los `*_ejemplo.json` no hacen falta en la carpeta del exe.

---

## Requisitos

- **Windows** con **Python 3.10 o superior** (desarrollado con 3.13).
- **OBS Studio 28 o superior**, que ya incluye obs-websocket v5 (probado con OBS 32.2).
- La fuente **Bebas Neue** instalada en Windows. Se usa en las listas de jugadores; si falta, OBS pone otra en su lugar.

## Instalación (desarrollo)

```powershell
cd obs
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Compilar el `.exe`

```powershell
.\venv\Scripts\python.exe -m PyInstaller obs.spec --noconfirm
```

- Se genera `dist\obs.exe`: un solo archivo, sin ventana de consola, de unos 8 MB.
- Cierra `obs.exe` antes de compilar; si está abierto, Windows no deja reemplazarlo.
- `obs.spec` excluye todo lo que la app no usa: numpy, OpenSSL, formatos de imagen sin uso, datos de Tcl y partes de la biblioteca estándar. Si añades a `main.py` algo que use un módulo de la lista `excludes`, quítalo de esa lista. Por ejemplo, conectar por `wss://` necesita `ssl`.

---

## Guía de uso

### 1. Preparar OBS (una sola vez)

1. **Activa el servidor WebSocket** en *Herramientas → Configuración del servidor WebSocket*:
   - Marca *Habilitar servidor WebSocket*.
   - Puerto `4455`.
   - Activa la autenticación y pon la contraseña configurada en `main.py` (`OBS_PASSWORD`).
2. **Crea las fuentes** en la escena que vayas a usar, con estos nombres exactos:

   | Nombre de la fuente | Tipo en OBS |
   |---|---|
   | `Logo Equipo A` | Imagen |
   | `Logo Equipo B` | Imagen |
   | `Lista de Jugadores A` | Texto (GDI+) |
   | `Lista de Jugadores B` | Texto (GDI+) |
   | `Puntaje Equipo A` | Texto (GDI+) |
   | `Puntaje Equipo B` | Texto (GDI+) |

   No importa dónde las coloques ni de qué tamaño: la app las reorganiza. La tipografía de los puntajes se respeta; la de las listas se cambia a Bebas Neue.
3. Deja esa escena **en el programa** (la que sale al aire). La app siempre trabaja sobre la escena activa.

### 2. Preparar los equipos (opcional)

La app lee los equipos del selector desde `equipos.json`. Créalo a partir de la plantilla y edítalo con tus equipos:

```powershell
copy equipos_ejemplo.json equipos.json
```

```json
{
  "EQUIPO-ROJO": {
    "jugadores": ["Jugador 1", "Jugador 2", "Jugador 3", "Jugador 4", "Jugador 5"]
  },
  "INVITADOS": {
    "jugadores": ["Carlos", "Sofía", "Diego", "Lucía"],
    "logo": "C:\\ruta\\completa\\a\\logo_invitados.png"
  }
}
```

- La clave (`"EQUIPO-ROJO"`) es el nombre que aparece en el selector.
- `jugadores`: hasta 5 nombres.
- `logo` (opcional): ruta completa a una imagen. Si no se indica, se usa `logos/<nombre>.png`, con el nombre en minúsculas y sin guiones ni espacios:

  | Equipo | Logo que busca |
  |---|---|
  | `EQUIPO-ROJO` | `logos/equiporojo.png` |
  | `EQUIPO AZUL` | `logos/equipoazul.png` |

Si `equipos.json` no existe, la app funciona igual, pero el selector queda vacío y los jugadores y logos se ponen a mano.

### 3. Usar el panel

```
[Logo A] [Jugadores A] [Puntaje A : Puntaje B] [Jugadores B] [Logo B]
                     [⚡ ACTUALIZAR OBS]
```

| Acción | Qué hace | ¿Envía a OBS? |
|---|---|---|
| Elegir un equipo en el selector | Rellena jugadores y logo | Sí, al momento |
| **Cambiar logo** | Abre un diálogo para elegir una imagen (PNG, JPG, WEBP) | Sí, al momento |
| Escribir nombres de jugadores | Edita la lista | No, hasta pulsar *Actualizar* |
| **✕** junto a un jugador | Borra ese nombre | No, hasta pulsar *Actualizar* |
| **Limpiar todos** | Borra los 5 nombres del equipo | No, hasta pulsar *Actualizar* |
| **+1 / −1** | Suma o resta un punto (mínimo 0) | Sí, al momento |
| **↺ Reiniciar** | Pone el puntaje en 0 | Sí, al momento |
| Escribir un puntaje y pulsar **Enter** | Fija ese valor | Sí, al momento |
| **⚡ ACTUALIZAR OBS** | Envía todo y reorganiza la escena | Sí |

Debajo del botón, la etiqueta de estado muestra el resultado: verde si todo salió bien y rojo si hubo errores. También muestra **avisos**, por ejemplo cuando una lista está demasiado cerca de su puntaje o cuando el lienzo no es 16:9.

Cada actualización guarda el estado en `torneo_datos.json`, y la app lo recupera al volver a abrirla.

### Estado guardado (`torneo_datos.json`)

No hace falta crearlo: la app lo escribe al pulsar *Actualizar OBS*, al tocar un puntaje, al elegir un equipo y al cambiar un logo. Al abrirse, rellena el panel con lo último guardado. Su formato (ver `torneo_datos_ejemplo.json`):

```json
{
  "equipoA": "EQUIPO-ROJO",
  "equipoB": "EQUIPO AZUL",
  "logoA": "C:\\ruta\\a\\obs\\logos\\equiporojo.png",
  "logoB": "C:\\ruta\\a\\obs\\logos\\equipoazul.png",
  "puntajeA": "2",
  "puntajeB": "1",
  "jugadoresA": ["Jugador 1", "Jugador 2", "Jugador 3", "Jugador 4", "Jugador 5"],
  "jugadoresB": ["Ana", "Luis", "Marta", "", ""],
  "tamanoFuenteJugadoresA": 300,
  "tamanoFuenteJugadoresB": 300
}
```

| Campo | Contenido |
|---|---|
| `equipoA` / `equipoB` | Equipo elegido en el selector (vacío si no se eligió ninguno). |
| `logoA` / `logoB` | Ruta **completa** del logo de cada equipo. |
| `puntajeA` / `puntajeB` | Puntaje, guardado como texto. |
| `jugadoresA` / `jugadoresB` | Los 5 campos de jugadores; los vacíos se guardan como `""` y no se envían a OBS. |
| `tamanoFuenteJugadoresA/B` | Tamaño de letra base de las listas. Se divide entre el número de jugadores. |

Para empezar un torneo desde cero, basta con borrar `torneo_datos.json`.

---

## Configuración de la distribución

Las constantes del principio de `main.py` controlan la distribución. Todas están en píxeles de un lienzo de **1920×1080**. En otras resoluciones 16:9 (720p, 4K) se escalan solas en proporción.

| Constante | Valor actual | Qué controla |
|---|---|---|
| `ALTURA_FILA` | 150 | Alto de logos, listas y puntajes. Los logos van en una caja cuadrada de este tamaño. |
| `ANCHO_MAX_LISTA` | 300 | Ancho máximo de cada lista. Si se pasa, la lista se reduce entera sin deformarse. |
| `MARGEN` | 50 | Distancia a los bordes del lienzo. |
| `SEPARACION_LOGO_LISTA` | 40 | Espacio entre cada logo y su lista. |
| `SEPARACION_LISTA_PUNTAJE` | 40 | Distancia mínima entre una lista y su puntaje; si no se cumple, se avisa. |
| `SEPARACION_PUNTAJES` | 120 | Hueco entre los dos puntajes en el centro. |
| `OBS_HOST` / `OBS_PORT` / `OBS_PASSWORD` | `localhost` / `4455` / — | Conexión con OBS. |
| `DEBUG_LAYOUT` | `True` | Muestra en consola las medidas calculadas (solo al ejecutar `main.py`, no en el `.exe`). |

Al reorganizar, la app también quita las rotaciones, los recortes y los *bounds* que se hayan puesto a mano en OBS.

---

## Solución de problemas

| Mensaje o síntoma | Causa probable |
|---|---|
| `Error al conectar con OBS` | OBS cerrado, servidor WebSocket desactivado, o puerto o contraseña distintos a los de `main.py`. |
| `Fuentes no encontradas en la escena activa` | Falta alguna de las 6 fuentes en la escena que está al aire, o tiene otro nombre. |
| `No existe el archivo '...'` | La ruta del logo ya no es válida, por ejemplo porque se movió la carpeta. Vuelve a elegir el equipo o el logo. |
| `No se encontró <archivo>` en la vista previa | Igual que el anterior: `torneo_datos.json` guarda rutas completas. |
| El selector solo muestra "— Elegir equipo —" | No hay `equipos.json` junto a `main.py` / `obs.exe`, o tiene un error de formato. |
| Aviso de que no cabe todo en el ancho | Nombres muy largos o puntajes grandes. Reduce `ALTURA_FILA` o las separaciones. |
| Las listas no salen en Bebas Neue | La fuente no está instalada en Windows. |
