#include <FastLED.h>

#define NUM_LEDS 60
#define DATA_PIN 3

CRGB leds[NUM_LEDS];

void setup() {
    FastLED.addLeds<WS2812, DATA_PIN, GRB>(leds, NUM_LEDS);
}

void loop() {
    // Simple rainbow animation
    for(int i = 0; i < NUM_LEDS; i++) {
        leds[i] = CHSV(i * 255 / NUM_LEDS, 255, 255);
    }
    FastLED.show();
    delay(50);
}