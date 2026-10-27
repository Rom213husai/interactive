#pragma once

#include <stdint.h>

struct CHSV {
    uint8_t hue;
    uint8_t saturation;
    uint8_t value;

    CHSV(uint8_t h, uint8_t s, uint8_t v) : hue(h), saturation(s), value(v) {}
};

struct CRGB {
    uint8_t hue = 0;
    uint8_t brightness = 0;

    CRGB &operator=(const CHSV &color) {
        hue = color.hue;
        brightness = color.value;
        return *this;
    }

    CRGB &operator+=(const CHSV &color) {
        hue = color.hue;
        const uint16_t sum = brightness + color.value;
        brightness = sum > 255 ? 255 : sum;
        return *this;
    }

    static const CRGB Black;
};

inline const CRGB CRGB::Black{};

inline void fill_solid(CRGB *leds, uint16_t count, CRGB color) {
    for (uint16_t i = 0; i < count; ++i) {
        leds[i] = color;
    }
}

inline void fadeToBlackBy(CRGB *leds, uint16_t count, uint8_t amount) {
    for (uint16_t i = 0; i < count; ++i) {
        leds[i].brightness = leds[i].brightness * (255 - amount) / 255;
    }
}

inline void fill_rainbow(CRGB *leds, uint16_t count, uint8_t hue, uint8_t deltaHue) {
    for (uint16_t i = 0; i < count; ++i) {
        leds[i] = CHSV(hue + i * deltaHue, 255, 255);
    }
}
