import requests
import re
import os
import base64
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from threading import Lock
from requests.packages.urllib3.util.retry import Retry
import time
import logging

lock = Lock()
logger = logging.getLogger(__name__)

def commit_push_y_borrar_archivos():
    try:
        # Hacer commit de http.txt
        subprocess.run(["git", "add", "http.txt"])
        subprocess.run(["git", "commit", "-m", f"Update proxyList {str(time.asctime())}"])
        # Hacer push
        subprocess.run(["git", "push"])
        # Eliminar http_proxies.txt
        os.remove("http_proxies.txt")
        logger.info("Archivo http_proxies.txt eliminado.")
        # Renombrar http.txt a http_proxies.txt
        os.rename("http.txt", "http_proxies.txt")
        logger.info("Archivo http.txt renombrado a http_proxies.txt.")
        logger.info("Commit y push completados.")
    except Exception as e:
        logger.error(f"Error al realizar el commit, push y borrar archivos: {e}")

def create_session():
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def obtener_proxies_from_url(url, pattern):
    try:
        response = session.get(url)
        if response.status_code == 200:
            proxies = re.findall(pattern, response.text)
            return proxies
        else:
            logger.error(f"Error al obtener proxies de {url}. Código de estado: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error al realizar la solicitud a {url}: {e}")
        return []

def obtener_proxies_proxy_daily():
    url = "https://proxy-daily.com"
    pattern = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\:[0-9]+\b')
    return obtener_proxies_from_url(url, pattern)

def guardar_en_archivo(ip_port):
    archivo_path = "http_proxies.txt"
    with lock:
        with open(archivo_path, "a") as archivo:
            archivo.write(ip_port + "\n")

def realizar_solicitudes_concurrentes(max_intentos=2):
    intentos = 0
    protocolo_http_encontrado = False

    with ThreadPoolExecutor(max_workers=os.cpu_count() or 1) as executor:
        while intentos < max_intentos:
            intentos += 1
            try:
                sources = [
                    obtener_proxies_proxy_daily
                ]

                for source in sources:
                    proxies = source()
                    for proxy in proxies:
                        guardar_en_archivo(proxy)
                        logger.info(f"Intento {intentos}: Proxy encontrado: {proxy}")

                        if "http" in proxy.lower():
                            protocolo_http_encontrado = True

                if protocolo_http_encontrado:
                    break
            except Exception as e:
                logger.error(f"Error al obtener proxies: {e}")

    logger.info("Fin del programa")

    archivo_entrada = "http_proxies.txt"
    archivo_salida = "http.txt"
    eliminar_duplicados(archivo_entrada, archivo_salida)

def eliminar_duplicados(archivo_entrada, archivo_salida):
    try:
        with open(archivo_entrada, 'r') as entrada, open(archivo_salida, 'w') as salida:
            lineas = set(entrada.readlines())
            salida.writelines(sorted(lineas))
        logger.info(f"Duplicados eliminados. Resultado guardado en {archivo_salida}")
    except Exception as e:
        logger.error(f"Error: {e}")

def main():
    logging.basicConfig(filename='proxy.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    global session
    session = create_session()
    realizar_solicitudes_concurrentes()
    commit_push_y_borrar_archivos()

if __name__ == "__main__":
    main()
