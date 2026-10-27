#include <cassert>
#include <stdint.h>

#include <Arduino.h>
#include <FastLED.h>

struct WS2812B {};
constexpr int GRB = 0;

struct FakeFastLED {
    template <typename Chipset, int pin, int order>
    void addLeds(CRGB *, uint16_t) {}
    void setBrightness(uint8_t) {}
    void clear() {}
    void show() {}
} FastLED;

struct FakeSerial {
    uint8_t events[4] = {};
    uint8_t eventCount = 0;

    void begin(unsigned long) {}
    void print(const char *) {}
    void print(uint8_t) {}
    void print(char) {}
    void println(uint8_t sensor) { events[eventCount++] = sensor; }
} Serial;

uint32_t currentTime = 0;
int pinValues[256] = {};

uint32_t millis() { return currentTime; }
int digitalRead(uint8_t pin) { return pinValues[pin]; }
void pinMode(uint8_t, int) {}
void delay(unsigned long) {}

#include "../ir_led/ir_led.ino"

int main() {
    setup();
    const uint8_t pin = IR_SENSOR_PINS[0].pin;

    pinValues[pin] = HIGH;
    loop();
    currentTime = 30;
    loop();
    assert(Serial.eventCount == 1);
    assert(Serial.events[0] == 1);
    assert(ledPlaying[0]);

    pinValues[pin] = LOW;
    currentTime = 31;
    loop();
    currentTime = 61;
    loop();

    pinValues[pin] = HIGH;
    currentTime = 62;
    loop();
    currentTime = 92;
    loop();
    assert(ledPlaying[0]);
    assert(Serial.eventCount == 2);
    assert(Serial.events[1] == 1);
}
