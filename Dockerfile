FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8080

ENV EMASS_MOCK_HOST=0.0.0.0 \
    EMASS_MOCK_PORT=8080 \
    EMASS_MOCK_API_KEY=test-api-key

CMD ["python", "-m", "emass_mock"]
