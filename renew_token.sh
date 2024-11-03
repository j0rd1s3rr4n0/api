#!/bin/bash

# Solicitar el token al usuario de forma segura
read -sp "Introduce tu token de GitHub: " token
echo -e "\n"

# Directorio de errores
error_log="/var/api/proxy/errors.log"

# Remover el origen anterior si existe
echo "Eliminando origen anterior..."
git remote remove origin 2>>"$error_log" && echo "Origen anterior eliminado." || echo "No se encontró un origen previo o hubo un error."

# Agregar el nuevo origen con el token
echo "Agregando nuevo origen..."
git remote add origin https://"$token"@github.com/j0rd1s3rr4n0/api.git 2>>"$error_log"
if [ $? -eq 0 ]; then
    echo "Origen agregado con éxito."
else
    echo "Error al agregar el origen. Revisa el archivo de registro de errores en $error_log."
    exit 1
fi

# Hacer el primer push a la rama principal
echo "Subiendo cambios a la rama 'main'..."
git push origin main 2>>"$error_log"
if [ $? -eq 0 ]; then
    echo "Cambios subidos correctamente a la rama 'main'."
else
    echo "Error al subir los cambios a la rama 'main'. Revisa el archivo de registro de errores en $error_log."
    exit 1
fi

# Configurar la rama principal como upstream
echo "Configurando la rama 'main' como upstream..."
git push --set-upstream origin main 2>>"$error_log"
if [ $? -eq 0 ]; then
    echo "Rama 'main' configurada como upstream correctamente."
else
    echo "Error al configurar la rama 'main' como upstream. Revisa el archivo de registro de errores en $error_log."
fi

echo -e "\nProceso completado."
