# This will be set to arm64 to support MacOS M1+ devices (and Linux-based arm64 devices)
ARG PLATFORM_TAG=""
ARG EMSDK_VERSION_TAG="4.0.8"

# ARG EMSDK_VERSION_TAG="3.1.70"

# Use only Emscripten base image
FROM emscripten/emsdk:${EMSDK_VERSION_TAG}${PLATFORM_TAG}

# Re-declare ARG after FROM to make it available in this stage

ENV DEBIAN_FRONTEND=noninteractive


# Update the apt-get package list. This takes a long time, so we do it first to maximize cache hits.
# Sometimes this fails so make sure we try a few times.
RUN apt-get update || apt-get update || apt-get update


# Install apt-fast to speed up apt-get installs
RUN apt-get install -y software-properties-common
RUN add-apt-repository ppa:apt-fast/stable -y && \
    apt-get update && \
    apt-get -y install apt-fast

# Update apt and install required packages
RUN apt-fast install -y \
    git \
    gawk \
    nano \
    ca-certificates \
    python3 \
    python3-pip \
    sed \
    tar \
    wget \
    unzip \
    make \
    cmake \
    ninja-build \
    ccache \
    mold \
    zlib1g \
    zlib1g-dev \
    gcc \
    g++ \
    rsync \
    coreutils \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*


# xdelta can make patches out of the binary blobs.
# apt update
# apt install -y --no-install-recommends xdelta3


# /container/bin contains symbolic links to python3 and pip3 as python and pip that we use for the compiler.
RUN mkdir -p /container/bin && \
    ln -s /usr/bin/python3 /container/bin/python && \
    ln -s /usr/bin/pip3 /container/bin/pip

RUN pip install uv==0.7.3


# /git is the dst for the source code, but actually not git anymore
# /misc is for tools related to building.
# /git/fastled/src is for the headers
# /examples is for building the Blink example, needs to be cleaned up.
# /js is the base build directory, named for historical reasons.
RUN \
   mkdir -p /git && \
   mkdir -p /misc && \
   mkdir -p /examples && \
   mkdir -p /js

ENV UV_COMPILE_BYTECODE=1


# Add Python and Emscripten to PATH
ENV PATH="/container/bin:/usr/local/bin:/usr/bin:/emsdk:/emsdk/upstream/emscripten:${PATH}"
ENV CCACHE_DIR=/ccache
ENV CCACHE_MAXSIZE=1G

# Set mold as the default linker
ENV LINKER=mold

ARG NO_PLATFORMIO="1"
ENV NO_PLATFORMIO=${NO_PLATFORMIO}

# Set container-specific environment variables for path resolution
ENV ENV_FASTLED_ROOT="/git/fastled"
ENV ENV_FASTLED_SOURCE_PATH="/git/fastled/src"
ENV ENV_EMSDK_PATH="/emsdk"
ENV ENV_SKETCH_ROOT="/js/src"
ENV ENV_VOLUME_MAPPED_SRC="/host/fastled/src"

# Create a custom print script
RUN echo '#!/bin/sh' > /usr/bin/print && \
    echo 'echo "$@"' >> /usr/bin/print && \
    chmod +x /usr/bin/print

# Add print function (which seems to be missing, strangly) and PATH modifications to /etc/profile
RUN echo 'print() { echo "$@"; }' >> /etc/profile && \
    echo 'export -f print' >> /etc/profile && \
    echo 'export PATH="/container/bin:/usr/bin:/emsdk:/emsdk/upstream/emscripten:$PATH"' >> /etc/profile && \
    echo 'export LINKER=mold' >> /etc/profile && \
    echo 'export NO_PLATFORMIO=1' >> /etc/profile && \
    echo 'source /emsdk/emsdk_env.sh' >> /etc/profile

# This was added to try and fix formatting issues. It didn't fix it but it's better to force everything to use
# utf-8, as god intended it.
ENV LANG=en_US.UTF-8
ENV LC_CTYPE=UTF-8
RUN echo 'export LANG=en_US.UTF-8' >> /etc/profile && \
    echo 'export LC_CTYPE=UTF-8' >> /etc/profile


RUN echo "update build 38"
# The NO_PLATFORMIO env var is now set at the top of the file

# Prune platforms we don't use and normalize line endings.
COPY ./build_tools/download_fastled.sh /build/download_fastled.sh
RUN chmod +x /build/download_fastled.sh && \
    dos2unix /build/download_fastled.sh
RUN /build/download_fastled.sh

RUN echo "update build 39"

# BEGIN BUILDING STATIC libfastled.a
# Now copy the CMakeLists.txt and the build_lib.sh script into the right place.
COPY ./build_tools/CMakeLists.txt /git/fastled-wasm/CMakeLists.txt
COPY ./build_tools/build_lib.sh /build/build_lib.sh

RUN chmod +x /build/build_lib.sh && \
    dos2unix /build/build_lib.sh
# Run the build
RUN /build/build_lib.sh --all

# END BUILDING STATIC libfastled.a


COPY . /tmp/fastled-wasm-compiler-install/
# Use uv to install globally
RUN uv pip install --system /tmp/fastled-wasm-compiler-install

# Effectively disable platformio telemetry and auto-updates.
RUN pio settings set check_platformio_interval 9999
RUN pio settings set enable_telemetry 0
# RUN uv run -m fastled_wasm_compiler.cli_update_from_master
COPY ./build_tools /build_tools
COPY ./build_tools/ccache-emcxx.sh /build_tools/ccache-emcxx.sh


# DISABLE FOR NOW
# COPY ./src/fastled_wasm_compiler/compile_lib.py /misc/compile_lib.py
# COPY ./src/fastled_wasm_compiler/compile_all_libs.py /misc/compile_all_libs.py
# RUN python3 /misc/compile_all_libs.py --src /git/fastled/src --out /build

RUN cp -r /git/fastled/examples/Blink /examples


### Final environment for sketch compilation
COPY ./assets/wasm_compiler_flags.py /platformio/wasm_compiler_flags.py
COPY ./assets/platformio.ini /platformio/platformio.ini

### Pre-warm the cache
RUN fastled-wasm-compiler-prewarm \
  --sketch=/examples/Blink \
  --assets-dir=/git/fastled/src/platforms/wasm/compiler \
  --fastled-root=/git/fastled \
  --fastled-source-path=/git/fastled/src \
  --emsdk-path=/emsdk \
  --sketch-path=/js/src \
  --debug

RUN fastled-wasm-compiler-prewarm \
  --sketch=/examples/Blink \
  --assets-dir=/git/fastled/src/platforms/wasm/compiler \
  --fastled-root=/git/fastled \
  --fastled-source-path=/git/fastled/src \
  --emsdk-path=/emsdk \
  --sketch-path=/js/src \
  --quick

RUN fastled-wasm-compiler-prewarm \
  --sketch=/examples/Blink \
  --assets-dir=/git/fastled/src/platforms/wasm/compiler \
  --fastled-root=/git/fastled \
  --fastled-source-path=/git/fastled/src \
  --emsdk-path=/emsdk \
  --sketch-path=/js/src \
  --release

### Final entry point init.
COPY ./entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
RUN dos2unix /entrypoint.sh


COPY ./build_tools_new/* /build_tools/

ENTRYPOINT ["/entrypoint.sh"]

CMD ["--help"]
