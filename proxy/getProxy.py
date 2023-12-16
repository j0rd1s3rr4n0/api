import requests
import re
import os
import base64
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

lock = Lock()
def commit_push_y_borrar_archivos():
    try:
        # Hacer commit de todos los cambios
        subprocess.run(["git", "add", "."])
        subprocess.run(["git", "commit", "-m", "Update proxyList"])

        # Hacer push
        subprocess.run(["git", "push"])

        # Eliminar http_proxies.txt
        os.remove("http_proxies.txt")
        print("Archivo http_proxies.txt eliminado.")

        # Renombrar http.txt a http_proxies.txt
        os.rename("http.txt", "http_proxies.txt")
        print("Archivo http.txt renombrado a http_proxies.txt.")

        # Hacer commit para reflejar los cambios de eliminar y renombrar
        subprocess.run(["git", "add", "."])
        subprocess.run(["git", "commit", "-m", "Update proxyList - Clean up"])

        print("Commit, push y limpieza completados.")
    except Exception as e:
        print(f"Error al realizar el commit, push y borrar archivos: {e}")
def obtener_proxy_gimmeproxy():
    # Función para obtener un proxy de gimmeproxy.com
    url = "https://gimmeproxy.com/api/getProxy"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error al obtener el proxy de gimmeproxy.com. Código de estado: {response.status_code}")
        return None

def obtener_proxies_free_proxy_list():
    # Función para obtener proxies de free-proxy-list.net
    url = "https://free-proxy-list.net"
    response = requests.get(url)
    if response.status_code == 200:
        pattern = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\:[0-9]+\b')
        proxies = re.findall(pattern, response.text)
        return proxies
    else:
        print(f"Error al obtener proxies de free-proxy-list.net. Código de estado: {response.status_code}")
        return []

def obtener_proxies_hidemylife():
    # Función para obtener proxies de hidemy.life
    url = "https://hidemy.life/en/proxy-list-servers"
    response = requests.get(url)
    if response.status_code == 200:
        pattern = re.compile(r'<tr><td>([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)<\/td><td>([0-9]+)<\/td>')
        proxies = re.findall(pattern, response.text)
        return [f"{ip}:{puerto}" for ip, puerto in proxies]
    else:
        print(f"Error al obtener proxies de hidemy.life. Código de estado: {response.status_code}")
        return []

def obtener_proxies_proxylist_org(page_number):
    # Función para obtener proxies de proxy-list.org
    url = f"https://proxy-list.org/spanish/index.php?p={page_number}"
    response = requests.get(url)
    if response.status_code == 200:
        pattern = re.compile(r"Proxy\('([^']+)'\)")
        proxies_base64 = re.findall(pattern, response.text)
        decoded_proxies = [base64.b64decode(proxy).decode("utf-8") for proxy in proxies_base64]
        valid_proxies = [proxy for proxy in decoded_proxies if re.match(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\:[0-9]+\b', proxy)]
        return valid_proxies
    else:
        print(f"Error al obtener proxies de proxy-list.org. Código de estado: {response.status_code}")
        return []

def obtener_proxies_iplocation_net(page_number):
    # Función para obtener proxies de iplocation.net
    url = f"https://www.iplocation.net/proxy-list/index/{page_number}"
    response = requests.get(url)
    if response.status_code == 200:
        pattern = re.compile(r'<tr>\s+<td><a[^>]+>([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)<\/a><\/td>\s+<td>([0-9]+)<\/td>\s+<td>([0-9]+)<\/td>')
        proxies = re.findall(pattern, response.text)
        return [f"{ip}:{puerto}" for ip, puerto, _ in proxies]
    else:
        print(f"Error al obtener proxies de iplocation.net. Código de estado: {response.status_code}")
        return []

def obtener_proxies_proxy_daily():
    # Función para obtener proxies de proxy-daily.com
    url = "https://proxy-daily.com"
    response = requests.get(url)
    if response.status_code == 200:
        pattern = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\:[0-9]+\b')
        proxies = re.findall(pattern, response.text)
        return proxies
    else:
        print(f"Error al obtener proxies de proxy-daily.com. Código de estado: {response.status_code}")
        return []

def guardar_en_archivo(ip_port):
    # Función para guardar la dirección en un archivo
    archivo_path = "http_proxies.txt"
    with lock:
        with open(archivo_path, "a") as archivo:
            archivo.write(ip_port + "\n")
        #print(f"La dirección {ip_port} se ha guardado en el archivo {archivo_path}")

def realizar_solicitudes_concurrentes(max_intentos=10):
    # Función principal para realizar solicitudes concurrentes
    intentos = 0
    protocolo_http_encontrado = False

    with ThreadPoolExecutor(max_workers=os.cpu_count() or 1) as executor:
        while intentos < max_intentos:
            intentos += 1
            gimmeproxy_future = executor.submit(obtener_proxy_gimmeproxy)
            gimmeproxy_proxy = gimmeproxy_future.result()

            for i in range(10):
                if gimmeproxy_proxy:
                    protocolo = gimmeproxy_proxy.get("protocol", "")
                    ip_port = gimmeproxy_proxy.get("ipPort", "")

                    if protocolo.lower() == "http":
                        protocolo_http_encontrado = True
                        guardar_en_archivo(ip_port)
                        print(f"Intento {intentos}: Proxy con protocolo HTTP encontrado en gimmeproxy.com.")
                    else:
                        print(f"Intento {intentos}: Proxy con protocolo {protocolo} en gimmeproxy.com. Buscando protocolo HTTP.")

                    if "json" not in gimmeproxy_proxy.get("type", "").lower():
                        break  # Salir del bucle si no se recibe un JSON

            free_proxy_list_future = executor.submit(obtener_proxies_free_proxy_list)
            hidemylife_future = executor.submit(obtener_proxies_hidemylife)
            proxylist_org_futures = [executor.submit(obtener_proxies_proxylist_org, page_number) for page_number in range(1, 11)]
            iplocation_net_futures = [executor.submit(obtener_proxies_iplocation_net, page_number) for page_number in range(1, 41)]
            proxy_daily_future = executor.submit(obtener_proxies_proxy_daily)

            free_proxy_list_proxies = free_proxy_list_future.result()
            hidemylife_proxies = hidemylife_future.result()
            proxylist_org_proxies = [proxy for future in as_completed(proxylist_org_futures) for proxy in future.result()]
            iplocation_net_proxies = [proxy for future in as_completed(iplocation_net_futures) for proxy in future.result()]
            proxy_daily_proxies = proxy_daily_future.result()

            for proxy in free_proxy_list_proxies:
                guardar_en_archivo(proxy)
                print(f"Proxy encontrado en free-proxy-list.net: {proxy}")

            for proxy in hidemylife_proxies:
                guardar_en_archivo(proxy)
                print(f"Proxy encontrado en hidemy.life: {proxy}")

            for proxy in proxylist_org_proxies:
                guardar_en_archivo(proxy)
                print(f"Proxy encontrado en proxy-list.org: {proxy}")

            for proxy in iplocation_net_proxies:
                guardar_en_archivo(proxy)
                print(f"Proxy encontrado en iplocation.net: {proxy}")

            for proxy in proxy_daily_proxies:
                guardar_en_archivo(proxy)
                print(f"Proxy encontrado en proxy-daily.com: {proxy}")

    print("Fin del programa")

    # Eliminar duplicados al final del script
    archivo_entrada = "http_proxies.txt"
    archivo_salida = "http.txt"
    eliminar_duplicados(archivo_entrada, archivo_salida)

def eliminar_duplicados(archivo_entrada, archivo_salida):
    try:
        with open(archivo_entrada, 'r') as entrada, open(archivo_salida, 'a') as salida:
            lineas = set(entrada.readlines())
            salida.writelines(sorted(lineas))
        print(f"Duplicados eliminados. Resultado guardado en {archivo_salida}")
    except Exception as e:
        print(f"Error: {e}")

def main():
    realizar_solicitudes_concurrentes()
    # Después de realizar las solicitudes y guardar en http.txt
    commit_push_y_borrar_archivos()

if __name__ == "__main__":
    main()
