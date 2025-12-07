# mantr

mantr es una herramienta de línea de comandos para sistemas Linux que permite traducir automáticamente las páginas del manual (man) a otros idiomas de forma completamente offline, utilizando el motor de traducción Argos Translate. Su objetivo es facilitar la comprensión de los manuales del sistema a usuarios que no dominan el inglés técnico.

## Instalación

Para instalar mantr mediante el paquete .deb:

sudo dpkg -i mantr_1.0-1.deb

Dependencias necesarias:

sudo apt install python3 python3-pip python3-venv
pip install argostranslate

Instalar los modelos de idioma necesarios, por ejemplo:

argospm install translate-en_es
argospm install translate-en_fr

## Uso

Traducción de un manual al español:

mantr ls

Traducción de un manual al francés:

mantr ls fr

Se pueden utilizar otros idiomas siempre que exista un modelo compatible en Argos Translate.

## Funcionamiento

mantr obtiene el contenido del manual mediante el comando man, lo procesa por bloques, traduce el contenido utilizando Argos Translate y muestra el resultado formateado mediante less. Las traducciones se almacenan en una caché local para evitar traducciones repetidas y mejorar el rendimiento.

Ruta de la caché:

~/.cache/mantr

## Opciones adicionales

Mostrar ayuda:

mantr --help

Mostrar versión:

mantr --version

Borrar la caché de traducciones:

mantr --clear-cache

Mostrar el contenido de la caché:

mantr --show-cache

## Características principales

- Traducción automática de páginas del manual.
- Funcionamiento completamente offline.
- Soporte para múltiples idiomas.
- Sistema de caché para mejorar el rendimiento.
- Compatible con distribuciones basadas en Debian (Ubuntu, Kali, etc.).

## Proyecto académico

Proyecto desarrollado como Trabajo de Fin de Grado.
