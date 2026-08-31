#include <Arduino.h>
#include <M5StickCPlus2.h>
#include <SensirionI2CSen5x.h>
#include <BLEDevice.h>
#include <BLEServer.h>

SensirionI2CSen5x sen5x;
BLEAdvertising *pAdvertising;

// Payload structure to transmit over BLE advertising
struct __attribute__((packed)) SensorPayload {
  uint16_t companyId; // 0xFFFF for custom
  float temp;
  float hum;
  float nox;
  float pm25;
} payload;

void setup() {
  M5.begin();
  M5.Lcd.setRotation(1);
  M5.Lcd.fillScreen(BLACK);
  M5.Lcd.drawString("M5Stick BLE SEN55", 10, 10, 2);

  Wire.begin(32, 33); // SDA, SCL pins for M5StickC Plus2 Grove Port
  sen5x.begin(Wire);
  sen5x.deviceReset();
  delay(100);
  sen5x.startMeasurement();

  BLEDevice::init("M5Stick_SEN55");
  pAdvertising = BLEDevice::getAdvertising();
  payload.companyId = 0xFFFF;
}

void loop() {
  M5.update();

  // Temporary variables to avoid packed struct reference binding issues
  float mass1, pm25_val, mass4, mass10, hum_val, temp_val, vocIndex, nox_val;

  uint16_t err = sen5x.readMeasuredValues(mass1, pm25_val, mass4, mass10, hum_val, temp_val, vocIndex, nox_val);

  if (!err) {
    // Copy read values into packed struct payload
    payload.pm25 = pm25_val;
    payload.hum = hum_val;
    payload.temp = temp_val;
    payload.nox = nox_val;

    // Convert raw payload buffer directly to Arduino String type
    String strData = String((char*)&payload, sizeof(payload));

    BLEAdvertisementData advData;
    advData.setManufacturerData(strData);

    pAdvertising->stop();
    pAdvertising->setAdvertisementData(advData);
    pAdvertising->start();

    M5.Lcd.fillScreen(BLACK);
    M5.Lcd.setCursor(0, 10);
    M5.Lcd.printf("Temp: %.1f C\n", payload.temp);
    M5.Lcd.printf("Hum:  %.1f %%\n", payload.hum);
    M5.Lcd.printf("NOx:  %.1f\n", payload.nox);
    M5.Lcd.printf("PM2.5:%.1f\n", payload.pm25);
  }
  delay(2000);
}
