# syntax=docker/dockerfile:1
FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/ctf

# System packages (single apt layer, cache-mounted)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        build-essential git curl wget ca-certificates gnupg sudo \
        python3 python3-pip python3-venv pipx \
        cmake meson ninja-build pkg-config \
        file binutils unzip xz-utils zlib1g-dev libssl-dev \
        openjdk-21-jdk-headless maven \
        gdb gdb-multiarch lldb \
        nasm patchelf elfutils \
        strace ltrace tmux vim less jq \
        libc6-dbg libcapstone-dev \
        zip p7zip-full \
        clang lld llvm llvm-dev libtool-bin automake autoconf \
        libglib2.0-dev libpixman-1-dev \
        libunwind-dev binutils-dev libblocksruntime-dev \
        libqt5widgets5 libc6-i386 \
    && rm -rf /var/lib/apt/lists/* && mkdir -p /var/lib/apt/lists/partial

# Non-root user
RUN useradd -m -s /bin/bash -G sudo ctf \
    && echo "ctf ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers \
    && mkdir -p /workspace /opt/tools \
    && chown -R ctf:ctf /workspace /opt/tools

# Python RE/exploit/frida stack (single pip layer, cache-mounted)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install --break-system-packages \
        angr claripy pwntools ropper ropgadget capstone unicorn keystone-engine \
        pyelftools z3-solver r2pipe lief \
        frida-tools objection mcp

# radare2 from source + r2pm plugins
RUN git clone --depth 1 https://github.com/radareorg/radare2 /opt/tools/radare2 \
    && cd /opt/tools/radare2 \
    && sys/install.sh

USER ctf
WORKDIR /home/ctf
RUN r2pm -U \
    && r2pm -ci r2mcp r2ghidra r2ghidra-sleigh \
    || echo "WARN: one or more r2pm plugins failed to install; r2mcp may still work" >&2
USER root

# AFL++ fuzzer
RUN git clone --depth 1 https://github.com/AFLplusplus/AFLplusplus /opt/tools/AFLplusplus \
    && cd /opt/tools/AFLplusplus \
    && make distrib -j"$(nproc)" \
    && make install

# honggfuzz fuzzer
RUN git clone --depth 1 https://github.com/google/honggfuzz /opt/tools/honggfuzz \
    && cd /opt/tools/honggfuzz \
    && make -j"$(nproc)" \
    && make install

# Ghidra headless
ARG GHIDRA_VERSION=12.1.2
ARG GHIDRA_DATE=20260605
ARG GHIDRA_URL=https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_${GHIDRA_VERSION}_build/ghidra_${GHIDRA_VERSION}_PUBLIC_${GHIDRA_DATE}.zip

RUN wget -q -O /tmp/ghidra.zip "${GHIDRA_URL}" \
    && unzip -q /tmp/ghidra.zip -d /opt/tools \
    && mv /opt/tools/ghidra_${GHIDRA_VERSION}_PUBLIC /opt/tools/ghidra \
    && rm /tmp/ghidra.zip \
    && chmod +x /opt/tools/ghidra/support/analyzeHeadless

ENV GHIDRA_INSTALL_DIR=/opt/tools/ghidra
ENV PATH="${GHIDRA_INSTALL_DIR}:${GHIDRA_INSTALL_DIR}/support:${PATH}"

# ghidra-mcp headless server
# Dynamically extracts the actual Ghidra version from the installed copy
# so the Maven build always matches — no more version-mismatch silent failures.
RUN --mount=type=cache,target=/root/.m2/repository \
    git clone --depth 1 https://github.com/bethington/ghidra-mcp /opt/tools/ghidra-mcp \
    && cd /opt/tools/ghidra-mcp \
    && pip3 install --break-system-packages --no-cache-dir -r requirements.txt \
    && GHIDRA_ACTUAL_VERSION="$(grep '^application\.version=' \
         "${GHIDRA_INSTALL_DIR}/Ghidra/application.properties" | cut -d= -f2)" \
    && echo "==> Patching pom.xml ghidra.version to ${GHIDRA_ACTUAL_VERSION}" \
    && sed -i "s|<ghidra.version>[^<]*</ghidra.version>|<ghidra.version>${GHIDRA_ACTUAL_VERSION}</ghidra.version>|" pom.xml \
    && PIP_BREAK_SYSTEM_PACKAGES=1 python3 -m tools.setup ensure-prereqs --ghidra-path "${GHIDRA_INSTALL_DIR}" \
    && mvn -q -DskipTests -Pheadless clean package \
    && HEADLESS_JAR="$(find target/archive-tmp -maxdepth 1 -iname '*.jar' 2>/dev/null | head -n1)" \
    && if [ -z "${HEADLESS_JAR}" ]; then \
         HEADLESS_JAR="$(find target -maxdepth 1 -iname '*Headless*.jar' 2>/dev/null | head -n1)"; \
       fi \
    && if [ -z "${HEADLESS_JAR}" ]; then \
         echo "WARN: no jar in archive-tmp or target, falling back to largest jar" >&2 \
         && HEADLESS_JAR="$(find target -maxdepth 1 -iname '*.jar' -printf '%s %p\n' 2>/dev/null | sort -rn | head -n1 | cut -d' ' -f2-)"; \
       fi \
    && mkdir -p docker \
    && echo "==> Deploying ${HEADLESS_JAR} -> docker/GhidraMCPHeadless.jar" \
    && cp "${HEADLESS_JAR}" docker/GhidraMCPHeadless.jar

# BinDiff CLI
ARG BINDIFF_DEB_URL=https://github.com/google/bindiff/releases/download/v8/bindiff_8_amd64.deb
RUN wget -q -O /tmp/bindiff.deb "${BINDIFF_DEB_URL}" \
    && apt-get update && apt-get install -y --no-install-recommends /tmp/bindiff.deb \
    && rm -f /tmp/bindiff.deb \
    && rm -rf /var/lib/apt/lists/*

# Android RE tools (platform-tools + apktool + jadx)
ARG APKTOOL_VERSION=2.10.0
ARG JADX_VER=1.5.1

RUN wget -q -O /tmp/platform-tools.zip \
        https://dl.google.com/android/repository/platform-tools-latest-linux.zip \
    && unzip -q /tmp/platform-tools.zip -d /opt/tools \
    && rm /tmp/platform-tools.zip \
    && wget -q -O /opt/tools/apktool.jar \
        "https://github.com/iBotPeaches/Apktool/releases/download/v${APKTOOL_VERSION}/apktool_${APKTOOL_VERSION}.jar" \
    && printf '#!/bin/sh\nexec java -jar /opt/tools/apktool.jar "$@"\n' > /usr/local/bin/apktool \
    && chmod +x /usr/local/bin/apktool \
    && wget -q -O /tmp/jadx.zip \
        "https://github.com/skylot/jadx/releases/download/v${JADX_VER}/jadx-${JADX_VER}.zip" \
    && unzip -q /tmp/jadx.zip -d /opt/tools/jadx \
    && rm /tmp/jadx.zip \
    && ln -s /opt/tools/jadx/bin/jadx /usr/local/bin/jadx \
    && ln -s /opt/tools/jadx/bin/jadx-gui /usr/local/bin/jadx-gui

ENV PATH="/opt/tools/platform-tools:${PATH}"

# Scripts & configs (most-frequently-changed, last layer)
COPY scripts/ /opt/tools/scripts/
COPY configs/ /opt/tools/configs/

RUN chmod +x /opt/tools/scripts/*.sh \
    && mkdir -p /home/ctf/.config/ghidra \
    && chown -R ctf:ctf /opt/tools /home/ctf

USER ctf
WORKDIR /workspace

ENTRYPOINT ["/opt/tools/scripts/entrypoint.sh"]
CMD ["bash"]
