# Project 17 replication environment: Ubuntu 24.04 with the four tool versions used in the original study
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1

# Optional package mirrors for slow networks
ARG UBUNTU_MIRROR=
ARG PIP_INDEX_URL=
RUN if [ -n "$UBUNTU_MIRROR" ]; then \
        sed -i "s|http://archive.ubuntu.com/ubuntu|$UBUNTU_MIRROR|g; s|http://security.ubuntu.com/ubuntu|$UBUNTU_MIRROR|g" \
            /etc/apt/sources.list.d/ubuntu.sources; \
    fi

# Package versions pinned to the original study
RUN apt-get -o Acquire::Retries=5 update && apt-get -o Acquire::Retries=5 install -y --no-install-recommends \
        clang-18=1:18.1.3-1ubuntu1 \
        cppcheck=2.13.0-2ubuntu3 \
        time=1.9-0.2build1 \
        cmake ninja-build make \
        gcc \
        python3 python3-venv python3-dev \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Same working root as the original study
ARG BASE=/home/yhong/comp5355
WORKDIR ${BASE}

# Flawfinder and CodeChecker (gcc is needed only to install CodeChecker)
RUN python3 -m venv ${BASE}/.venv \
    && ${BASE}/.venv/bin/pip install --no-cache-dir --retries 5 ${PIP_INDEX_URL:+--index-url "$PIP_INDEX_URL"} \
        flawfinder==2.0.20 codechecker==6.29.1

# Fail the build if any version differs
RUN clang-18 --version | grep -q "version 18.1.3" \
    && [ "$(cppcheck --version)" = "Cppcheck 2.13.0" ] \
    && [ "$(${BASE}/.venv/bin/flawfinder --version)" = "2.0.20" ] \
    && ${BASE}/.venv/bin/CodeChecker analyzer-version 2>/dev/null | grep -q "6.29.1" \
    && echo "tool versions verified"

COPY config/ /replication/config/
COPY replication/ /replication/replication/
WORKDIR ${BASE}
ENTRYPOINT ["python3", "/replication/replication/pipeline.py"]
