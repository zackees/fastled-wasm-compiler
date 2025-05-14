
# This will be set to arm64 to support MacOS M1+ devices (and Linux-based arm64 devices)
ARG PLATFORM_TAG=""
ARG EMSDK_VERSION_TAG="4.0.8"
# ARG EMSDK_VERSION_TAG="3.1.70"

# Use only Emscripten base image
FROM emscripten/emsdk:${EMSDK_VERSION_TAG}${PLATFORM_TAG}


ENV DEBIAN_FRONTEND=noninteractive

# Update the apt-get package list. This takes a long time, so we do it first to maximize cache hits.
# Also install apt-fast first
RUN apt-get update


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
    dos2unix \
    tar \
    wget \
    unzip \
    make \
    cmake \
    ninja-build \
    ccache \
    zlib1g \
    zlib1g-dev \
    gcc \
    g++ \
    rsync \
    && rm -rf /var/lib/apt/lists/*


# /container/bin contains symbolic links to python3 and pip3 as python and pip that we use for the compiler.
RUN mkdir -p /container/bin && \
    ln -s /usr/bin/python3 /container/bin/python && \
    ln -s /usr/bin/pip3 /container/bin/pip


# Add Python and Emscripten to PATH
ENV PATH="/container/bin:/usr/local/bin:/usr/bin:/emsdk:/emsdk/upstream/emscripten:${PATH}"
ENV CCACHE_DIR=/ccache
ENV CCACHE_MAXSIZE=1G

# Create a custom print script
RUN echo '#!/bin/sh' > /usr/bin/print && \
    echo 'echo "$@"' >> /usr/bin/print && \
    chmod +x /usr/bin/print

# Add print function (which seems to be missing, strangly) and PATH modifications to /etc/profile
RUN echo 'print() { echo "$@"; }' >> /etc/profile && \
    echo 'export -f print' >> /etc/profile && \
    echo 'export PATH="/container/bin:/usr/bin:/emsdk:/emsdk/upstream/emscripten:$PATH"' >> /etc/profile && \
    echo 'source /emsdk/emsdk_env.sh' >> /etc/profile

# This was added to try and fix formatting issues. It didn't fix it but it's better to force everything to use
# utf-8, as god intended it.
ENV LANG=en_US.UTF-8
ENV LC_CTYPE=UTF-8
RUN echo 'export LANG=en_US.UTF-8' >> /etc/profile && \
    echo 'export LC_CTYPE=UTF-8' >> /etc/profile


ARG FASTLED_VERSION=master
ENV FASTLED_VERSION=${FASTLED_VERSION}
RUN git clone -b ${FASTLED_VERSION} https://github.com/fastled/FastLED.git --depth 1 /git/fastled

RUN echo "force update10"

COPY ./assets/wasm_compiler_flags.py /platformio/wasm_compiler_flags.py
COPY ./assets/platformio.ini /platformio/platformio.ini

RUN cd /git/fastled/examples && ls -al || false


# now update the git repo to the latest version
RUN cd /git/fastled && git pull


RUN echo "force re build4"

COPY ./src/fastled_wasm_compiler/copy_headers.py /misc/copy_headers.py


# Copy the headers only from fastled
RUN mkdir -p /headers
RUN python3 /misc/copy_headers.py /git/fastled/src /headers

COPY ./src/fastled_wasm_compiler/compile_lib.py /misc/compile_lib.py


# compile the fastled library in all three modes
RUN python3 /misc/compile_lib.py --src /git/fastled/src --out /build/debug --debug
RUN python3 /misc/compile_lib.py --src /git/fastled/src --out /build/quick --quick
RUN python3 /misc/compile_lib.py --src /git/fastled/src --out /build/release --release


# COPY examples from /git/fastled/examples to /examples
# COPY /git/fastled/examples /examples
# RUN mkdir -p /examples && cp -r /git/fastled/examples /

# COPY BLINK

RUN cd /git/fastled/examples && ls -al || false

RUN mkdir -p /examples

RUN cp -r /git/fastled/examples/Blink /examples

# assert that directory/examples/Blink exists
RUN ls -al /examples/Blink || false


# COPY BLINK for test compile, we should get rid of this and use a real example, like above.
#COPY ./Blink /examples/Blink

#COPY ./src/fastled_wasm_compiler/compile_sketch.py /misc/compile_sketch.py

# # Use the quick build for the example by default
# RUN python /misc/compile_sketch.py \
#   --example /examples/Blink \
#   --lib /build/quick/libfastled.a \
#   --out /build_examples/Blink


RUN pip install uv==0.7.3

COPY . /tmp/fastled-wasm-compiler-install/
# Use uv to install globally
RUN uv pip install --system /tmp/fastled-wasm-compiler-install


# Effectively disable platformio telemetry and auto-updates.
RUN pio settings set check_platformio_interval 9999
RUN pio settings set enable_telemetry 0


# now pre-warm the cache.
# RUN pio pkg update
# Copy /examples/Blink to /build_examples/Blink
# RUN mkdir -p /build_examples && \
#     cp -r /examples/Blink /build_examples/Blink

# Create the build directory which for historical reasons is
# at /js
RUN mkdir -p /js

# Pre-warm the cache for the compiler, takes off a whopping 6 seconds.
# For legacy reasons the sketch has to be two levels up. This produces
# multiple build artifacts so that patch is just to delete the folder.
# Also, there was something about this that was important. But it could
# just be legacy logic. The compiler pipeline relies on this.
#
# Counter intuintively, even though we've copied /examples/Blink to /build_examples/Blink
# we actually have to select /build_examples as the target directory.
# RUN fastled-wasm-compiler \
#   --compiler-root=/js \
#   --assets-dir=/git/fastled/src/platforms/wasm/compiler \
#   --mapped-dir=/build_examples \
#   --debug && \
#   rm -rf /build_examples/Blink && \
#   cp -r /examples/Blink /build_examples 

RUN fastled-wasm-compiler-prewarm \
  --sketch=/examples/Blink \
  --assets-dir=/git/fastled/src/platforms/wasm/compiler \
  --debug


# List all files in /build_examples
# RUN cd /build_examples && find

# Why does this happen? We need to get rid of all the manual cleaning
# out of directories.
# RUN cp -r /git/fastled/examples/Blink /build_examples/Blink

# RUN fastled-wasm-compiler \
#   --compiler-root=/js \
#   --assets-dir=/git/fastled/src/platforms/wasm/compiler \
#   --mapped-dir=/build_examples \
#   --quick && \
#   rm -rf /build_examples/Blink && \
#   cp -r /examples/Blink /build_examples/Blink 

RUN fastled-wasm-compiler-prewarm \
  --sketch=/examples/Blink \
  --assets-dir=/git/fastled/src/platforms/wasm/compiler \
  --quick

# ## TODO: Release.
# # Now remove the builds
# RUN rm -rf /build_examples


COPY ./entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
RUN dos2unix /entrypoint.sh

ENTRYPOINT ["fastled-wasm-compiler"]

CMD ["--help"]
