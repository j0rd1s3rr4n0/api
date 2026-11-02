# Security Toolkit All-in-One

Herramienta unica con tres modulos en la misma GUI:

- OpenDir: escaneo y descarga de directory listings, OpenDirs, WebDAV visibles y rutas compatibles con Tor/proxies.
- Google Dorks: biblioteca local categorizada, filtro, copia, exportacion y apertura de busquedas.
- Proxies: scraper/validador integrado para HTTP, HTTPS, SOCKS4, SOCKS4A, SOCKS5 y SOCKS5H.

## Windows

```powershell
.\build_windows.ps1
```

Salida:

```text
dist\security_toolkit_all_in_one.exe
```

## Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-linux.txt
./build_linux.sh
```

Salida:

```text
dist/security_toolkit_all_in_one
```

## Notas de seguridad

- Para `.onion`, usa Tor como SOCKS5H para que la resolucion DNS pase por Tor.
- Para clearnet anonimo, activa Tor o proxies y deja `Sin IP leak` activo.
- La cuarentena de archivos peligrosos marca descargas ejecutables con `Zone.Identifier` en Windows cuando aplica.
