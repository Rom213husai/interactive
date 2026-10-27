#pragma once

#include <stdint.h>
#include "led.h"

struct IrSensorPin {
    uint8_t number;
    uint8_t pin;
};

struct SensorLedSetting {
    uint8_t strip;
    LedPattern pattern;
    uint8_t hue;
};

constexpr uint8_t IR_SENSOR_COUNT = 4;

// マイコンごとの設定。書き込むマイコンに合わせて変更する。
constexpr uint8_t DEVICE_ID = 3;  // 5台それぞれに1～5の異なる番号を設定する。
constexpr uint8_t LED_PIN_1 = 17;
constexpr uint8_t LED_PIN_2 = 18;
constexpr uint16_t LED_COUNT_1 = 300;
constexpr uint16_t LED_COUNT_2 = 300;
constexpr uint16_t LED_UNLIT_TAIL_COUNT = 60;  // 各テープの末尾1m（60チップ）を消灯する。
constexpr uint8_t LED_BRIGHTNESS = 120;

// センサ番号とGPIO番号の対応。この番号がPC側の効果音設定にも使われる。
constexpr IrSensorPin IR_SENSOR_PINS[IR_SENSOR_COUNT] = {
    {1, 35}, //{32,34,35,35,34}
    {2, 32}, //{33,35,32,32,35}
    {3, 33}, //{35,32,33,33,33}
    {4, 34}, //{34,33,34,34,32}
};

// 上から順にセンサ1、2、3、4に対応するLEDテープ、パターン、色相。
constexpr SensorLedSetting SENSOR_LED_SETTINGS[IR_SENSOR_COUNT] = {
    {1, LedPattern::CenterOutWave, 16},
    {1, LedPattern::EdgeToCenterWave, 200},
    {2, LedPattern::CenterOutWave, 18},
    {2, LedPattern::EdgeToCenterWave, 255},
};
