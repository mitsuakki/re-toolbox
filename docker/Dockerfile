FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/ctf

# Base packages
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git curl wget ca-certificates gnupg sudo \
        python3 python3-pip python3-venv pipx \
        cmake meson ninja-build pkg-config \
        file binutils unzip xz-utils zlib1g-dev libssl-dev \
        openjdk-21-jdk-headless \
        gdb gdb-multiarch lldb \
        nasm patchelf elfutils \
        strace ltrace tmux vim less jq \
        libc6-dbg libcapstone-dev \
        zip p7zip-full \
    && rm -rf /var/lib/apt/lists/*

# Non-root working user
RUN useradd -m -s /bin/bash -G sudo ctf \
    && echo "ctf ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers \
    && mkdir -p /workspace /opt/tools \
    && chown -R ctf:ctf /workspace /opt/tools

# radare2 (from source, latest) + r2pm
RUN git clone --depth 1 https://github.com/radareorg/radare2 /opt/tools/radare2 \
    && cd /opt/tools/radare2 \
    && sys/install.sh

# radare2-mcp + r2ghidra decompiler bridge, installed via r2pm as the ctf user
USER ctf
WORKDIR /home/ctf
RUN r2pm -U \
    && r2pm -ci r2mcp r2ghidra r2ghidra-sleigh \
    || true
USER root

# Ghidra (headless + GUI capable) + ghidra-mcp plugin
ARG GHIDRA_VERSION=11.3.2
ARG GHIDRA_DATE=20250415
ARG GHIDRA_URL=https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_${GHIDRA_VERSION}_build/ghidra_${GHIDRA_VERSION}_PUBLIC_${GHIDRA_DATE}.zip

RUN wget -q -O /tmp/ghidra.zip "${GHIDRA_URL}" \
    && unzip -q /tmp/ghidra.zip -d /opt/tools \
    && mv /opt/tools/ghidra_${GHIDRA_VERSION}_PUBLIC /opt/tools/ghidra \
    && rm /tmp/ghidra.zip \
    && chmod +x /opt/tools/ghidra/ghidraRun /opt/tools/ghidra/support/analyzeHeadless

ENV GHIDRA_INSTALL_DIR=/opt/tools/ghidra
ENV PATH="${GHIDRA_INSTALL_DIR}:${GHIDRA_INSTALL_DIR}/support:${PATH}"

# ghidra-mcp (bethington fork: GUI plugin + headless server + 200+ tools)
RUN git clone --depth 1 https://github.com/bethington/ghidra-mcp /opt/tools/ghidra-mcp \
    && cd /opt/tools/ghidra-mcp \
    && (mvn -q -DskipTests -Dghidra.version=${GHIDRA_VERSION} clean package || \
        echo "WARN: ghidra-mcp build needs network/maven access at build time; build manually if it failed") \
    || true

# Lightweight GUI stack so the Ghidra plugin path also works (X11 + VNC)
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb x11vnc fluxbox novnc websockify maven \
    && rm -rf /var/lib/apt/lists/*

# BinDiff (CLI). Requires a Ghidra/IDA export for diffing; CLI only, no MCP.
ARG BINDIFF_DEB_URL=https://github.com/google/bindiff/releases/download/v8/bindiff_8_amd64.deb
RUN wget -q -O /tmp/bindiff.deb "${BINDIFF_DEB_URL}" \
    && apt-get update \
    && apt-get install -y --no-install-recommends /tmp/bindiff.deb || apt-get install -y -f \
    && rm -f /tmp/bindiff.deb \
    && rm -rf /var/lib/apt/lists/*

# angr + Python RE/exploit stack (CLI / scripts, no dedicated MCP)
RUN pip3 install --break-system-packages --no-cache-dir \
        angr claripy pwntools ropper ropgadget capstone unicorn keystone-engine \
        pyelftools z3-solver r2pipe lief

# Fuzzing: AFL++ (built from source) + honggfuzz
RUN apt-get update && apt-get install -y --no-install-recommends \
        clang lld llvm llvm-dev libtool-bin automake autoconf \
        libglib2.0-dev libpixman-1-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/AFLplusplus/AFLplusplus /opt/tools/AFLplusplus \
    && cd /opt/tools/AFLplusplus \
    && make distrib -j"$(nproc)" \
    && make install

# RUN git clone --depth 1 https://github.com/google/honggfuzz /opt/tools/honggfuzz \
#     && cd /opt/tools/honggfuzz \
#     && make -j"$(nproc)" \
#     && make install

# Android RE: platform-tools (adb/fastboot), apktool, jadx
RUN wget -q -O /tmp/platform-tools.zip \
        https://dl.google.com/android/repository/platform-tools-latest-linux.zip \
    && unzip -q /tmp/platform-tools.zip -d /opt/tools \
    && rm /tmp/platform-tools.zip

ARG APKTOOL_VERSION=2.10.0
RUN wget -q -O /opt/tools/apktool.jar \
    https://github.com/iBotPeaches/Apktool/releases/download/v${APKTOOL_VERSION}/apktool_${APKTOOL_VERSION}.jar \
    && printf '#!/bin/sh\nexec java -jar /opt/tools/apktool.jar "$@"\n' > /usr/local/bin/apktool \
    && chmod +x /usr/local/bin/apktool

RUN JADX_VER=1.5.1 \
    && wget -q -O /tmp/jadx.zip \
        "https://github.com/skylot/jadx/releases/download/v${JADX_VER}/jadx-${JADX_VER}.zip" \
    && unzip -q /tmp/jadx.zip -d /opt/tools/jadx \
    && rm /tmp/jadx.zip \
    && ln -s /opt/tools/jadx/bin/jadx /usr/local/bin/jadx \
    && ln -s /opt/tools/jadx/bin/jadx-gui /usr/local/bin/jadx-gui

ENV PATH="/opt/tools/platform-tools:${PATH}"

# Frida (Android/iOS instrumentation, very common in mobile CTF reverse)
RUN pip3 install --break-system-packages --no-cache-dir frida-tools objection

# Final layout
COPY scripts/ /opt/tools/scripts/
COPY docker/entrypoint.sh /opt/tools/scripts/entrypoint.sh

COPY configs/ /opt/tools/configs/
RUN chmod +x /opt/tools/scripts/*.sh \
    && chown -R ctf:ctf /opt/tools /home/ctf

USER ctf
WORKDIR /workspace

ENTRYPOINT ["/opt/tools/scripts/entrypoint.sh"]
CMD ["bash"]
