# API · Proxy Atlas

<img src="proxy/assets/proxy_atlas.png" alt="Icono de Proxy Atlas" width="128" height="128">

Repositorio de configuraciones, listas y herramientas. **Proxy Atlas** centraliza la recopilación, normalización, validación y clasificación de proxies, con un pool histórico permanente y resultados actualizados en cada ejecución.

## Inicio rápido

Desde la raíz del repositorio, con Python 3.10 o posterior:

```powershell
python -m pip install -r requirements_proxy.txt
python proxy/proxy_atlas.py
```

En Windows también puedes usar `proxy/run_proxy_atlas.bat`. El lanzador ejecuta una vez; para una actualización periódica debes configurar el programador de tareas o cron.

Para leer una lista local sin descargar fuentes:

```powershell
python proxy/proxy_atlas.py --input mi_lista.txt
```

La entrada admite IPv4 y puerto, con protocolo opcional. Se soportan HTTP, HTTPS, SOCKS4, SOCKS4a, SOCKS5 y SOCKS5h. Sin protocolo se asume HTTP. La validación exige una respuesta JSON con una IP válida; abrir el puerto no basta.

## Motor Go complementario

Python gestiona las fuentes, SQLite, la geolocalización y los informes. Go puede encargarse de las conexiones concurrentes con colas acotadas y plazos por comprobación.

Para compilar el checker con Go 1.22 o posterior:

```powershell
cd proxy/golang_checker
go test ./...
go build -trimpath -o proxy_checker.exe .
cd ../..
python proxy/proxy_atlas.py --engine go --threads 128
```

Si ya tienes `proxy/golang_checker/proxy_checker.exe`, puedes ejecutar directamente el último comando. En Linux/macOS compila con `-o proxy_checker`. El binario compilado no necesita Go instalado para ejecutarse y no se incluye en Git. Python sigue siendo el motor predeterminado.

Consulta los formatos JSONL/TXT, el uso independiente y las diferencias de timeout en la [documentación del checker Go](proxy/golang_checker/README.md).

## Histórico y resultados actuales

El pool conserva los proxies aunque fallen o desaparezcan de las fuentes. Las fechas se guardan en UTC:

| Campo | Significado |
| --- | --- |
| `first_seen` | Primera incorporación al pool; no se sobrescribe |
| `last_seen` | Última aparición en una fuente o lista de entrada |
| `last_checked` | Última comprobación completada |
| `last_valid` | Última comprobación satisfactoria |
| `status` | Último estado: `valid`, `invalid` o `unverified` |
| `checks` | Número de comprobaciones completadas |
| `date_basis` | Fecha observada o fecha de importación de datos antiguos |

Para los datos antiguos sin fecha original se registra la fecha de importación. El estado histórico describe la última comprobación, no garantiza disponibilidad actual.

Cada ejecución comprueba los nuevos candidatos, los válidos anteriores y hasta **30.000 entradas del histórico**, priorizando las nunca comprobadas y las más antiguas. Puedes ajustar esa selección:

```powershell
python proxy/proxy_atlas.py --engine go --history-limit 5000
python proxy/proxy_atlas.py --engine go --full-history
```

`--history-limit 0` omite la selección del histórico; los nuevos candidatos y los válidos anteriores se siguen comprobando. `--max-proxies` controla el tamaño de lote, no el total de proxies a validar.

## Estructura

| Ruta | Contenido |
| --- | --- |
| `proxy/proxy_atlas.py` | CLI y motor principal |
| `proxy/proxy_atlas.spec` | Empaquetado con PyInstaller |
| `proxy/run_proxy_atlas.bat` | Lanzador de Windows |
| `proxy/sources.txt` | Fuentes adicionales |
| `proxy/golang_checker/` | Validador Go y pruebas |
| `proxy/history/pool.sqlite3` | Pool histórico persistente |
| `proxy/history/pool.csv` | Exportación del histórico |
| `proxy/results/candidates.txt` | Candidatos de la ejecución |
| `proxy/results/valid.txt` | Proxies que superaron la validación |
| `proxy/results/classified/proxies.csv` | Informe con ubicación y proveedor |
| `proxy/results/classified/proxies.json` | Informe estructurado |
| `proxy/results/classified/*.txt` | Listas por protocolo |
| `proxy/results/classified/countries/` | Listas por código de país y protocolo |
| `proxy/results/classified/providers/` | Listas por ASN y protocolo |
| `proxy/logs/` | Registro de ejecución |
| `proxy/archive/` | Datos heredados |
| `tools/` | Descargadores, auditor y toolkits |

Los resultados actuales contienen únicamente proxies validados en esa ejecución. La ubicación aproximada y el proveedor/ASN corresponden a la IP del servidor proxy. IPinfo aporta esos metadatos; si no están disponibles se indica `Unknown`. Las consultas correctas se cachean siete días. `--no-geo` desactiva la geolocalización.

Las rutas predeterminadas se resuelven junto al script. Consulta las opciones para personalizarlas con `python proxy/proxy_atlas.py --help`.

## Herramientas auxiliares

Los descargadores OpenDir, el auditor de dorks y los toolkits están en [`tools/`](tools/README.md). Los toolkits utilizan el mismo motor de Proxy Atlas. Las configuraciones y datos de los otros proyectos permanecen en sus carpetas del repositorio.

## Pruebas

Desde la raíz:

```powershell
python -m unittest discover -s proxy -p test_proxy_atlas.py -v
```

Para comprobar la integración con el ejecutable Go compilado, en PowerShell:

```powershell
$env:PROXY_ATLAS_TEST_ENGINE = "go"
python -m unittest discover -s proxy -p test_proxy_atlas.py -v
Remove-Item Env:PROXY_ATLAS_TEST_ENGINE
```

Las pruebas del checker se ejecutan con `go test ./...` desde `proxy/golang_checker/`.

## Documentación

- [Proxy Atlas: opciones, clasificación e histórico](proxy/README.md)
- [Checker Go: compilación y ejecución independiente](proxy/golang_checker/README.md)
- [Herramientas auxiliares](tools/README.md)
- [Compilación para Linux](proxy/LINUX_BUILD.md)

Los antiguos comandos `ultimater_multi.py` y `run_ultimater_multi_hourly.bat` se sustituyeron por `proxy_atlas.py` y `run_proxy_atlas.bat`. Actualiza cualquier tarea externa que aún utilice esos nombres. No se publican resultados automáticamente salvo que se indique expresamente `--git`.
