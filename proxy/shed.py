import schedule
import time
import subprocess
import os

contador = 0

def ejecutar_main():
    global contador
    contador+=1
    os.system('title Contador: '+str(contador))
    subprocess.run(["python", "getProxy.py"])

# Programar la ejecución de main.py cada 2 minutos
schedule.every(5).minutes.do(ejecutar_main)
ejecutar_main()
while True:
    time.sleep(1)
    schedule.run_pending()
    time.sleep(1)
