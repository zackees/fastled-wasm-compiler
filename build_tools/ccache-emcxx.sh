#!/bin/bash

CCACHE_CONFIGPATH=/js/pio_cache/ccache.conf ccache em++ "$@"

# build_tools/ccache-emcxx.sh