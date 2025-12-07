import sys, os, re, subprocess, time, hashlib, textwrap
from pathlib import Path

WRAP_WIDTH = 80  # ancho típico de man
TARGET = sys.argv[1] if len(sys.argv) > 1 else "es"
BACKEND = os.environ.get("BACKEND", "argos")

GLOSSARY = {
    "Anchoring": "Anclaje",
    "Anchor": "Ancla",
    "Anchors": "Anclas",

    "The Backslash Character and Special Expressions":
        "El carácter barra invertida y las expresiones especiales",

    "Output Line Prefix Control": "Control del prefijo de las líneas de salida",
    "Reporting Bugs": "Informe de errores",

    "The Backslash Character":
        "El carácter barra invertida",

    "Special Expressions":
        "Expresiones especiales",

    "Character classes": "Clases de caracteres",
    "Wildcard matching": "Coincidencia con comodines",
    "Bracket expressions": "Expresiones entre corchetes",
    "Regular expressions": "Expresiones regulares",
    "Metacharacters": "Metacaracteres",
    "Quantifiers": "Cuantificadores",
    "Repetition": "Repetición",
}

CUSTOM_TITLES = {
    "Anchoring": "ANCLAJE",
    "The Backslash Character and Special Expressions": "CARÁCTER BARRA INVERTIDA Y EXPRESIONES ESPECIALES",
    "Repetition": "REPETICIÓN",
}


# Patrones reutilizables para flags cortas / largas.
# Soportan ejemplos como:
#   -q
#   -q, --quiet
#   -q, --quiet, --silent
#   --color[=WHEN]
#   --color[=WHEN], --colour[=WHEN]
FLAG_SHORT = r'-[A-Za-z0-9]+'
FLAG_LONG  = r'--[A-Za-z0-9][A-Za-z0-9-]*(?:\[=[^]]+\]|=[^\s]+)?'
FLAG       = rf'(?:{FLAG_SHORT}|{FLAG_LONG})'

OPTION_HEAD_RE = re.compile(
    rf'^\s*(?:{FLAG})(?:\s*,\s*{FLAG})*\s*$',
    re.M,
)


VERB_MAP = {
    "ignore": "ignorar", "list": "listar", "print": "imprimir", "show": "mostrar",
    "display": "mostrar", "include": "incluir", "exclude": "excluir", "sort": "ordenar",
    "use": "usar", "append": "añadir", "enclose": "encerrar", "reverse": "invertir",
    "scale": "escalar", "color": "colorear", "hide": "ocultar",
}

def fix_do_not_spanish(s: str) -> str:
    # do not <verb>  → no <infinitivo>
    def repl(m):
        v = m.group(1).lower()
        return "no " + VERB_MAP.get(v, v)  # si no está en el mapa, deja el verbo tal cual
    s = re.sub(r'\b[Dd]o not\s+([A-Za-z]+)\b', repl, s)
    # don't <verb> (poco frecuente en man, por si acaso)
    s = re.sub(r"\b[Dd]on['’]t\s+([A-Za-z]+)\b", repl, s)
    return s

def post_es_fixes(s: str) -> str:
    out = s
    # non-XYZ → no XYZ
    out = re.sub(r'\bnon[-\s]?([a-záéíóúñ]+)\b', r'no \1', out, flags=re.I)
    # starting/ending with
    out = re.sub(r'\bstarting with\b', 'que comienzan por', out, flags=re.I)
    out = re.sub(r'\bending with\b', 'que terminan con', out, flags=re.I)
    # in columns / by columns
    out = re.sub(r'\bby columns\b', 'en columnas', out, flags=re.I)
    out = re.sub(r'\bin columns\b', 'en columnas', out, flags=re.I)
    # artículos y pegados comunes
    out = re.sub(r'([.,;:])([^\s])', r'\1 \2', out)
    # aplicar regla "do not"
    out = fix_do_not_spanish(out)
        # PARCHES ESPECÍFICOS PARA grep(1)
    out = re.sub(
        r"Skip any command-line file with a name suffix that matches? the pattern GLOB, using wildcard matching; a name suffix is either the whole name, or a trailing part that starts with a non-slash character immediately after a slash \(/.\) in the name\.",
        "Saltar cualquier archivo de línea de comandos cuyo nombre termine con el patrón GLOB, "
        "usando coincidencia con comodines; un sufijo de nombre puede ser el nombre completo o "
        "la parte final que empieza con un carácter que no es / justo después de una barra (/).",
        out
    )

    out = re.sub(
        r"Skip any command-line directory with a name suffix that match the pattern GLOB\.",
        "Saltar cualquier directorio de línea de comandos cuyo nombre termine con el patrón GLOB.",
        out
    )
    # --- Parches específicos para frases difíciles de grep(1) ---


    # Cola de la frase de --include / --exclude
    out = re.sub(
        r'and --exclude options are given, the last matching one wins\.',
        'y se dan opciones --exclude, la última coincidencia es la que prevalece.',
        out
    )
    # Frase típica de man grep --exclude=GLOB (y similares):
    # la traducimos entera para evitar mezclas inglés/español.
    out = re.sub(
        r"Skip any command-line file with a name suffix that match(?:es|ing)? the pattern GLOB,.*?;",
        "Saltar cualquier archivo de línea de comandos cuyo nombre tenga un sufijo que coincida con el patrón GLOB, "
        "usando coincidencia con comodines;",
        out,
        flags=re.S,
    )
    # Frase corta que Argos a veces no traduce.
    out = re.sub(
        r"Suppress error messages about no existent or unreadable files\.",
        "Suprime los mensajes de error sobre archivos inexistentes o ilegibles.",
        out,
    )



    return out

    return out


def looks_like_options_block(chunk: str) -> bool:
    """
    Devuelve True si el 'chunk' parece listado de opciones:
    - Una o más líneas que son solo flags (-x, --xxx, -x, --xxx, --xxx=WORD)
    - Y al menos una línea de descripción indentada a continuación.
    """
    lines = chunk.splitlines()
    i = 0
    saw_pair = False
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        # ¿línea de cabecera de opción?
        if OPTION_HEAD_RE.match(ln):
            j = i + 1
            # buscar una continuación indentada (descripción)
            if j < len(lines) and (lines[j].startswith(" ") or lines[j].startswith("\t")):
                saw_pair = True
            # saltar hasta el siguiente “bloque” (sigue leyendo continuaciones indentadas)
            i = j
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith(" ") or lines[i].startswith("\t")):
                i += 1
            continue
        else:
            # no es opción ⇒ no cumple
            return False
    return saw_pair

def unhyphenate_chunk(s: str) -> str:
    """Une palabras partidas por guion al final de línea: 'speci-\nfied' -> 'specified'
       Soporta guion ASCII y guiones Unicode (incluye soft hyphen).
    """
    return re.sub(r'([A-Za-z])(?:-|[\u00AD\u2010\u2011\u2012\u2013\u2014])\s*\n\s*([A-Za-z])', r'\1\2', s)

def normalize_for_translation(s: str) -> str:
    if not s:
        return s
    # quita soft hyphen y guiones tipográficos comunes
    s = s.replace("\u00AD", "-").replace("\u2010", "-").replace("\u2011", "-") \
         .replace("\u2012", "-").replace("\u2013", "-").replace("\u2014", "-")
    # colapsa espacios y arregla saltos
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s+\n", "\n", s)
    return s.strip()

SPANISH_CHARS = "áéíóúÁÉÍÓÚñÑ"

def translate_with_retry(desc: str) -> str:
    base = normalize_for_translation(desc)
    t = translate_safe(base)
    if t and t.strip() != base.strip():
        # primera pasada buena
        if TARGET.startswith("es"):
            # solo en español aplicamos glosario + arreglos específicos
            return post_es_fixes(apply_glossary(t))
        # en otros idiomas devolvemos la traducción tal cual
        return t

    # Reintento por trozos más pequeños (. ; : ,)
    parts = re.split(r"([.;:,])", base)
    out, buf = [], ""
    for i, tok in enumerate(parts):
        if i % 2 == 0:
            buf = tok.strip()
        else:
            if buf:
                frag = translate_safe(buf)
                if TARGET.startswith("es"):
                    frag = post_es_fixes(apply_glossary(frag))
                out.append(frag)
            out.append(tok)  # el separador
            buf = ""
    if buf:
        frag = translate_safe(buf)
        if TARGET.startswith("es"):
            frag = post_es_fixes(apply_glossary(frag))
        out.append(frag)

    res = "".join(out).strip()
    return res if res else base



# --- Mapeo de secciones ---
SECTION_MAP = {
    "NAME": "NOMBRE", "SYNOPSIS": "SINOPSIS", "DESCRIPTION": "DESCRIPCIÓN",
    "OPTIONS": "OPCIONES", "EXIT STATUS": "ESTADO DE SALIDA",
    "RETURN VALUE": "VALOR DE RETORNO", "ENVIRONMENT": "ENTORNO",
    "FILES": "ARCHIVOS", "AUTHOR": "AUTOR", "REPORTING BUGS": "INFORME DE ERRORES",
    "COPYRIGHT": "DERECHOS DE AUTOR", "SEE ALSO": "VÉASE TAMBIÉN",
}

# === Caché de resultados ya traducidos ===
CACHE_DIR = Path(os.environ.get("MANTR_CACHE_DIR", Path.home() / ".cache" / "mantr"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def compute_cache_key(target_lang: str, backend: str, raw_text: str) -> Path:
    """
    Genera una clave de caché a partir de idioma + backend + hash del texto de entrada.
    Devuelve la ruta del fichero de caché.
    """
    h = hashlib.sha256(raw_text.encode("utf-8", errors="ignore")).hexdigest()
    safe_cmd = os.environ.get("MANTR_CMD", "unknown").replace("/", "_")
    short_hash = h[:12]  # suficiente, 12 caracteres

    fname = f"{safe_cmd}_{target_lang}_{backend}_{short_hash}.txt"

    return CACHE_DIR / fname


TARGET  = sys.argv[1] if len(sys.argv) > 1 else "es"
BACKEND = os.environ.get("BACKEND", "auto")  # auto | argos | libre | hf

# ==================== TRADUCTOR (solo gratis) ====================
class Translator:
    """
    Backends:
      - argos : Argos Translate (offline puro, requiere paquete en→es instalado)
      - libre : LibreTranslate local (http://localhost:5000/translate por defecto)
      - hf    : HuggingFace (Helsinki-NLP/opus-mt-en-es); descarga 1ª vez y luego offline
      - auto  : intenta Argos → Libre → HF
    """
    def __init__(self, backend="auto"):
        self.backend = backend
        self._init_clients()

    def _init_clients(self):
        self._argos = None
        self._requests = None
        self._libre_url = os.environ.get("LIBRE_URL", "http://localhost:5000/translate")
        self._hf_pipe = None

        if self.backend in ("argos", "auto"):
            try:
                from argostranslate import translate as _atr
                self._argos = _atr
            except Exception:
                self._argos = None

        if self.backend in ("libre", "auto"):
            try:
                import requests  # noqa
                self._requests = __import__("requests")
            except Exception:
                self._requests = None

        if self.backend in ("hf", "auto"):
            try:
                from transformers import pipeline
                self._hf_pipe = pipeline(
                    "translation_en_to_es",
                    model="Helsinki-NLP/opus-mt-en-es"
                )
            except Exception:
                self._hf_pipe = None

    def _argos_translate(self, text, src, dest):
        if not self._argos:
            return None
        try:
            return self._argos.translate(text, src, dest)
        except Exception:
            return None

    def _libre_translate(self, text, src, dest):
        if not self._requests:
            return None
        try:
            r = self._requests.post(
                self._libre_url,
                data={"q": text, "source": src, "target": dest, "format": "text"},
                timeout=15,
            )
            if r.ok:
                return r.json().get("translatedText") or None
        except Exception:
            pass
        return None

    def _hf_translate(self, text, src, dest):
        # Modelo EN->ES; si pides otro par, devolvemos None
        if not self._hf_pipe or not (src == "en" and dest == "es"):
            return None
        try:
            return self._hf_pipe(text)[0]["translation_text"]
        except Exception:
            return None

    def translate(self, text, src="en", dest="es"):
        text = (text or "").strip()
        if not text:
            return text

        if self.backend == "argos":
            return self._argos_translate(text, src, dest) or text
        if self.backend == "libre":
            return self._libre_translate(text, src, dest) or text
        if self.backend == "hf":
            return self._hf_translate(text, src, dest) or text

        # auto: Argos → Libre → HF → original
        out = self._argos_translate(text, src, dest)
        if out: return out
        out = self._libre_translate(text, src, dest)
        if out: return out
        out = self._hf_translate(text, src, dest)
        return out or text


tr = Translator(BACKEND)

def apply_glossary(s: str) -> str:
    for en, es in GLOSSARY.items():
        # case-insensitive, por si acaso
        s = re.sub(rf"\b{re.escape(en)}\b", es, s, flags=re.IGNORECASE)
    return s

def translate_safe(text, src="en", dest=TARGET, sleep=0.0):
    """
    Traduce con tolerancia a fallos y aplica glosario/arreglos
    cuando el destino es español.
    """
    text = (text or "").strip()
    if not text:
        return text

    out = tr.translate(text, src=src, dest=dest) or text

    if dest.startswith("es"):
        # glosario técnico (grep, anchoring, etc.)
        out = apply_glossary(out)
        # arreglillos de "do not", non-X, espacios, etc.
        out = post_es_fixes(out)

    if sleep:
        time.sleep(sleep)

    return out

    # 1) parches específicos + fixes generales en español
    out = post_es_fixes(out)
    # 2) glosario otra vez, por si Argos ha dejado palabras raras
    out = apply_glossary(out)

    return out


# --- Detección de opciones ---
OPTION_PATTERNS = [
    # Cualquier combinación de flags seguida de descripción
    #   -q, --quiet, --silent  Quiet; do not write anything...
    #   --exclude=GLOB  Skip any command-line file...
    re.compile(
        rf'^\s*(?P<flags>{FLAG}(?:\s*,\s*{FLAG})*)\s+(?P<desc>.+)$'
    ),
]

FLAG_ONLY_PATTERNS = [
    # Solo flags en la línea, sin descripción todavía
    #   -q, --quiet, --silent
    #   --color[=WHEN], --colour[=WHEN]
    re.compile(
        rf'^\s*(?P<flags>{FLAG}(?:\s*,\s*{FLAG})*)\s*$'
    ),
]

def split_option_line(line: str):
    for rx in OPTION_PATTERNS:
        m = rx.match(line)
        if m:
            return m.group("flags"), m.group("desc")
    return None, None

def match_flag_only(line: str):
    for rx in FLAG_ONLY_PATTERNS:
        m = rx.match(line)
        if m:
            return m.group("flags")
    return None
# ======================================
#   FUNCIONES DE FORMATEO ESTILO MAN
# ======================================

def format_option(flags: str, desc: str, width: int = 80) -> str:
    """
    Formatea una opción al estilo 'man':
    - flags a la izquierda
    - descripción alineada a partir de una columna fija
    - líneas envueltas con indentación
    """
    indent_col = 16  # columna donde empieza la descripción
    flags_str = flags.rstrip()

    # Determinar si la línea de flags cabe o hay que saltar
    if len(flags_str) >= indent_col:
        header = " " * 8 + flags_str + "\n"
        indent = " " * indent_col
    else:
        padding = " " * (indent_col - len(flags_str))
        header = " " * 8 + flags_str + padding
        indent = " " * indent_col

    # Envolver descripción
    words = desc.split()
    lines = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 > (width - indent_col):
            lines.append(indent + current)
            current = w
        else:
            current += (" " + w) if current else w
    if current:
        lines.append(indent + current)

    return header + "\n".join(lines) + "\n"


def translate_options_block(block_text: str) -> str:
    block_text = unhyphenate_chunk(block_text)

    lines = block_text.splitlines()
    out_lines = []
    carry = None

    def emit_option(flags: str, desc: str) -> None:
        indent_flags = " " * 7     # columna 8
        indent_desc = " " * 14     # columna 15 (estilo GNU)

        desc = normalize_for_translation(desc)
        translated = translate_with_retry(desc)
        translated = fix_punctuation_spacing(translated)

        wrapped = textwrap.fill(
            translated,
            width=WRAP_WIDTH,
            initial_indent=indent_desc,
            subsequent_indent=indent_desc
        )

        out_lines.append(indent_flags + flags)
        out_lines.append(wrapped)

    for ln in lines:
        if not ln.strip():
            if carry:
                flags, desc = carry
                emit_option(flags, desc)
                carry = None
            out_lines.append(ln)
            continue

        flags, desc = split_option_line(ln)
        if flags is not None:
            if carry:
                f2, d2 = carry
                emit_option(f2, d2)
            carry = (flags, (desc or "").strip())
            continue

        only = match_flag_only(ln)
        if only:
            if carry:
                f2, d2 = carry
                emit_option(f2, d2)
            carry = (only, "")
            continue

        if carry and (ln.startswith(" ") or ln.startswith("\t")):
            carry = (carry[0], (carry[1] + " " + ln.strip()).strip())
        else:
            out_lines.append(ln)

    if carry:
        flags, desc = carry
        emit_option(flags, desc)

    return "\n".join(out_lines) + "\n"

def fix_punctuation_spacing(s: str) -> str:
    s = re.sub(r'([.,;:!?])([^\s])', r"\1 \2", s)
    s = re.sub(r"(\S)(')", r"\1 \2", s)
    return s

# --- Consumo de bloques ---
buf, mode, out_chunks = [], None, []
current_section = None  # si no lo tienes ya declarado por arriba

def flush():
    global buf, mode, current_section
    if mode is None:
        return
    chunk = "".join(buf)

    if mode == "text":
        # ¿En realidad es un bloque de opciones mal clasificado?
        if looks_like_options_block(chunk):
            out_chunks.append(translate_options_block(chunk))
        else:
            # primero, desguionar con el chunk tal cual (con \n)
            chunk2 = unhyphenate_chunk(chunk)
            # ahora sí, aplanar
            joined = " ".join([ln.strip() for ln in chunk2.splitlines() if ln.strip()])
            joined = normalize_for_translation(joined)

            if current_section == "SYNOPSIS":
                # En SYNOPSIS preservamos la sintaxis del comando, no la traducimos
                wrapped = textwrap.fill(joined, width=WRAP_WIDTH)
                out_chunks.append(wrapped + "\n\n")
            else:
                translated = translate_safe(joined, dest=TARGET)
                translated = fix_punctuation_spacing(translated)
                # aquí envolvemos el párrafo a 80 columnas
                wrapped = textwrap.fill(translated, width=WRAP_WIDTH)
                out_chunks.append(wrapped + "\n\n")

    elif mode == "options":
        out_chunks.append(translate_options_block(chunk))

    elif mode == "section":
        title = (chunk or "").strip()
        current_section = title
        if TARGET.startswith("es"):
            # en español mapeamos NAME→NOMBRE, DESCRIPTION→DESCRIPCIÓN, etc.
            out_chunks.append(SECTION_MAP.get(title, title) + "\n\n")
        else:
            # en otros idiomas dejamos el título original (en inglés)
            out_chunks.append(title + "\n\n")

    else:  # code / others
        out_chunks.append(chunk + ("\n" if not chunk.endswith("\n") else ""))

    buf, mode = [], None

# === LECTURA + CACHÉ ===

# 1) leer toda la entrada de una vez
raw = sys.stdin.read()
if not raw:
    sys.exit(0)

# 2) clave de caché
cache_file = compute_cache_key(TARGET, BACKEND, raw)

# 3) si existe en caché, mostrar y salir
if cache_file.exists():
    cached = cache_file.read_text(encoding="utf-8", errors="ignore")
    try:
        p = subprocess.Popen(["less", "-R"], stdin=subprocess.PIPE, text=True)
        p.communicate(cached)
    except Exception:
        print(cached, end="")
    sys.exit(0)

# 4) si no hay caché, procesar como siempre pero usando 'raw'
for line in raw.splitlines(keepends=True):
    if line.startswith("--- ") and line.strip().endswith("---"):
        tag = line.strip().strip("- ").strip("/")
        if tag in ("text", "code", "options", "section") and line.strip().startswith("--- /"):
            flush()
            continue
        if tag in ("text", "code", "options", "section"):
            flush()
            mode = tag
            continue
    buf.append(line)

flush()

# 5) generar salida final
output = "".join(out_chunks)

# 6) guardar en caché
try:
    cache_file.write_text(output, encoding="utf-8")
except Exception:
    pass  # si falla la caché no rompemos nada

# 7) mostrar por less (como antes)
try:
    p = subprocess.Popen(["less", "-R"], stdin=subprocess.PIPE, text=True)
    p.communicate(output)
except Exception:
    print(output, end="")
