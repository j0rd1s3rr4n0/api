#!/bin/bash

# Ruta al archivo Python
python_script="/var/api/proxy/getProxy.py"

# Ruta del archivo de log para errores
error_log="/var/api/proxy/errors.log"

# Establecer el directorio de trabajo a /var/api/proxy
cd /var/api/proxy

# Establecer virtualenv
source /var/api/venv/bin/activate

# Verificar si el archivo Python existe
if [ -f "$python_script" ]; then
    # Verificar si el archivo 'running' ya existe
    if [ -f "running" ]; then
        echo "El script ya está en ejecución."
    else
        # Crear el archivo 'running'
        touch running
        # Ejecutar el script Python y redirigir errores
        python3 "$python_script" 2>> "$error_log"
        # Eliminar el archivo 'running'
        rm running
    fi
else
    echo "Error: El archivo $python_script no existe." >> "$error_log"
fi

