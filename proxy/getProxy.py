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
import warnings
from urllib3.exceptions import InsecureRequestWarning
from colorama import Fore, Style
lock = Lock()

def commit_push_y_borrar_archivos():
    try:
        # Hacer commit de http.txt
        subprocess.run(["git", "add", "http.txt"])
        subprocess.run(["git", "commit", "-m", f"Update proxyList {str(time.asctime())}"])
        # Hacer push
        subprocess.run(["git", "push"])
        # Eliminar http_proxies.txt
        os.remove("http_proxies.txt")
        print("Archivo http_proxies.txt eliminado.")
        # Renombrar http.txt a http_proxies.txt
        os.rename("http.txt", "http_proxies.txt")
        print("Archivo http.txt renombrado a http_proxies.txt.")
        print("Commit y push completados.")
    except Exception as e:
        print(f"Error al realizar el commit, push y borrar archivos: {e}")
def create_session():
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def obtener_proxies_from_url(url, pattern):
    response = session.get(url)
    if response.status_code == 200:
        proxies = re.findall(pattern, response.text)
        return proxies
    else:
        print(f"Error al obtener proxies de {url}. Código de estado: {response.status_code}")
        return []

def obtener_proxies_gimmeproxy():
    url = "https://gimmeproxy.com/api/getProxy"
    response = session.get(url)
    if response.status_code == 200:
        proxy = response.json()
        return [f"{proxy['ipPort']}"]
    else:
        print(f"Error al obtener proxy de gimmeproxy.com. Código de estado: {response.status_code}")
        return []

def obtener_proxies_free_proxy_list():
    url = "https://free-proxy-list.net"
    pattern = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\:[0-9]+\b')
    return obtener_proxies_from_url(url, pattern)

def obtener_proxies_hidemylife():
    url = "https://hidemy.life/en/proxy-list-servers"
    pattern = re.compile(r'<tr><td>([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)<\/td><td>([0-9]+)<\/td>')
    proxies = obtener_proxies_from_url(url, pattern)
    return [f"{ip}:{puerto}" for ip, puerto in proxies]

def obtener_proxies_proxylist_org(page_number):
    url = f"https://proxy-list.org/spanish/index.php?p={page_number}"
    pattern = re.compile(r"Proxy\('([^']+)'\)")
    proxies_base64 = obtener_proxies_from_url(url, pattern)
    decoded_proxies = [base64.b64decode(proxy).decode("utf-8") for proxy in proxies_base64]
    valid_proxies = [proxy for proxy in decoded_proxies if re.match(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\:[0-9]+\b', proxy)]
    return valid_proxies

def obtener_proxies_iplocation_net(page_number):
    url = f"https://www.iplocation.net/proxy-list/index/{page_number}"
    pattern = re.compile(r'<tr>\s+<td><a[^>]+>([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)<\/a><\/td>\s+<td>([0-9]+)<\/td>\s+<td>([0-9]+)<\/td>')
    proxies = obtener_proxies_from_url(url, pattern)
    return [f"{ip}:{puerto}" for ip, puerto, _ in proxies]

def obtener_proxies_freeproxylistcc(page_number):
    url = f"https://freeproxylist.cc/servers/{page_number}.html"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            html = response.text
            lista_ips_puertos = []

            # Expresión regular para encontrar las direcciones IP y los puertos dentro de las etiquetas <td>
            patron = r'<td>\s*([\d\.]+)\s*</td>\s*<td>\s*(\d+)\s*</td>'
            matches = re.findall(patron, html)

            # Itera sobre los matches encontrados y forma la lista de ip:puerto
            for match in matches:
                ip = match[0]
                puerto = match[1]
                lista_ips_puertos.append(f"{ip}:{puerto}")

            return lista_ips_puertos
        else:
            print(f"Error al obtener la respuesta FreeProxyListCc : {response.status_code}")
            return []
    except Exception as e:
        print(f"Error al hacer la solicitud FreeProxyListCc")
        return []

def obtener_proxies_limuproxy(page_number):
    url = f"https://api.lumiproxy.com/web_v1/free-proxy/list?page_size=100&page={page_number}&protocol=2&language=en-us"  # Reemplaza esto con la URL real
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            lista_ips_puertos = []
            for item in data["data"]["list"]:
                ip = item["ip"]
                port = item["port"]
                lista_ips_puertos.append(f"{ip}:{port}")
            return lista_ips_puertos
        else:
            print(f"Error al obtener la respuesta LumiProxy. Código de estado: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error al hacer la solicitud LumiProxy")
        return []

def obtener_proxies_proxy_scrape():
    url = "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text"
    pattern = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\:[0-9]+\b')
    return obtener_proxies_from_url(url, pattern)

def obtener_proxies_proxylistdownload():
    url = "https://www.proxy-list.download/HTTP"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            html = response.text
            lista_ips_puertos = []

            # Expresión regular para encontrar las direcciones IP y los puertos dentro de las etiquetas <td>
            patron = r'<td>\s*([\d\.]+)\s*</td>\s*<td>\s*(\d+)\s*</td>'
            matches = re.findall(patron, html)

            # Itera sobre los matches encontrados y forma la lista de ip:puerto
            for match in matches:
                ip = match[0]
                puerto = match[1]
                lista_ips_puertos.append(f"{ip}:{puerto}")

            return lista_ips_puertos
        else:
            print(f"Error al obtener la respuesta ProxyListDownload : {response.status_code}")
            return []
    except Exception as e:
        print(f"Error al hacer la solicitud ProxyListDownload")
        return []

# Domain not found
def obtener_proxies_proxy_daily():
    url = "https://proxy-daily.com"
    pattern = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\:[0-9]+\b')
    return obtener_proxies_from_url(url, pattern)

"""
def obtener_proxies_premprxy(page_number):
    url = f"https://premproxy.com/list/ip-port/{page_number}.htm"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            lista_ips_puertos = []
            for item in data["data"]["list"]:
                ip = item["ip"]
                port = item["port"]
                lista_ips_puertos.append(f"{ip}:{port}")
            return lista_ips_puertos
        else:
            print(f"Error al obtener la respuesta LumiProxy. Código de estado: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error al hacer la solicitud LumiProxy")
        return []
"""

# WAF Enabled
def obtener_proxies_smallseotools():
    url = "https://smallseotools.com/free-proxy-list/"
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

            sources = [
                obtener_proxies_gimmeproxy,
                obtener_proxies_free_proxy_list,
                obtener_proxies_hidemylife,
                lambda: [proxy for future in as_completed(executor.submit(obtener_proxies_proxylist_org, page_number) for page_number in range(1, 11)) for proxy in future.result()],
                lambda: [proxy for future in as_completed(executor.submit(obtener_proxies_freeproxylistcc, page_number) for page_number in range(1, 11)) for proxy in future.result()],
                lambda: [proxy for future in as_completed(executor.submit(obtener_proxies_iplocation_net, page_number) for page_number in range(1, 41)) for proxy in future.result()],
                lambda: [proxy for future in as_completed(executor.submit(obtener_proxies_limuproxy, page_number) for page_number in range(1, 41)) for proxy in future.result()],
                obtener_proxies_proxy_scrape,
                obtener_proxies_proxylistdownload,
                #obtener_proxies_proxy_daily,
                #obtener_proxies_smallseotools,
            ]

            for source in sources:
                proxies = source()
                for proxy in proxies:
                    guardar_en_archivo(proxy)
                    warnings.filterwarnings("ignore", category=InsecureRequestWarning)
                    # Geolocate Proxy
                    geo = requests.get(f"http://freeipapi.com/api/json/{proxy.split(':')[0]}", timeout=0.5, verify=False)
                    if(geo.status_code == 200):
                        geo = geo.json()
                        # Check if the proxy is Up and print the country, region and city
                        try:
                            response = requests.get("http://httpbin.org/ip", proxies={"http": f"http://{proxy}","https": f"https://{proxy}"}, timeout=0.1, verify=False)
                            if response.status_code == 200:
                                protocolo_http_encontrado = True
                        except Exception as e:
                            geo = {"countryCode": "N/A", "regionName": "N/A", "cityName": "N/A"}
                    else:
                        geo = {"countryCode": "N/A", "regionName": "N/A", "cityName": "N/A"}
                    country_code = geo.get("countryCode")
                    location = geo.get("regionName")
                    city = geo.get("cityName")
                    geo_info = "[{}, {}, {}]".format(country_code, location, city)
                    
                    print(f"{Fore.CYAN}[{intentos}]{Style.RESET_ALL}{Fore.MAGENTA} Proxy Found:{Style.RESET_ALL} {Fore.RED}{proxy.ljust(21)}{Style.RESET_ALL} - {Fore.BLUE}{geo_info.ljust(50)}{Style.RESET_ALL} - {Fore.YELLOW}{time.strftime('%d/%m/%Y %H:%M:%S')}{Style.RESET_ALL}") 
                    # print(f"[] Proxy encontrado: {proxy.ljust(21)} - {geo_info.ljust(35)}")
                    #print(f"[{intentos}] Proxy encontrado: {proxy}")

                    
            if protocolo_http_encontrado:
                break

    print("Fin del programa")

    archivo_entrada = "http_proxies.txt"
    archivo_salida = "http.txt"
    eliminar_duplicados(archivo_entrada, archivo_salida)

def eliminar_duplicados(archivo_entrada, archivo_salida):
    try:
        with open(archivo_entrada, 'r') as entrada, open(archivo_salida, 'w') as salida:
            lineas = set(entrada.readlines())
            salida.writelines(sorted(lineas))
        print(f"Duplicados eliminados. Resultado guardado en {archivo_salida}")
    except Exception as e:
        print(f"Error: {e}")

def main():
    global session
    session = create_session()
    realizar_solicitudes_concurrentes()
    commit_push_y_borrar_archivos()

if __name__ == "__main__":
    main()
