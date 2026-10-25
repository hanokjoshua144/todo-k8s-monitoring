FROM python:3.12-slim
ARG APP_VERSION=v1
ENV APP_VERSION=$APP_VERSION
WORKDIR /app
COPY app.py .
EXPOSE 8080
CMD ["python", "-u", "app.py"]
