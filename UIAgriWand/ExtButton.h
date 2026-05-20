#pragma once
#include "Arduino.h"
#include "RTC_PCF85063.h"
#include "ui.h"
#include <HardwareSerial.h>

// Tanya Roja untuk pin ini
#define RX_PIN  44   // ganti
#define TX_PIN  43   // ganti

extern HardwareSerial SensorSerial;

void ExtButton_Init();
void ExtButton_Loop();
void ExtButton_ResetPinpoints();
void ExtButton_RequestTimeSync();
bool ExtButton_IsTimeSynced();
bool ExtButton_IsRecording();
unsigned long ExtButton_GetRecStartSec();