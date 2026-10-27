#pragma once

#include <stdint.h>
#include <FastLED.h>

enum class LedPattern : uint8_t {
    CenterOutWave,
    EdgeToCenterWave,
};

struct LedPlayback {
    LedPattern pattern;
    uint16_t position;
    uint8_t hue;
};

void startLedPattern(
    CRGB *leds, 
    uint16_t count, 
    LedPlayback &playback,
    LedPattern pattern,
    uint8_t hue,
    bool clearLeds = true
);
bool playLedPattern(CRGB *leds, uint16_t count, LedPlayback &playback);
void fadeLedPattern(CRGB *leds, uint16_t count);
