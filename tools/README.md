# Herramientas auxiliares

Estas utilidades se han trasladado desde `proxy/`:

- `opendir_downloader/`: descargador CLI y GUI clásica.
- `opendir_downloader_pro/`: descargador GUI Pro.
- `google_dork_auditor/`: auditor de dorks.
- `security_toolkit_all_in_one/`: interfaz integrada; importa el motor único de `../proxy/proxy_atlas.py`.
- `toolkit_all_in_one/`: lanzador de las herramientas y del gestor de proxies.

Los scripts de compilación y lanzadores utilizan la nueva estructura. El build conjunto de Linux sigue en `proxy/build_all_linux.sh`. No hay una copia independiente del motor de proxies dentro de los toolkits.
