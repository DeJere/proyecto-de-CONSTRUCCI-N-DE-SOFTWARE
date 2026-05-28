FROM python:3.11-slim

# Evita que Python genere archivos .pyc y asegura que los logs salgan a la consola
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalamos las dependencias necesarias
RUN pip install --no-cache-dir fastapi uvicorn pinotdb requests

# Copiamos los archivos necesarios al contenedor
COPY main.py .
COPY index.html .

EXPOSE 8000

# Ejecutamos uvicorn. 
# Usamos 0.0.0.0 para que el puerto sea accesible desde fuera del contenedor.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]