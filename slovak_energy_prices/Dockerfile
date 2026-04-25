ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.21
FROM ${BUILD_FROM}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apk add --no-cache python3

COPY rootfs /
RUN chmod a+x /run.sh /usr/local/bin/app.py

CMD [ "/run.sh" ]
