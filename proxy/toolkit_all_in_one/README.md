# Proxy Security Toolkit

Launcher unico para abrir todas las herramientas del pack desde una sola ventana.

## Incluye

- OpenDir Downloader Pro
- OpenDir Downloader Classic
- OpenDir Downloader CLI
- Google Dork Auditor
- Ultimate Multi Proxy

## Windows

Desde PowerShell en esta carpeta:

```powershell
.\build_suite_windows.ps1
```

Salida:

```text
suite_dist/
  proxy_security_toolkit.exe
  tools/
    google_dork_auditor.exe
    opendir_downloader.exe
    opendir_downloader_gui.exe
    opendir_downloader_pro.exe
    ultimater_multi.exe
```

Ejecuta:

```powershell
.\suite_dist\proxy_security_toolkit.exe
```

## Linux

Primero instala dependencias:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-tk
```

Desde esta carpeta:

```bash
chmod +x build_suite_linux.sh ../build_all_linux.sh
./build_suite_linux.sh
```

Salida:

```text
suite_dist/
  proxy_security_toolkit
  tools/
    google_dork_auditor
    opendir_downloader
    opendir_downloader_gui
    opendir_downloader_pro
    ultimater_multi
```

Ejecuta:

```bash
./suite_dist/proxy_security_toolkit
```

## Uso

El launcher busca primero binarios ya compilados junto a el en `tools/`. Si no existen, intenta abrir los scripts Python desde el repo.
