#include <FastLED.h>
#include "led.h"

void startLedPattern(
    CRGB *leds, uint16_t count, 
    LedPlayback &playback,
    LedPattern pattern, 
    uint8_t hue,
    bool clearLeds
) {
    playback.pattern = pattern;
    playback.position = 0;
    playback.hue = hue;
    if (clearLeds) {
        fill_solid(leds, count, CRGB::Black);
    }
}

bool playLedPattern(
    CRGB *leds, 
    uint16_t count, 
    LedPlayback &playback
) {
    if (count == 0) {
        return false;
    }

    const uint16_t radius = count / 2 + count % 2;
    const uint16_t leftCenter = (count - 1) / 2;
    const uint16_t rightCenter = count / 2;
    const bool fromCenter = playback.pattern == LedPattern::CenterOutWave;
    constexpr uint8_t waveWidth = 4;

    if (playback.position >= radius) {
        return false;
    }

    for (uint8_t step = 0; step < waveWidth; ++step) {
        const uint16_t distance = playback.position + step;
        if (distance >= radius) {
            break;
        }

        const uint16_t left = fromCenter ? leftCenter - distance : distance;
        const uint16_t right = fromCenter ? rightCenter + distance : count - 1 - distance;
        leds[left] += CHSV(playback.hue, 200, 255);
        if (left != right) {
            leds[right] += CHSV(playback.hue, 200, 255);
        }
    }

    playback.position += waveWidth;
    return playback.position < radius;
}

void fadeLedPattern(CRGB *leds, uint16_t count) {
    fadeToBlackBy(leds, count, 12);
}
