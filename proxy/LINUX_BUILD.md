# Linux build

Este directorio incluye un compilador simple para generar todos los binarios Linux de una vez con PyInstaller.

## Herramientas que compila

- `ultimater_multi`
- `google_dork_auditor`
- `opendir_downloader`
- `opendir_downloader_gui`
- `opendir_downloader_pro`

## Dependencias del sistema

En Debian/Ubuntu/Kali:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-tk
```

Para las GUI en servidores sin escritorio, usa un entorno grafico real o Xvfb:

```bash
sudo apt install -y xvfb
```

## Compilar todo

Desde la carpeta `proxy`:

```bash
chmod +x build_all_linux.sh
./build_all_linux.sh
```

El script crea un virtualenv local en `.venv-build`, instala dependencias desde `requirements-linux-build.txt` y deja los binarios en:

```text
linux_dist/
```

## Ejecutar

```bash
./linux_dist/opendir_downloader_pro
./linux_dist/opendir_downloader_gui
./linux_dist/google_dork_auditor
./linux_dist/opendir_downloader --help
./linux_dist/ultimater_multi --help
```

## Tor en Linux

Instala Tor:

```bash
sudo apt install -y tor
sudo systemctl enable --now tor
```

Normalmente quedara escuchando en:

```text
socks5h://127.0.0.1:9050
```

En OpenDir usa `socks5h`, no `socks5`, para que la resolucion DNS de `.onion` se haga dentro de Tor.

## Personalizar rutas

Puedes cambiar el virtualenv, salida o Python:

```bash
VENV_DIR=/tmp/proxy-build-venv DIST_DIR=/tmp/proxy-bin PYTHON_BIN=python3.12 ./build_all_linux.sh
```

## Notas

- PyInstaller no compila de Windows a Linux. Ejecuta este script dentro de Linux para obtener binarios Linux.
- Los binarios son para la distro/arquitectura donde compilas. Para mayor compatibilidad, compila en una distro antigua o en una VM/container similar al destino.
- `sockshandler.py` esta incluido dentro de las carpetas de OpenDir para que el soporte SOCKS no dependa de un paquete externo raro.
