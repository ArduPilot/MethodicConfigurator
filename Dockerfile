FROM python:3.14-slim-bookworm@sha256:5404df00cf00e6e7273375f415651837b4d192ac6859c44d3b740888ac798c99

LABEL maintainer="ArduPilot Methodic Configurator Team"
LABEL description="Development environment for ArduPilot Methodic Configurator with SITL support"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV DISPLAY=:99

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    python3-tk \
    xvfb \
    x11-utils \
    gnome-screenshot \
    libusb-1.0-0 \
    procps \
    libatomic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md LICENSE.md ./
COPY ardupilot_methodic_configurator/ ./ardupilot_methodic_configurator/
COPY tests/ ./tests/
COPY scripts/ ./scripts/

RUN pip install -e ".[dev]"

RUN chmod +x scripts/*.sh && \
    mkdir -p sitl sitl-cache && \
    touch /root/.Xauthority && \
    echo '#!/bin/bash' > /entrypoint.sh && \
    echo 'rm -f /tmp/.X99-lock' >> /entrypoint.sh && \
    echo 'Xvfb :99 -screen 0 1024x768x24 -ac &' >> /entrypoint.sh && \
    echo 'sleep 2' >> /entrypoint.sh && \
    echo 'exec "$@"' >> /entrypoint.sh && \
    chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

CMD ["python", "-m", "pytest", "-v", "-rs"]
