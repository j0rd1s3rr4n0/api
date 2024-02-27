#!/bin/bash

# Ruta al archivo Python
python_script="getProxy.py"

# Verificar si el archivo Python existe
if [ -f "$python_script" ]; then
    # Ejecutar el script Python
    python "$python_script"
else
    echo "Error: El archivo $python_script no existe."
fi

