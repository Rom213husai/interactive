#pragma once

#include <Arduino.h>
#include "config.h"

void setupIrSensors();
uint8_t readNewIrDetections();
bool isIrSensorActive(uint8_t sensorNumber);
