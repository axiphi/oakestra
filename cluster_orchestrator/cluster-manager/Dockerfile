FROM ghcr.io/astral-sh/uv:python3.10-trixie
LABEL org.opencontainers.image.source https://github.com/oakestra/oakestra

RUN apt-get update --yes \
    && apt-get install --yes --no-install-recommends \
      curl \
      build-essential \
      git

COPY . /app
WORKDIR /app

ENV UV_NO_DEV=1
RUN uv sync --locked

# Install appropriate requirements
ARG LIB_BRANCH=develop
ENV LIB_BRANCH=${LIB_BRANCH}

RUN uv run -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. --pyi_out=. proto/clusterRegistration.proto

# ENV FLASK_APP=scheduler.py
ENV FLASK_ENV=development
# TRUE for verbose logging
ENV FLASK_DEBUG=FALSE

ENV SYSTEM_MANAGER_URL=3.120.37.66
ENV SYSTEM_MANAGER_PORT=10000
ENV SYSTEM_MANAGER_GRPC_PORT=50052

ENV CLUSTER_SERVICE_MANAGER_URL=localhost
ENV CLUSTER_SERVICE_MANAGER_PORT=10010

ENV CLUSTER_MONGO_URL=localhost
ENV CLUSTER_MONGO_PORT=10007

ENV CLUSTER_SCHEDULER_URL=localhost
ENV CLUSTER_SCHEDULER_PORT=5555

ENV MQTT_BROKER_URL=localhost
ENV MQTT_BROKER_PORT=10003
ENV MY_PORT=10100

ENV LOG_LEVEL=INFO

CMD gunicorn --bind [::]:${MY_PORT} cluster_manager:app