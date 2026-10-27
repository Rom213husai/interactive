#include <FastLED.h>

const int IR_SENSOR_PIN = 33;
const int LED_PIN = 13;
const int NUM_LEDS = 300;

const int BRIGHTNESS = 120;

CRGB leds[NUM_LEDS];

bool wasDetected = false;
int lightPosition = 0;
uint8_t baseHue = 0;

void setup() {
  Serial.begin(115200);

  pinMode(IR_SENSOR_PIN, INPUT);

  FastLED.addLeds<WS2812B, LED_PIN, GRB>(leds, NUM_LEDS);
  FastLED.setBrightness(BRIGHTNESS);

  FastLED.clear();
  FastLED.show();
}

void loop() {
  int sensorState = digitalRead(IR_SENSOR_PIN);
  bool detected = sensorState == HIGH;

  Serial.print("Sensor: ");
  Serial.println(sensorState == HIGH ? "HIGH" : "LOW");

  if (detected) {
    if (!wasDetected) {
      lightPosition = 0;
      baseHue += 32;
      FastLED.clear();
    }

    softRainbowWipe();
  } else {
    fadeToBlackBy(leds, NUM_LEDS, 12);
  }

  wasDetected = detected;

  FastLED.show();
  delay(25);
}

void softRainbowWipe() {
  fadeToBlackBy(leds, NUM_LEDS, 18);

  for (int i = 0; i < lightPosition; i++) {
    uint8_t hue = baseHue + i * 2;
    uint8_t brightness = map(i, 0, lightPosition, 80, 255);
    leds[i] += CHSV(hue, 200, brightness);
  }

  if (lightPosition < NUM_LEDS) {
    lightPosition += 4;
  } else {
    baseHue++;
    fill_rainbow(leds, NUM_LEDS, baseHue, 2);
  }
}
