

# ARG FASTLED_VERSION=master
# ENV URL https://github.com/FastLED/FastLED/archive/refs/heads/${FASTLED_VERSION}.zip


# # Download latest, unzip move into position and clean up.
# RUN wget -O /git/fastled.zip ${URL} && \
#     unzip /git/fastled.zip -d /git && \
#     mv /git/FastLED-master /git/fastled && \
#     rm /git/fastled.zip
    
URL = "https://github.com/FastLED/FastLED/archive/refs/heads/master.zip"

import subprocess
import sys
from pathlib import Path
from typing import List

from fastled_wasm_compiler.paths import FASTLED_SRC

FASTLED_SRC_STR = FASTLED_SRC.as_posix()

def _run(cmd: List[str]) -> int:
    print(f"Running command: {cmd}")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert proc.stdout is not None
    line: bytes
    for line in proc.stdout:
        line_str = line.decode("utf-8", errors="replace")
        print(line_str.strip())
    proc.wait()
    return proc.returncode

def main() -> int: