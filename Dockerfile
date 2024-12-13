# Usa una imagen base ligera de Python
FROM python:3.12-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia el archivo requirements.txt al contenedor
COPY requirements.txt /app/requirements.txt

# Instala las dependencias desde requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copia todos los archivos de tu proyecto al contenedor
COPY . /app

# Expone el puerto predeterminado de Uvicorn
EXPOSE 8000

# Comando para iniciar la aplicación
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
