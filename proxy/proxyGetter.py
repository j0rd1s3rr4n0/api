import requests
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import socket

# Crear una sesión con headers personalizados
def create_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })
    return session

# Extraer IPs y puertos válidos del contenido HTML
def extraer_ips_y_puertos(contenido):
    proxies = set()
    if isinstance(contenido, bytes):
        contenido = contenido.decode("utf-8", errors="ignore")

    patron = re.compile(r'(?:(?:http|https|socks4|socks5)://)?(?:(?:\d{1,3}\.){3}\d{1,3}):\d+')
    encontrados = patron.findall(contenido)
    for proxy in encontrados:
        if "://" in proxy:
            proxy = proxy.split("://")[1]
        proxies.add(proxy.strip())
    return list(proxies)

# Obtener proxies desde una URL
def obtener_proxies_from_url(url, session):
    try:
        response = session.get(url, timeout=10)
        if response.status_code == 200:
            return extraer_ips_y_puertos(response.content)
    except Exception as e:
        print(f"[ERROR] No se pudo obtener proxies de {url}: {e}")
    return []

# Obtener proxies desde una fuente con múltiples URLs
def obtener_proxies_from_sources(urls, session):
    proxies = []
    for url in urls:
        proxies.extend(obtener_proxies_from_url(url, session))
    return proxies

# Definición de fuentes
sources = {
    "proxyscrape": lambda session: obtener_proxies_from_sources([
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=https&timeout=10000&country=all"
    ], session),

    "free-proxy-list": lambda session: obtener_proxies_from_url("https://free-proxy-list.net/", session),
    
    "sslproxies": lambda session: obtener_proxies_from_url("https://www.sslproxies.org/", session),
    
    "us-proxy": lambda session: obtener_proxies_from_url("https://www.us-proxy.org/", session),

    "openproxy": lambda session: obtener_proxies_from_sources([
        "https://openproxy.space/list/http",
        "https://openproxy.space/list/https",
        "https://openproxy.space/list/socks4",
        "https://openproxy.space/list/socks5"
    ], session),

    "proxy-list.download": lambda session: obtener_proxies_from_sources([
        "https://www.proxy-list.download/api/v1/get?type=http",
        "https://www.proxy-list.download/api/v1/get?type=https"
    ], session),

    "proxy-daily": lambda session: obtener_proxies_from_sources([
        "https://proxy-daily.com/",
        "https://free-proxy-list.net/anonymous-proxy.html"
    ], session)
}

# Guardar proxies únicos en un archivo
proxies_guardados = set()

def guardar_en_archivo(proxy):
    if proxy not in proxies_guardados:
        with open("proxies.txt", "a") as f:
            f.write(proxy + "\n")
        proxies_guardados.add(proxy)

# Comprobar si el proxy funciona correctamente
def comprobar_proxy(proxy):
    try:
        proxies = {
            "http": f"http://{proxy}",
            "https": f"http://{proxy}"
        }
        response = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=5)
        if response.status_code == 200:
            print(f"[OK] Proxy válido: {proxy}")
            guardar_en_archivo(proxy)
        else:
            print(f"[X] Proxy inválido: {proxy}")
    except Exception as e:
        print(f"[X] Error con proxy {proxy}: {e}")

# Ejecutar solicitudes en paralelo
def realizar_solicitudes_concurrentes(proxies, max_workers=50):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(comprobar_proxy, proxies)

# Punto de entrada
if __name__ == "__main__":
    session = create_session()
    todos_los_proxies = []

    for nombre, funcion in sources.items():
        try:
            proxies = funcion(session)
            print(f"[INFO] {nombre} -> {len(proxies)} proxies encontrados")
            todos_los_proxies.extend(proxies)
        except Exception as e:
            print(f"[ERROR] Fuente {nombre} falló: {e}")

    print(f"[INFO] Total de proxies antes de filtrar: {len(todos_los_proxies)}")
    todos_los_proxies = list(set(todos_los_proxies))  # Eliminar duplicados

    print(f"[INFO] Total de proxies únicos: {len(todos_los_proxies)}")
    print("[INFO] Comprobando validez de los proxies...")

    realizar_solicitudes_concurrentes(todos_los_proxies)
