FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y curl ca-certificates unixodbc && \
    curl -fsSL https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb -o /tmp/packages.deb && \
    dpkg -i /tmp/packages.deb && apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql18 && \
    rm -rf /var/lib/apt/lists/* /tmp/packages.deb
WORKDIR /app
COPY consumers/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY consumers/api /app/consumers/api
CMD ["uvicorn", "consumers.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
