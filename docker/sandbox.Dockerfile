# Image used inside OpenSandbox for encounter 6. Build it before the talk so no
# network is needed on stage:
#   docker build -t bestiary-sandbox:latest -f docker/sandbox.Dockerfile docker
FROM python:3.12-slim
RUN pip install --no-cache-dir pytest==8.3.4
WORKDIR /workspace
