#!/bin/bash

# Check if NO_CCACHE environment variable is set
if [ -n "$NO_CCACHE" ]; then
    # Skip ccache and use emcc directly
    exec emcc "$@"
else
    # Use ccache as before
    exec ccache emcc "$@"
fi