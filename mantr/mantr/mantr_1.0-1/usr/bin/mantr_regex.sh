#!/usr/bin/env bash
# Uso: ./mantr_regex.sh <comando>

cmd="$1"
if [ -z "$cmd" ]; then
  echo "Uso: $0 <comando>"
  exit 1
fi

# Usamos gawk si existe; si no, awk normal
AWK_BIN="$(command -v gawk || command -v awk)"

man "$cmd" | col -bx | "$AWK_BIN" '
BEGIN {
  bloque = ""
  current_section = ""
}

function is_section_title(line) {
  return (line ~ /^[A-Z][A-Z0-9 ]+$/ &&
          line !~ /^[A-Z0-9_.-]+\([0-9][^)]+\)[[:space:]]+.*$/)
}

# Simplificado: evita problemas con UTF-8
function normalize_text(s) {
  gsub(/[[:space:]]+/, " ", s)
  sub(/^[[:space:]]+/, "", s)
  sub(/[[:space:]]+$/, "", s)
  return s
}

function looks_sentence(txt) {
  words = gsub(/\b[[:alpha:]]{3,}\b/, "&", txt)
  punct = (txt ~ /[.;:!?)]/)
  lower = (txt ~ /[a-z]/)
  return (words >= 6 && punct && lower)
}

function dedent_common(txt,    arr,n,i,ln,minind,reb) {
  n = split(txt, arr, "\n")
  minind = 999
  for (i=1;i<=n;i++){
    ln = arr[i]
    if (ln ~ /[^[:space:]]/) {
      match(ln, /^[ ]*/)
      if (RLENGTH < minind) minind = RLENGTH
    }
  }
  reb=""
  for (i=1;i<=n;i++){
    ln = arr[i]
    if (minind < 999) sub("^" sprintf(" {%d}", minind), "", ln)
    reb = reb ln "\n"
  }
  return reb
}

function looks_code(txt,    arr,n,i,ln,indented,words,has_punct) {
  n = split(txt, arr, "\n")
  indented=0; words=0; has_punct=0
  for (i=1;i<=n;i++){
    ln=arr[i]
    if (ln ~ /^[[:space:]]{6,}/) indented++
    if (ln ~ /[[:alpha:]]{3,}/) words++
    if (ln ~ /[.;:!?)]/) has_punct=1
  }
  return (indented*2>=n) && (!has_punct || words<=1)
}

function flush_block(    tipo,arr,n,i,ln,joined,first,first_trim) {
  if (bloque == "") return

  n = split(bloque, arr, "\n")
  for (i=1;i<=n;i++){
    ln = arr[i]
    if (ln ~ /[^[:space:]]/) { first=ln; break }
  }

  deb    = dedent_common(bloque)
  joined = normalize_text(deb)

  # Recorta sangría para detectar opciones aunque estén indentadas
  first_trim = first
  sub(/^[[:space:]]+/, "", first_trim)

  if (is_section_title(bloque)) {
    tipo="section"
  }
  else if (current_section == "NAME") {
    tipo="text"
  }
  else if (first_trim ~ /^--?[A-Za-z0-9]/) {
    tipo="options"
  }
  else if (current_section == "DESCRIPTION" && looks_sentence(joined)) {
    tipo="text"
  }
  else if (looks_code(deb)) {
    tipo="code"
  } else {
    tipo="text"
  }

  print "--- " tipo " ---"
  print bloque
  print "--- /" tipo " ---"

  bloque = ""
}

{
  if (is_section_title($0)) {
    flush_block()
    current_section = $0
    print "--- section ---"
    print $0
    print "--- /section ---"
    next
  }

  if ($0 ~ /^[[:space:]]*$/) {
    flush_block()
    next
  }

  bloque = bloque $0 "\n"
}

END {
  flush_block()
}
'
