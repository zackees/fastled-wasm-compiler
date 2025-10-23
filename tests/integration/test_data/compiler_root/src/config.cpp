// Config file with #define before include - should NOT use PCH
#define CUSTOM_CONFIG_VALUE 42

#include "FastLED.h"

int getConfigValue() {
    return CUSTOM_CONFIG_VALUE;
}
