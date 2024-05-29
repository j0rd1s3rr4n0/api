#!/bin/bash

# Ruta al archivo Python
python_script="/var/api/proxy/getProxy.py"

# Ruta del archivo de log para errores
error_log="/var/api/proxy/errors.log"

# Establecer el directorio de trabajo a /var/api/proxy
cd /var/api/proxy

# Verificar si el archivo Python existe
if [ -f "$python_script" ]; then
    # Ejecutar el script Python y redirigir errores
    python3 "$python_script" 2>> "$error_log"
else
    echo "Error: El archivo $python_script no existe." >> "$error_log"
fi
