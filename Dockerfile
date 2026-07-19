FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8305

ENTRYPOINT ["openemr-mcp"]
CMD ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8305"]
