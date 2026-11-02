# Proxy Atlas Go Checker

Motor de validación complementario de Proxy Atlas. Python conserva el scraping, SQLite, geolocalización, categorías e informes; este ejecutable comprueba los proxies. No duplica ni reemplaza el pool histórico.

## Compilar y probar

Requiere Go 1.22 o posterior. Solo utiliza la biblioteca estándar, sin módulos externos.

```powershell
cd proxy/golang_checker
go test ./...
go vet ./...
go build -trimpath -o proxy_checker.exe .
```

En Linux/macOS, usa `-o proxy_checker`.

El ejecutable compilado no necesita Go instalado para ejecutarse. `proxy_checker.exe` se ha compilado y probado en Windows; es un artefacto local excluido de Git.

Desde la raíz del repositorio:

```powershell
python proxy/proxy_atlas.py --engine go --threads 128
python proxy/proxy_atlas.py --engine go --input mi_lista.txt --history-limit 0
```

`--go-checker RUTA` permite usar otro ejecutable. `--threads` controla el total de comprobaciones Go concurrentes; `--processes` solo afecta al motor Python. Python sigue siendo el motor predeterminado. Una interrupción o respuesta incompleta de Go no cambia el estado histórico del lote afectado.

## Uso independiente

```powershell
.\proxy_checker.exe -input ..\results\candidates.txt -output checks.jsonl -workers 128 -timeout 5s
.\proxy_checker.exe -input ..\results\candidates.txt -output valid.txt -format txt
```

La entrada admite una URL por línea o `IP:puerto` (HTTP), líneas vacías y comentarios `#`. Los protocolos son HTTP, HTTPS, SOCKS4/4a y SOCKS5/5h. No admite credenciales. Conserva duplicados de entrada para procesar el flujo con memoria acotada; Proxy Atlas realiza la deduplicación antes de invocarlo.

JSONL contiene un resultado por candidato: `proxy`, `valid`, `latency_ms` y `error` cuando falla. El orden es el de finalización, no el de entrada. `-format txt` emite únicamente URLs normalizadas que superan la prueba. Sin archivos, lee stdin y escribe stdout. Los errores operativos se escriben en stderr y devuelven un código distinto de cero. Los archivos se escriben primero en un temporal junto al destino y se reemplazan solo tras completar el trabajo.

## Validación y rendimiento

Como Python, exige HTTP 200 y JSON con `origin` o `ip`, que contenga una IP válida o varias separadas por comas. Rechaza redirecciones, HTML, TLS sin confianza y cuerpos de más de 64 KiB. SOCKS4/5 resuelven el destino localmente; SOCKS4a/5h lo delegan al proxy. `https://` indica TLS hasta el servidor proxy.

Usa trabajadores y colas limitados, lectura progresiva y una única conexión de validación por candidato. Evita crear procesos de validación y evita el sondeo TCP adicional del motor Python. Esto reduce trabajo y limita memoria; la mejora de velocidad real depende de la red y debe medirse con el mismo conjunto de proxies.

Una diferencia deliberada: `-timeout` es el plazo total del chequeo, incluido el cuerpo. El timeout HTTP de Requests limita esperas de conexión/lectura, no necesariamente el tiempo total. Por eso un proxy muy lento podría producir resultados distintos. Go también limita las cabeceras a 16 KiB. Los timeouts de conexión y de negociación SOCKS/TLS se controlan con `-connect-timeout`.

Las pruebas cubren las cuatro variantes SOCKS, DNS delegado, TLS no confiable, respuestas inválidas, tamaño de cuerpo, plazos y límite de concurrencia. La integración Python permite ejecutar su prueba CLI con el motor compilado estableciendo `PROXY_ATLAS_TEST_ENGINE=go` antes de ejecutar `python -m unittest discover -s proxy -p test_proxy_atlas.py -v` desde la raíz.

Referencias: [net/http](https://pkg.go.dev/net/http), [context](https://pkg.go.dev/context).

## Comprobación local de rendimiento

En una ejecución de control del 1 de noviembre de 2026, con 200 comprobaciones repetidas contra un servidor HTTP local, 16 trabajadores y timeout de 5 segundos, ambos motores validaron las 200 entradas. Python empleó 0,448 s y abrió 400 conexiones (sondeo y solicitud); Go empleó 0,136 s, incluido el arranque del ejecutable, y abrió 200. Es una medición local puntual de la sobrecarga del validador, no una estimación de velocidad sobre proxies públicos ni del scraping completo.
