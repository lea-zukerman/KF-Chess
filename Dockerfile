# Image for the game server. Only the packages the server actually
# imports are copied in -- no client, no view layer, no tests.
FROM python:3.12-slim

WORKDIR /app

# pip reads PIP_TRUSTED_HOST from the environment, and an ARG is visible
# to RUN in this stage without persisting into the final image. Empty by
# default, so an ordinary build verifies certificates as usual. On a
# network that intercepts TLS with a CA the container cannot chain to,
# build with:
#   docker build --build-arg PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org" .
ARG PIP_TRUSTED_HOST=

# Installed before the source is copied so this layer stays cached
# while the code changes.
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

COPY kungfu_chess/ ./kungfu_chess/
COPY protocol/ ./protocol/
COPY transport/ ./transport/
COPY server/ ./server/
COPY services/ ./services/

EXPOSE 8765

# The gateway is only the default: shard and allocator run from this same
# image with a different command. See docker-compose.yml.
#
# 0.0.0.0 rather than localhost: the port has to be reachable from
# outside the container.
CMD ["python", "-m", "services.gateway", "--host", "0.0.0.0", "--port", "8765"]