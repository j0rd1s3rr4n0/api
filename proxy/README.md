# Proxy Atlas

<img src="assets/proxy_atlas.png" alt="Icono de Proxy Atlas" width="128" height="128">

El único motor mantenido es `proxy_atlas.py`. Recoge listas remotas o lee una lista local, normaliza y elimina duplicados, comprueba los proxies y exporta ubicación y proveedor. Las implementaciones anteriores se han retirado; su historial está en Git.

Desde la raíz del repositorio:

```sh
python -m pip install -r requirements_proxy.txt
python proxy/proxy_atlas.py
```

Motor Go complementario: [golang_checker](golang_checker/README.md). Tras compilarlo, ejecuta `python proxy/proxy_atlas.py --engine go`. El histórico y los informes siguen siendo los mismos.

Para procesar una lista propia sin descargar fuentes:

```sh
python proxy/proxy_atlas.py --input mi_lista.txt
```

Entrada: IPv4 y puerto, con protocolo opcional (`http://`, `https://`, `socks4://`, `socks4a://`, `socks5://`, `socks5h://`). Sin protocolo se asume HTTP, o se infiere SOCKS del nombre de la fuente remota. No se admiten credenciales ni QUIC. `https://` significa TLS hasta el servidor proxy, no simplemente capacidad CONNECT. Las listas externas pueden etiquetar esa distinción incorrectamente; solo se exportan las entradas que superan la comprobación.

La comprobación usa HTTPS con certificado verificado y exige una respuesta JSON con `origin` o `ip` válido. Un puerto abierto o una página HTML no bastan. `--test-url` permite otro servicio con el mismo formato. Los proxies anteriores se vuelven a comprobar en cada ejecución.

## Resultados

### Pool histórico permanente

`history/pool.sqlite3` conserva todos los proxies descubiertos, aunque fallen o desaparezcan de las fuentes. `history/pool.csv` permite consultarlos en Excel. Ambos se guardan junto al archivo indicado con `--raw-out` (por defecto, en `proxy/history/`). SQLite se actualiza por transacciones y el CSV se reemplaza al terminar su escritura.

- `first_seen`: primera incorporación al pool, que nunca se sobrescribe.
- `last_seen`: última aparición en una fuente o lista de entrada; volver a validarlo no cambia esta fecha.
- `last_checked`: última comprobación completada.
- `last_valid`: última vez que funcionó, conservada aunque luego falle.
- `status`: resultado de la última comprobación (`valid`, `invalid` o `unverified`). No garantiza que siga funcionando ahora.
- `checks`: número de comprobaciones completadas.
- `date_basis`: `observed` para nuevos descubrimientos o `imported` para datos anteriores incorporados sin fecha original conocida.

Todas las fechas son UTC. Al crear un pool nuevo se importa la lista bruta anterior antes de reemplazarla, además de los válidos anteriores. Un pool existente no vuelve a importar la lista bruta en cada ejecución. Para esas entradas, la primera fecha es la de importación: no se inventa cuándo se descubrieron originalmente. Las comprobaciones interrumpidas no se registran como fallos.

En cada ejecución se comprueban los nuevos descubrimientos, los válidos anteriores y hasta 30.000 proxies históricos. Se priorizan los nunca comprobados y después los de comprobación más antigua. `--history-limit N` ajusta ese cupo; `--history-limit 0` omite la selección histórica y `--full-history` revisa todo el pool. Las categorías actuales contienen solo proxies verificados en esa ejecución. El histórico conserva el último estado de los demás.

Las rutas predeterminadas se resuelven junto al script, independientemente del directorio desde el que se ejecuta:

| Archivo o carpeta | Contenido |
| --- | --- |
| `results/candidates.txt` | Candidatos únicos, sin garantía de funcionamiento |
| `results/valid.txt` | Todos los proxies válidos con su esquema |
| `results/classified/proxies.csv` | Tabla para Excel con protocolo, IP, puerto, país, región, ciudad, coordenadas, ASN y proveedor |
| `results/classified/proxies.json` | Los mismos datos en formato estructurado |
| `results/classified/http.txt`, `socks5.txt`, etc. | Válidos por protocolo |
| `results/classified/countries/ES/http.txt` | Válidos por código de país y protocolo |
| `results/classified/providers/AS123/http.txt` | Válidos por ASN del proveedor y protocolo |

Las listas de categorías se regeneran, vaciando las que han dejado de tener proxies. Los CSV/JSON contienen únicamente resultados de la ejecución actual. El proveedor es la organización de red asociada al ASN de la IP del servidor proxy, no necesariamente quien vende el servicio. La ubicación es aproximada y corresponde a esa IP, no a una persona ni necesariamente a la IP de salida.

IPinfo aporta los metadatos. Los resultados correctos se cachean siete días; las consultas fallidas se reintentan en otra ejecución. Se consultan como máximo 1.000 IP nuevas o caducadas por ejecución. Si no hay datos, se informa `Unknown`; con `--no-geo` no se consulta ni utiliza la caché. La API pública tiene una cuota compartida, por lo que los metadatos no están garantizados. Opcionalmente se lee `IPINFO_TOKEN` del entorno; los campos disponibles dependen del plan. Referencias: [API](https://ipinfo.io/developers/core-api), [límites públicos](https://support.ipinfo.io/hc/en-us/articles/30792479436562-What-Is-the-Difference-Between-Using-the-Authenticated-Free-Plan-and-the-Public-API-With-No-Account).

`--sources` añade URLs a las fuentes incorporadas; `--input` omite todo el scraping. `--max-proxies` controla el tamaño de lote, no un límite total. Consulta el resto con `--help`. No se publica nada automáticamente salvo que se indique expresamente `--git`.

El lanzador `run_proxy_atlas.bat` ejecuta el mismo motor una vez; la periodicidad debe configurarse en el programador de tareas. Los descargadores, auditor y toolkits están en `../tools/`. Los datos antiguos de `archive/` se conservan como históricos y no son puntos de entrada.

## Pruebas

```sh
python -m unittest discover -s proxy -p test_proxy_atlas.py -v
```

Incluyen una ejecución real de la CLI con un servidor local controlado, rechazo de respuestas HTML, eliminación de proxies anteriores fallidos, deduplicación y regeneración de informes.

## Nombres y rendimiento

- `proxy_atlas.py`: motor y CLI de Proxy Atlas.
- `proxy_atlas.spec`: empaquetado del ejecutable.
- `run_proxy_atlas.bat`: lanzador de Windows.
- `test_proxy_atlas.py`: pruebas.
- `sources.txt`: fuentes adicionales.
- `logs/proxy_atlas.log`: registro de ejecución.
- `history/`: pool permanente, sin pérdida de fechas durante el cambio de nombre.
- `results/`: candidatos, válidos e informes clasificados.

SQLite selecciona el cupo histórico mediante un índice de fecha de comprobación. No se carga todo el pool en memoria para una ejecución normal. Los lotes se crean bajo demanda; las fuentes se deduplican por URL. El CSV histórico se exporta una vez por ejecución, sin ordenar el millón de filas; puede tardar unos segundos y SQLite es la fuente persistente principal.

```sh
python proxy/proxy_atlas.py --history-limit 5000
python proxy/proxy_atlas.py --full-history
```

Se han renombrado los archivos y actualizado los lanzadores del repositorio. Si tienes tareas programadas externas, actualiza su comando a `proxy_atlas.py` o `run_proxy_atlas.bat`. Los archivos de `archive/` son datos heredados, no resultados de Proxy Atlas.
