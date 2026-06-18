FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /project
COPY app/requirements.txt /project/app/requirements.txt
RUN pip install --no-cache-dir -r /project/app/requirements.txt
COPY app /project/app