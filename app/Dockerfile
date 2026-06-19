FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /project

RUN addgroup --system app && adduser --system --ingroup app app

COPY app/requirements.txt /project/app/requirements.txt
RUN pip install --no-cache-dir -r /project/app/requirements.txt

COPY app /project/app
COPY alembic.ini /project/alembic.ini
COPY alembic /project/alembic
RUN chown -R app:app /project

USER app
EXPOSE 8000

CMD ["uvicorn", "app.reader_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
