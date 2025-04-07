import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import subprocess
import random

# CONFIGURACIÓN
PROXY_FILE = 'proxies.txt'
VALID_FILE = 'http.txt'  # antes era 'valid_proxies.txt'
URL_TEST = 'http://httpbin.org/ip'
TIMEOUT = 5
MAX_WORKERS = 20

# CONTADORES
total = 0
exitosos = 0
fallidos = 0

# Lista para almacenar los válidos
proxies_validos = []

def probar_proxy(proxy):
    global exitosos, fallidos
    proxies = {
        "http": f"http://{proxy}",
        "https": f"http://{proxy}"
    }
    try:
        response = requests.get(URL_TEST, proxies=proxies, timeout=TIMEOUT)
        if response.status_code == 200:
            print(f"[✓] Proxy válido: {proxy} | IP detectada: {response.json().get('origin')}")
            exitosos += 1
            proxies_validos.append(proxy)
        else:
            fallidos += 1
    except Exception:
        fallidos += 1
        print(f"[X] Proxy inválido: {proxy}")

def guardar_proxies_validos():
    # Mezclar antes de guardar
    random.shuffle(proxies_validos)
    with open(VALID_FILE, 'w') as f:
        for proxy in proxies_validos:
            f.write(proxy + '\n')
    print(f"\n💾 Proxies válidos mezclados y guardados en '{VALID_FILE}'")

def hacer_push_git():
    try:
        subprocess.run(["git", "add", VALID_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "Actualización de proxies válidos"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("🚀 Cambios subidos a GitHub correctamente.")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Error al hacer push a GitHub: {e}")

def main():
    global total
    try:
        with open(PROXY_FILE, 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"❌ Archivo '{PROXY_FILE}' no encontrado.")
        return

    total = len(proxies)
    print(f"\n📦 Total de proxies a probar: {total}\n")

    start = datetime.now()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        executor.map(probar_proxy, proxies)

    end = datetime.now()
    duracion = end - start

    print("\n📊 RESULTADOS")
    print("------------")
    print(f"✓ Válidos:   {exitosos}")
    print(f"✗ Inválidos: {fallidos}")
    print(f"⏱ Tiempo:    {duracion.total_seconds():.2f} segundos")

    if proxies_validos:
        guardar_proxies_validos()
        hacer_push_git()
    else:
        print("\n⚠️ No se encontraron proxies válidos. Nada que subir a GitHub.")

if __name__ == '__main__':
    main()
