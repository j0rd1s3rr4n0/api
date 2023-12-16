import schedule
import time
import subprocess

def ejecutar_main():
    subprocess.run(["python", "getProxy.py"])

# Programar la ejecución de main.py cada 2 minutos
schedule.every(1).minutes.do(ejecutar_main)

while True:
    schedule.run_pending()
    time.sleep(1)
