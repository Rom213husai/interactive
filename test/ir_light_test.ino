// 赤外線センサが反応したら対応するライトを点灯するコード

// --- 設定項目 ---
const int IR_SENSOR_PIN_1 = 33;  // 赤外線センサ1を接続するピン
const int IR_SENSOR_PIN_2 = 32;  // 赤外線センサ2を接続するピン
const int LIGHT_PIN_1 = 13;      // ライト/LED1を接続するピン
const int LIGHT_PIN_2 = 12;      // ライト/LED2を接続するピン

// センサが遮られたときの値
const int DETECTED_STATE = HIGH;
// ----------------

bool lastDetected1 = false;
bool lastDetected2 = false;

void setup() {
  Serial.begin(115200);

  pinMode(IR_SENSOR_PIN_1, INPUT);
  pinMode(IR_SENSOR_PIN_2, INPUT);
  pinMode(LIGHT_PIN_1, OUTPUT);
  pinMode(LIGHT_PIN_2, OUTPUT);

  digitalWrite(LIGHT_PIN_1, LOW);
  digitalWrite(LIGHT_PIN_2, LOW);
}

void loop() {
  // センサの値を読み取る
  int sensorState1 = digitalRead(IR_SENSOR_PIN_1);
  int sensorState2 = digitalRead(IR_SENSOR_PIN_2);
  bool detected1 = sensorState1 == DETECTED_STATE;
  bool detected2 = sensorState2 == DETECTED_STATE;

  // センサ1の状態が変化した時だけライト1を更新
  if (detected1 != lastDetected1) {
    if (detected1) {
      Serial.println("Sensor 1: Detected!");
      digitalWrite(LIGHT_PIN_1, HIGH);
    } else {
      Serial.println("Sensor 1: Clear");
      digitalWrite(LIGHT_PIN_1, LOW);
    }

    lastDetected1 = detected1;
    delay(50);  // 短い連続反応を防ぐウェイト
  }

  // センサ2の状態が変化した時だけライト2を更新
  if (detected2 != lastDetected2) {
    if (detected2) {
      Serial.println("Sensor 2: Detected!");
      digitalWrite(LIGHT_PIN_2, HIGH);
    } else {
      Serial.println("Sensor 2: Clear");
      digitalWrite(LIGHT_PIN_2, LOW);
    }

    lastDetected2 = detected2;
    delay(50);  // 短い連続反応を防ぐウェイト
  }
}
