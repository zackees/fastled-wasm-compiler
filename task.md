[platformio]
build_cache_dir = .pio/cache

[env:main]
build_flags =
   ${env.build_flags}
   -D IDF_CCACHE_ENABLE=1
#board_build.cmake_extra_args = -DCCACHE_ENABLE=ON
Build time 4m30s => 30s. The difference is huge, 9x.

Also tried commented out -DCCACHE_ENABLE=ON instead of IDF_CCACHE_ENABL