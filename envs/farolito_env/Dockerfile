# OpenEnv environment for encounter 10. Build context: the repo root.
#   docker build -t bestiary-openenv:dev -f envs/farolito_env/Dockerfile .
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends patch && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir openenv==0.14.0 pytest==8.3.4
WORKDIR /app
COPY envs/farolito_env ./farolito_env
COPY upstream/farolito ./toy_repo
ENV PYTHONPATH=/app FAROLITO_TOY_REPO=/app/toy_repo
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/health')"
CMD ["python", "-m", "farolito_env.app", "--host", "0.0.0.0", "--port", "8000"]
