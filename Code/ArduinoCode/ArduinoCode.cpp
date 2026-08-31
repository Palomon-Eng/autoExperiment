#include <Arduino.h>
#include <Wire.h>
#include <SensirionI2CSen5x.h>

// ==========================================
// HARDWARE PINS (Arduino 4 Relays Shield)
// Relays are on pins 4, 7, 8, 12
// ==========================================
#define RELAY_SOL1 8
#define RELAY_SOL2 12
#define RELAY_SOL3 7
#define RELAY_PUMP 4

// ==========================================
// DECLARING FUNCTIONS
// ==========================================
void start();
void stopAll();
void pumpTest();
void startFunctionSequence();
void updateFunctionSequence();
void readAndStoreSensors();
void handleCommand(char c);
void leakTest();
void printLiveCountdown(uint32_t now);

// ==========================================
// TIMING & STATE MACHINE CONSTANTS
// ==========================================
const uint32_t FIVE_MINUTES = 300000; 
const uint32_t SENSOR_INTERVAL = 2000; // Read sensor every 2s
uint32_t previousSensorMillis = 0;
uint32_t previousCountdownMillis = 0; 

enum FunctionState {
  STATE_IDLE,
  STATE_BLOCK_VALVE3_CLOSED, // Step 1 of Block: Pump run (HIGH), Val 1 & 2 Open (LOW), Val 3 Closed (HIGH)
  STATE_BLOCK_VALVE3_OPEN,   // Step 2 of Block: Pump run (HIGH), Val 1, 2 & 3 Open (LOW)
  STATE_BLOCK_FREEZE,        // Step 3 of Block: Freeze, Pump off (LOW), All Val Closed (HIGH)
  STATE_BLOCK_POST_FREEZE,   // Step 4 of Block: Pump run (HIGH), Val 1, 2 & 3 Open (LOW)
  STATE_FINAL_FREEZE,        // Final Freeze before the finish line
  STATE_FINAL_RUN           // Final Run: Pump run (HIGH), Val 1, 2 & 3 Open (LOW)
};

FunctionState currentSeqState = STATE_IDLE;
uint32_t sequenceStepTimer = 0;
uint32_t blockCounter = 0; // Tracks our 3 block cycles
String currentStatusMsg = "IDLE";

// ==========================================
// SENSOR & CSV DATA LOGGING (Circular Buffer)
// ==========================================
SensirionI2CSen5x sen5x;
float currentNox = 0.0, currentHum = 0.0, currentTemp = 0.0;

struct SensorData {
  uint32_t timestamp;
  float nox;
  float hum;
  float temp;
};

const int MAX_CSV_RECORDS = 100;
SensorData history[MAX_CSV_RECORDS];
int historyIdx = 0;
bool historyFull = false;

// ==========================================
// SETUP
// ==========================================
void setup() {
  Serial.begin(115200);
  delay(2000); 

  pinMode(RELAY_SOL1, OUTPUT);
  pinMode(RELAY_SOL2, OUTPUT);
  pinMode(RELAY_SOL3, OUTPUT);
  pinMode(RELAY_PUMP, OUTPUT);
  stopAll();
    
  Serial.println("Initializing SEN5x...");
  Wire.begin();
  sen5x.begin(Wire);
  delay(100); 
  
  uint16_t error = sen5x.deviceReset();
  if (error) {
    Serial.println("Warning: SEN5x deviceReset failed.");
  }
  delay(100);
  
  sen5x.setTemperatureOffsetSimple(0.0);
  error = sen5x.startMeasurement();
  if (error) {
    Serial.println("Error: Failed to start SEN5x measurement.");
  } else {
    Serial.println("SEN5x Initialized Successfully.");
  }
}

// ==========================================
// MAIN LOOP
// ==========================================
void loop() {
  updateFunctionSequence();
  
  while (Serial.available() > 0) {
    char c = Serial.read();
    handleCommand(c);
  }

  uint32_t currentMillis = millis();
  
  if (currentMillis - previousCountdownMillis >= 1000) {
    previousCountdownMillis = currentMillis;
    //printLiveCountdown(currentMillis); //Uncomment for a live countdown
  }

  if (currentMillis - previousSensorMillis >= SENSOR_INTERVAL) {
    previousSensorMillis = currentMillis;
    //readAndStoreSensors(); //Uncomment if sen55 is connected and you want sensor readings
  }
}

// ==========================================
// CONTROL FUNCTIONS
// ==========================================
void start() {
  currentSeqState = STATE_IDLE;
  digitalWrite(RELAY_SOL1, LOW);  
  digitalWrite(RELAY_SOL2, LOW);  
  digitalWrite(RELAY_SOL3, HIGH); 
  digitalWrite(RELAY_PUMP, LOW);  
  currentStatusMsg = "STARTED (MANUAL)";
  Serial.println("Command: START");
}

void stopAll() {
  currentSeqState = STATE_IDLE;
  digitalWrite(RELAY_SOL1, HIGH); 
  digitalWrite(RELAY_SOL2, HIGH); 
  digitalWrite(RELAY_SOL3, HIGH); 
  digitalWrite(RELAY_PUMP, LOW);  
  currentStatusMsg = "STOPPED";
  Serial.println("Command: STOP");
}

void pumpTest() {
  digitalWrite(RELAY_PUMP, HIGH); 
  delay(1000); 
  digitalWrite(RELAY_PUMP, LOW);  
  currentStatusMsg = "PUMP TEST COMPLETE";
  Serial.println("Command: PUMP TEST");
}

void startFunctionSequence() {
  stopAll(); 
  blockCounter = 0;
  currentSeqState = STATE_BLOCK_VALVE3_CLOSED;
  
  // Start Step 1 of Block 1: Valve 1 & 2 Open (LOW), Valve 3 Closed (HIGH), Pump On (HIGH)
  digitalWrite(RELAY_SOL1, LOW);
  digitalWrite(RELAY_SOL2, LOW);
  digitalWrite(RELAY_SOL3, HIGH); 
  digitalWrite(RELAY_PUMP, HIGH);
  
  sequenceStepTimer = millis();
  currentStatusMsg = "STAGE: BLOCK 1/3 - VALVE 3 CLOSED RUN (5 MINS)";
  Serial.println(currentStatusMsg);
}

void leakTest() {
    digitalWrite(RELAY_SOL1, HIGH); 
    digitalWrite(RELAY_SOL2, HIGH); 
    digitalWrite(RELAY_SOL3, LOW);  
    digitalWrite(RELAY_PUMP, HIGH); 
}

// ==========================================
// SEQUENCE STATE MACHINE (Non-blocking)
// ==========================================
void updateFunctionSequence() {
  if (currentSeqState == STATE_IDLE || currentSeqState == STATE_BLOCK_FREEZE || currentSeqState == STATE_FINAL_FREEZE) return;

  uint32_t now = millis();

  switch (currentSeqState) {
    case STATE_BLOCK_VALVE3_CLOSED:
      if (now - sequenceStepTimer >= FIVE_MINUTES) {
        // Step 2 of Block: Open Valve 3 (LOW)
        digitalWrite(RELAY_SOL3, LOW); 
        currentSeqState = STATE_BLOCK_VALVE3_OPEN;
        sequenceStepTimer = now;
        currentStatusMsg = "STAGE: BLOCK " + String(blockCounter + 1) + "/3 - VALVE 3 OPEN RUN (5 MINS)";
        Serial.println("\n" + currentStatusMsg);
      }
      break;

    case STATE_BLOCK_VALVE3_OPEN:
      if (now - sequenceStepTimer >= FIVE_MINUTES) {
        // Step 3 of Block: Freeze. Close all valves (HIGH), turn off pump (LOW)
        digitalWrite(RELAY_SOL1, HIGH);
        digitalWrite(RELAY_SOL2, HIGH);
        digitalWrite(RELAY_SOL3, HIGH);
        digitalWrite(RELAY_PUMP, LOW);
        
        currentSeqState = STATE_BLOCK_FREEZE;
        currentStatusMsg = "STAGE: BLOCK " + String(blockCounter + 1) + "/3 - FREEZE (AWAITING KEYPRESS)";
        Serial.println("\n" + currentStatusMsg);
      }
      break;

    case STATE_BLOCK_POST_FREEZE:
      if (now - sequenceStepTimer >= FIVE_MINUTES) {
        blockCounter++;
        
        if (blockCounter < 3) {
          // Loop back to Step 1 of the block for the next cycle
          digitalWrite(RELAY_SOL1, LOW);
          digitalWrite(RELAY_SOL2, LOW);
          digitalWrite(RELAY_SOL3, HIGH); // Valve 3 Closed again
          digitalWrite(RELAY_PUMP, HIGH);
          
          currentSeqState = STATE_BLOCK_VALVE3_CLOSED;
          sequenceStepTimer = now;
          currentStatusMsg = "STAGE: BLOCK " + String(blockCounter + 1) + "/3 - VALVE 3 CLOSED RUN (5 MINS)";
          Serial.println("\n" + currentStatusMsg);
        } else {
          // Block repeated 3 times. Go to Final Freeze. Close all valves, pump off.
          digitalWrite(RELAY_SOL1, HIGH);
          digitalWrite(RELAY_SOL2, HIGH);
          digitalWrite(RELAY_SOL3, HIGH);
          digitalWrite(RELAY_PUMP, LOW);
          
          currentSeqState = STATE_FINAL_FREEZE;
          currentStatusMsg = "STAGE: FINAL FREEZE (AWAITING KEYPRESS)";
          Serial.println("\n" + currentStatusMsg);
        }
      }
      break;

    case STATE_FINAL_RUN:
      if (now - sequenceStepTimer >= FIVE_MINUTES) {
        stopAll();
        currentStatusMsg = "STAGE: EXPERIMENT COMPLETE";
        Serial.println("\n" + currentStatusMsg);
      }
      break;

    default:
      break;
  }
}

// ==========================================
// COUNTDOWN LIVE TRACKING DISPLAY
// ==========================================
void printLiveCountdown(uint32_t now) {
  if (currentSeqState == STATE_IDLE || currentSeqState == STATE_BLOCK_FREEZE || currentSeqState == STATE_FINAL_FREEZE) return;

  uint32_t timeElapsed = now - sequenceStepTimer;
  if (timeElapsed > FIVE_MINUTES) return; 
  
  uint32_t timeRemaining = FIVE_MINUTES - timeElapsed;
  uint32_t totalSecondsRemaining = timeRemaining / 1000;
  uint32_t minutes = totalSecondsRemaining / 60;
  uint32_t seconds = totalSecondsRemaining % 60;

  Serial.print("[Countdown] ");
  Serial.print(minutes);
  Serial.print("m ");
  Serial.print(seconds);
  Serial.println("s remaining...");
}

// ==========================================
// SENSOR READING & LOGGING
// ==========================================
void readAndStoreSensors() {
  float mass1, mass2, mass4, mass10, vocIndex;
  
  uint16_t error = sen5x.readMeasuredValues(
    mass1, mass2, mass4, mass10, 
    currentHum, currentTemp, vocIndex, currentNox
  );

  if (error) return; 

  if (isnan(currentHum)) currentHum = 0.0;
  if (isnan(currentTemp)) currentTemp = 0.0;
  if (isnan(currentNox)) currentNox = 0.0;

  history[historyIdx] = {millis(), currentNox, currentHum, currentTemp};
  historyIdx++;
  
  if (historyIdx >= MAX_CSV_RECORDS) {
    historyIdx = 0;
    historyFull = true;
  }
}

// ==========================================
// COMMAND HANDLING & UNFREEZE INTERRUPTS
// ==========================================
void handleCommand(char c) {
  // Handle Mid-Block Unfreeze
  if (currentSeqState == STATE_BLOCK_FREEZE) {
    currentSeqState = STATE_BLOCK_POST_FREEZE;
    
    // Open all valves (LOW), pump turns on (HIGH)
    digitalWrite(RELAY_SOL1, LOW);
    digitalWrite(RELAY_SOL2, LOW);
    digitalWrite(RELAY_SOL3, LOW);
    digitalWrite(RELAY_PUMP, HIGH);
    
    sequenceStepTimer = millis();
    currentStatusMsg = "STAGE: BLOCK " + String(blockCounter + 1) + "/3 - POST-FREEZE RUN (5 MINS)";
    Serial.println("\nAction: Unfreezing Block Sequence...");
    Serial.println(currentStatusMsg);
    return;
  }
  
  // Handle Final Unfreeze
  if (currentSeqState == STATE_FINAL_FREEZE) {
    currentSeqState = STATE_FINAL_RUN;// Open all valves (LOW), pump turns on (HIGH)
    digitalWrite(RELAY_SOL1, LOW);
    digitalWrite(RELAY_SOL2, LOW);
    digitalWrite(RELAY_SOL3, LOW);
    digitalWrite(RELAY_PUMP, HIGH);
    sequenceStepTimer = millis();
    currentStatusMsg = "STAGE: FINAL RUN (5 MINS)";
    Serial.println("\nAction: Unfreezing for Final Run...");
    Serial.println(currentStatusMsg);
    return;
  }
  // Base Serial commands
  if (c == '1') 
  {
    start();
  } else if (c == '0') 
  {
    stopAll();
  } else if (c == 't') 
  {
    pumpTest();
  } else if (c == 'f') 
  {
    startFunctionSequence();
  } else if (c == 'l') 
  {
    leakTest();
  } else if (c == '2')
  {
    digitalWrite(RELAY_SOL1, HIGH);
    delay(1000);
    digitalWrite(RELAY_SOL1, LOW);
  } else if (c == '3')
  {
    digitalWrite(RELAY_SOL2, HIGH);
    delay(1000);
    digitalWrite(RELAY_SOL2, LOW);
  } else if (c == '4')
  {
    digitalWrite(RELAY_SOL3, HIGH);
    delay(1000);
    digitalWrite(RELAY_SOL3, LOW);
  } else if (c == '5')
  {
    digitalWrite(RELAY_PUMP, HIGH);
    delay(1000);
    digitalWrite(RELAY_PUMP, LOW);
  }
}
