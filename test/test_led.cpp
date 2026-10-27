#include <cassert>

#include <FastLED.h>
#include "config.h"
#include "led.h"

void checkWave(uint16_t count, LedPattern pattern) {
    CRGB leds[10] = {};
    LedPlayback playback = {};
    startLedPattern(leds, count, playback, pattern, 96);

    const uint16_t leftCenter = (count - 1) / 2;
    const uint16_t rightCenter = count / 2;
    const uint16_t radius = count / 2 + count % 2;
    bool playing = true;

    for (uint16_t frame = 0; frame < radius; frame += 4) {
        playing = playLedPattern(leds, count, playback);
        for (uint16_t distance = frame; distance < frame + 4 && distance < radius;
             ++distance) {
            const uint16_t left = pattern == LedPattern::CenterOutWave
                                      ? leftCenter - distance : distance;
            const uint16_t right = pattern == LedPattern::CenterOutWave
                                       ? rightCenter + distance : count - 1 - distance;
            assert(leds[left].brightness == 255);
            assert(leds[right].brightness == 255);
            assert(leds[left].hue == 96);
            assert(leds[right].hue == 96);
        }
    }

    assert(!playing);
    assert(!playLedPattern(leds, count, playback));
    if (count > 8) {
        fadeLedPattern(leds, count);
        assert(leds[0].brightness < 255);
        assert(leds[0].brightness > 0);
        assert(leds[count - 1].brightness == leds[0].brightness);
    }
}

void checkUnlitTail(LedPattern pattern) {
    constexpr uint16_t activeCount = LED_COUNT_1 - LED_UNLIT_TAIL_COUNT;
    CRGB leds[LED_COUNT_1] = {};
    LedPlayback playback = {};
    startLedPattern(leds, activeCount, playback, pattern, 96);

    bool playing = playLedPattern(leds, activeCount, playback);
    if (pattern == LedPattern::CenterOutWave) {
        assert(leds[(activeCount - 1) / 2].brightness == 255);
        assert(leds[activeCount / 2].brightness == 255);
        assert(leds[0].brightness == 0);
    } else {
        assert(leds[0].brightness == 255);
        assert(leds[activeCount - 1].brightness == 255);
        assert(leds[activeCount / 2].brightness == 0);
    }

    while (playing) {
        playing = playLedPattern(leds, activeCount, playback);
    }
    for (uint16_t i = 0; i < activeCount; ++i) {
        assert(leds[i].brightness == 255);
    }
    for (uint16_t i = activeCount; i < LED_COUNT_1; ++i) {
        assert(leds[i].brightness == 0);
    }
}

int main() {
    const LedPattern patterns[] = {LedPattern::CenterOutWave, LedPattern::EdgeToCenterWave};
    for (LedPattern pattern : patterns) {
        checkWave(10, pattern);
        checkWave(9, pattern);
        checkWave(1, pattern);
        checkUnlitTail(pattern);
    }

    CRGB leds[1] = {};
    LedPlayback playback = {};
    for (LedPattern pattern : patterns) {
        startLedPattern(leds, 0, playback, pattern, 0);
        assert(!playLedPattern(leds, 0, playback));
        assert(playback.position == 0);
    }

    CRGB wave[8] = {};
    wave[0] = CHSV(1, 200, 100);
    startLedPattern(wave, 8, playback, LedPattern::EdgeToCenterWave, 64, false);
    assert(wave[0].brightness == 100);
    startLedPattern(wave, 8, playback, LedPattern::EdgeToCenterWave, 64);
    assert(wave[0].brightness == 0);
}
