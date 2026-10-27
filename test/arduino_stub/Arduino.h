#pragma once

#include <stdint.h>

constexpr int LOW = 0;
constexpr int HIGH = 1;
constexpr int INPUT = 0;

uint32_t millis();
int digitalRead(uint8_t pin);
void pinMode(uint8_t pin, int mode);

inline long map(long value, long inputMin, long inputMax, long outputMin, long outputMax) {
    return (value - inputMin) * (outputMax - outputMin) /
               (inputMax - inputMin) + outputMin;
}
