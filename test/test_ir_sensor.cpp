#include <cassert>

#include "ir_sensor.h"

uint32_t currentTime = 0;
int pinValues[256] = {};
bool configuredPins[256] = {};

uint8_t pinForSensor(uint8_t number) {
    for (const IrSensorPin &sensor : IR_SENSOR_PINS) {
        if (sensor.number == number) {
            return sensor.pin;
        }
    }
    assert(false);
    return 0;
}

uint32_t millis() {
    return currentTime;
}

int digitalRead(uint8_t pin) {
    return pinValues[pin];
}

void pinMode(uint8_t pin, int mode) {
    assert(mode == INPUT);
    configuredPins[pin] = true;
}

int main() {
    setupIrSensors();
    for (uint8_t sensor = 1; sensor <= IR_SENSOR_COUNT; ++sensor) {
        assert(configuredPins[pinForSensor(sensor)]);
    }
    assert(readNewIrDetections() == 0);

    pinValues[pinForSensor(2)] = HIGH;
    assert(readNewIrDetections() == 0);
    currentTime = 29;
    assert(readNewIrDetections() == 0);
    currentTime = 30;
    assert(readNewIrDetections() == (1U << 1));
    assert(isIrSensorActive(2));
    assert(!isIrSensorActive(1));
    assert(readNewIrDetections() == 0);

    pinValues[pinForSensor(1)] = HIGH;
    pinValues[pinForSensor(3)] = HIGH;
    assert(readNewIrDetections() == 0);
    currentTime = 60;
    assert(readNewIrDetections() == ((1U << 0) | (1U << 2)));

    pinValues[pinForSensor(2)] = LOW;
    assert(readNewIrDetections() == 0);
    currentTime = 90;
    assert(readNewIrDetections() == 0);
    assert(!isIrSensorActive(2));
    pinValues[pinForSensor(2)] = HIGH;
    assert(readNewIrDetections() == 0);
    currentTime = 120;
    assert(readNewIrDetections() == (1U << 1));
}
