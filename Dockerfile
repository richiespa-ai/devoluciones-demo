FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY static ./static

# Usuario sin privilegios: si alguien encontrara un fallo, no tendría permisos de administrador en el contenedor
RUN useradd --create-home appuser && mkdir -p data && chown appuser data
USER appuser

# La base de datos de demo se genera sola en el primer arranque
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
