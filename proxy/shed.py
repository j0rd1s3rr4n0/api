"""
Este script programa la ejecución de un archivo (getProxy.exe o getProxy.py)
a intervalos regulares especificados por el usuario o por defecto cada 5 minutos.

Uso:
    python main.py --every [minutos]

Argumentos:
    --every [minutos]: Intervalo en minutos para ejecutar el archivo. 
                       Si no se proporciona, se usa un intervalo de 5 minutos.
"""

import schedule
import time
import subprocess
import os
import sys

def ejecutar_main():
    """
    Ejecuta 'getProxy.exe' si existe, de lo contrario, ejecuta 'getProxy.py'.

    Maneja errores de archivo no encontrado y errores de ejecución del subproceso.
    """
    try:
        if os.path.exists("2getProxy.exe"):
            subprocess.run(["getProxy.exe"], check=True)
        else:
            subprocess.run(["getProxy.py"], check=True)
    except FileNotFoundError as e:
        print(f"Error: archivo no encontrado - {e}")
    except subprocess.CalledProcessError as e:
        print(f"Error: fallo en la ejecución del subproceso - {e}")
    except Exception as e:
        print(f"Error inesperado: {e}")

def obtener_intervalo():
    """
    Obtiene el intervalo de ejecución en minutos desde los argumentos de la línea de comandos.

    Retorna:
        int: El intervalo de ejecución en minutos.
    
    Maneja errores de índice y conversión de tipo de los argumentos.
    """
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--every":
            return int(sys.argv[2])
        else:
            return 5
    except (IndexError, ValueError) as e:
        print(f"Error en los argumentos: {e}")
        return 5

def main():
    """
    Configura la programación de la tarea y ejecuta la primera instancia de inmediato.
    Luego, entra en un bucle infinito para ejecutar la tarea según el intervalo programado.
    """
    minutos = obtener_intervalo()

    # Programar la ejecución de main.py cada n minutos
    schedule.every(minutos).minutes.do(ejecutar_main)

    # Primera ejecución
    ejecutar_main()

    # Loop de ejecución
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            print("Ejecución interrumpida por el usuario.")
            break
        except Exception as e:
            print(f"Error en el loop principal: {e}")

if __name__ == "__main__":
    main()
