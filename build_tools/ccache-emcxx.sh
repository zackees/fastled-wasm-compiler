#!/bin/bash

# Check if NO_CCACHE environment variable is set
if [ -n "$NO_CCACHE" ]; then
    # Skip ccache and use em++ directly
    exec em++ "$@"
else
    # Use ccache as before
    CCACHE_CONFIGPATH=/js/pio_cache/ccache.conf exec ccache em++ "$@"
fi

# build_tools/ccache-emcxx.sh