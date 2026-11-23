FROM python:3.15-slim-bookworm@sha256:96599df822d0e1c6bb700014a05c7f3c8cabc6e0f7ff3c4f9f69cee033b4b5d9

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

# Bootstrap uv, then install test and frozen-archive dependencies using project pins.
RUN pip install "uv==0.12.6" && \
    uv pip install --system -e ".[dev,linux_dist]" && \
    python -c "from PyInstaller.archive.readers import ZlibArchiveReader; from PyInstaller.archive.writers import ZlibArchiveWriter"

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
