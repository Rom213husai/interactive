#include "ir_sensor.h"

static_assert(
    IR_SENSOR_PINS[0].number >= 1 && IR_SENSOR_PINS[0].number <= IR_SENSOR_COUNT &&
    IR_SENSOR_PINS[1].number >= 1 && IR_SENSOR_PINS[1].number <= IR_SENSOR_COUNT &&
    IR_SENSOR_PINS[2].number >= 1 && IR_SENSOR_PINS[2].number <= IR_SENSOR_COUNT &&
    IR_SENSOR_PINS[3].number >= 1 && IR_SENSOR_PINS[3].number <= IR_SENSOR_COUNT &&
    IR_SENSOR_PINS[0].number != IR_SENSOR_PINS[1].number &&
    IR_SENSOR_PINS[0].number != IR_SENSOR_PINS[2].number &&
    IR_SENSOR_PINS[0].number != IR_SENSOR_PINS[3].number &&
    IR_SENSOR_PINS[1].number != IR_SENSOR_PINS[2].number &&
    IR_SENSOR_PINS[1].number != IR_SENSOR_PINS[3].number &&
    IR_SENSOR_PINS[2].number != IR_SENSOR_PINS[3].number,
    "IR sensor numbers must be unique and between 1 and 4"
);
static_assert(
    IR_SENSOR_PINS[0].pin != IR_SENSOR_PINS[1].pin &&
    IR_SENSOR_PINS[0].pin != IR_SENSOR_PINS[2].pin &&
    IR_SENSOR_PINS[0].pin != IR_SENSOR_PINS[3].pin &&
    IR_SENSOR_PINS[1].pin != IR_SENSOR_PINS[2].pin &&
    IR_SENSOR_PINS[1].pin != IR_SENSOR_PINS[3].pin &&
    IR_SENSOR_PINS[2].pin != IR_SENSOR_PINS[3].pin,
    "IR sensor GPIO pins must be unique"
);

constexpr uint32_t DEBOUNCE_MS = 30;
bool rawDetected[IR_SENSOR_COUNT] = {};
bool stableDetected[IR_SENSOR_COUNT] = {};
uint32_t rawChangedAt[IR_SENSOR_COUNT] = {};

void setupIrSensors() {
    for (const IrSensorPin &sensor : IR_SENSOR_PINS) {
        pinMode(sensor.pin, INPUT);
    }
}

uint8_t readNewIrDetections() {
    uint8_t newDetections = 0;
    uint32_t now = millis();

    for (const IrSensorPin &sensor : IR_SENSOR_PINS) {
        uint8_t index = sensor.number - 1;
        bool detected = digitalRead(sensor.pin) == LOW;
        if (detected != rawDetected[index]) {
            rawDetected[index] = detected;
            rawChangedAt[index] = now;
        }

        if (detected != stableDetected[index] && now - rawChangedAt[index] >= DEBOUNCE_MS) {
            stableDetected[index] = detected;
            if (detected) {
                newDetections |= (1U << index);
            }
        }
    }

    return newDetections;
}

bool isIrSensorActive(uint8_t sensorNumber) {
    return sensorNumber >= 1 && sensorNumber <= IR_SENSOR_COUNT &&
           stableDetected[sensorNumber - 1];
}
