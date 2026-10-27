#include <Arduino.h>
#include <FastLED.h>
#include "config.h"
#include "ir_sensor.h"
#include "led.h"

static_assert(DEVICE_ID >= 1 && DEVICE_ID <= 5, "DEVICE_ID must be 1-5");
static_assert(LED_PIN_1 != LED_PIN_2, "LED strips need different data pins");
static_assert(LED_COUNT_1 > LED_UNLIT_TAIL_COUNT &&
              LED_COUNT_2 > LED_UNLIT_TAIL_COUNT,
              "Each strip must have LEDs before its unlit tail");
static_assert(SENSOR_LED_SETTINGS[0].strip >= 1 && SENSOR_LED_SETTINGS[0].strip <= 2 &&
              SENSOR_LED_SETTINGS[1].strip >= 1 && SENSOR_LED_SETTINGS[1].strip <= 2 &&
              SENSOR_LED_SETTINGS[2].strip >= 1 && SENSOR_LED_SETTINGS[2].strip <= 2 &&
              SENSOR_LED_SETTINGS[3].strip >= 1 && SENSOR_LED_SETTINGS[3].strip <= 2,
              "Each sensor must use strip 1 or 2");

constexpr uint8_t STRIP_COUNT = 2;

CRGB strip1[LED_COUNT_1];
CRGB strip2[LED_COUNT_2];
CRGB *const strips[STRIP_COUNT] = {strip1, strip2};
constexpr uint16_t stripActiveCounts[STRIP_COUNT] = {
    LED_COUNT_1 - LED_UNLIT_TAIL_COUNT,
    LED_COUNT_2 - LED_UNLIT_TAIL_COUNT,
};
LedPlayback playback[IR_SENSOR_COUNT] = {};
bool ledPlaying[IR_SENSOR_COUNT] = {};

void sendIrEvent(uint8_t sensor) {
    Serial.print("IR,");
    Serial.print(DEVICE_ID);
    Serial.print(',');
    Serial.println(sensor);
}

void startSensorLed(uint8_t sensor) {
    uint8_t index = sensor - 1;
    if (ledPlaying[index]) {
        return;
    }

    const SensorLedSetting &setting = SENSOR_LED_SETTINGS[sensor - 1];
    uint8_t strip = setting.strip - 1;
    startLedPattern(strips[strip], stripActiveCounts[strip], playback[index],
                    setting.pattern, setting.hue, false);
    ledPlaying[index] = true;
}

void updateStrip(uint8_t strip) {
    fadeLedPattern(strips[strip], stripActiveCounts[strip]);
    for (uint8_t sensor = 1; sensor <= IR_SENSOR_COUNT; ++sensor) {
        uint8_t index = sensor - 1;
        if (ledPlaying[index] && SENSOR_LED_SETTINGS[index].strip == strip + 1) {
            ledPlaying[index] = playLedPattern(strips[strip], stripActiveCounts[strip],
                                               playback[index]);
        }
    }
}

void setup() {
    Serial.begin(115200);
    setupIrSensors();

    // 物理的な300チップすべてに送信し、末尾60チップにも消灯データを届ける。
    FastLED.addLeds<WS2812B, LED_PIN_1, GRB>(strip1, LED_COUNT_1);
    FastLED.addLeds<WS2812B, LED_PIN_2, GRB>(strip2, LED_COUNT_2);
    FastLED.setBrightness(LED_BRIGHTNESS);
    FastLED.clear();
    FastLED.show();
}

void loop() {
    uint8_t newDetections = readNewIrDetections();
    for (uint8_t sensor = 1; sensor <= IR_SENSOR_COUNT; ++sensor) {
        if (newDetections & (1U << (sensor - 1))) {
            startSensorLed(sensor);
            sendIrEvent(sensor);
        }
    }

    for (uint8_t strip = 0; strip < STRIP_COUNT; ++strip) {
        updateStrip(strip);
    }
    FastLED.show();
    delay(25);
}
