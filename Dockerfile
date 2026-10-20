FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -m app
COPY moxfield.py api.py ./
COPY static ./static
USER app
ENV PORT=8000
# --proxy-headers: Render va detrás de un proxy; así el límite por IP usa la IP real del cliente
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
