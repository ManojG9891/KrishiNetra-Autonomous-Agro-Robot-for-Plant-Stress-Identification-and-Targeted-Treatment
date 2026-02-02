// --- LIBRARIES ---
#include <NewPing.h> // A more reliable library for ultrasonic sensors

// =======================================================================================
//   PIN DEFINITIONS (FINAL - Based on validated test code)
// =======================================================================================

// --- Motors: Right Side ---
const int RIGHT_IN1 = 9;
const int RIGHT_IN2 = 7;
const int RIGHT_IN3 = A4;
const int RIGHT_IN4 = A5;
const int RIGHT_EN = 10;   // PWM speed control for all right-side motors

// --- Motors: Left Side ---
const int LEFT_IN1 = A0;
const int LEFT_IN2 = A1;
const int LEFT_IN3 = A2;
const int LEFT_IN4 = A3;
const int LEFT_EN = 11;    // PWM speed control for all left-side motors

// --- Actuators (Relays/Pumps) ---
const int RELAY_1_PESTICIDE_1 = 3;
const int RELAY_2_PESTICIDE_2 = 4;
const int RELAY_3_FERTILIZER = 5;

// --- Navigation & Odometry Sensors ---
const int HALL_SENSOR_PIN = 2; // Must be an interrupt pin (2 or 3 on Uno)
const int FRONT_TRIG_PIN = 13;
const int FRONT_ECHO_PIN = 12;
const int SIDE_TRIG_PIN = 8;
const int SIDE_ECHO_PIN = 6;

// --- OBJECTS & GLOBAL VARIABLES ---
String command;
volatile int hall_count = 0;
unsigned long last_hall_trigger_time = 0; // For debouncing the hall sensor

NewPing sonarFront(FRONT_TRIG_PIN, FRONT_ECHO_PIN, 400); // Max distance 400 cm
NewPing sonarSide(SIDE_TRIG_PIN, SIDE_ECHO_PIN, 400);

// =======================================================================================
//   SETUP - INITIALIZE HARDWARE AND COMMUNICATION
// =======================================================================================
void setup() {
  Serial.begin(115200);
  pinMode(RIGHT_IN1, OUTPUT); pinMode(RIGHT_IN2, OUTPUT); pinMode(RIGHT_IN3, OUTPUT); pinMode(RIGHT_IN4, OUTPUT);
  pinMode(LEFT_IN1, OUTPUT);  pinMode(LEFT_IN2, OUTPUT); pinMode(LEFT_IN3, OUTPUT); pinMode(LEFT_IN4, OUTPUT);
  pinMode(RIGHT_EN, OUTPUT);  pinMode(LEFT_EN, OUTPUT);
  pinMode(RELAY_1_PESTICIDE_1, OUTPUT); pinMode(RELAY_2_PESTICIDE_2, OUTPUT); pinMode(RELAY_3_FERTILIZER, OUTPUT);
  digitalWrite(RELAY_1_PESTICIDE_1, HIGH); digitalWrite(RELAY_2_PESTICIDE_2, HIGH); digitalWrite(RELAY_3_FERTILIZER, HIGH);
  pinMode(HALL_SENSOR_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(HALL_SENSOR_PIN), count_rotation, FALLING);
  stopAll();
  Serial.println("<STATUS:Uno_Ready>");
}


// =======================================================================================
//   MAIN LOOP - COMMAND-DRIVEN
// =======================================================================================
void loop() {
  if (Serial.available() > 0) {
    String commandWithBrackets = Serial.readStringUntil('>');
    if (commandWithBrackets.startsWith("<")) {
      String command = commandWithBrackets.substring(1);
      processCommand(command);
    }
  }
}
// =======================================================================================
//   COMMAND ROUTER & HANDLERS
// =======================================================================================
void processCommand(String& cmd) {
  if (cmd.startsWith("MOVE:")) {
    int firstColon = cmd.indexOf(':');
    int secondColon = cmd.indexOf(':', firstColon + 1);
    int left = cmd.substring(firstColon + 1, secondColon).toInt();
    int right = cmd.substring(secondColon + 1).toInt();
    moveMotors(left, right);
    Serial.println("<ACK:MOVE_OK>");
  } else if (cmd.startsWith("SPRAY:")) {
    int firstColon = cmd.indexOf(':');
    int secondColon = cmd.indexOf(':', firstColon + 1);
    int tankNum = cmd.substring(firstColon + 1, secondColon).toInt();
    long duration = cmd.substring(secondColon + 1).toInt();
    int pin = getRelayPin(tankNum);
    if (pin != -1) {
        digitalWrite(pin, LOW); delay(duration); digitalWrite(pin, HIGH);
        Serial.println("<ACK:SPRAY_COMPLETE>");
    }
  } else if (cmd.startsWith("PUMP:")) {
    int firstColon = cmd.indexOf(':');
    int secondColon = cmd.indexOf(':', firstColon + 1);
    int tankNum = cmd.substring(firstColon + 1, secondColon).toInt();
    int state = cmd.substring(secondColon + 1).toInt();
    int pin = getRelayPin(tankNum);
    if (pin != -1) {
        digitalWrite(pin, state == 1 ? LOW : HIGH);
        Serial.println("<ACK:PUMP_OK>");
    }
  } else if (cmd == "STOP") {
    stopAll();
    Serial.println("<ACK:STOP_OK>");
  } else if (cmd == "RESET_ENCODER") {
    noInterrupts();
    hall_count = 0;
    interrupts();
    Serial.println("<ACK:ENCODER_RESET>");
  } else if (cmd == "get_data") {
    long front_dist = sonarFront.ping_cm();
    if (front_dist == 0) front_dist = 400;
    long side_dist = sonarSide.ping_cm();
    if (side_dist == 0) side_dist = 400;
    Serial.print("<DATA:SENSORS:F:");
    Serial.print(front_dist);
    Serial.print(",S:");
    Serial.print(side_dist);
    Serial.print(",E:");
    Serial.print(hall_count);
    Serial.println(">");
  }
}

// =======================================================================================
//   CORE & HELPER FUNCTIONS
// =======================================================================================

void moveMotors(int leftSpeed, int rightSpeed) {
  leftSpeed = constrain(leftSpeed, -255, 255);
  rightSpeed = constrain(rightSpeed, -255, 255);

  // Left Side Control
  if (leftSpeed >= 0) { // Forward
    digitalWrite(LEFT_IN1, HIGH); digitalWrite(LEFT_IN2, LOW);
    digitalWrite(LEFT_IN3, HIGH); digitalWrite(LEFT_IN4, LOW);
  } else { // Backward
    digitalWrite(LEFT_IN1, LOW); digitalWrite(LEFT_IN2, HIGH);
    digitalWrite(LEFT_IN3, LOW); digitalWrite(LEFT_IN4, HIGH);
  }
  analogWrite(LEFT_EN, abs(leftSpeed));

  // Right Side Control
  if (rightSpeed >= 0) { // Forward
    digitalWrite(RIGHT_IN1, HIGH); digitalWrite(RIGHT_IN2, LOW);
    digitalWrite(RIGHT_IN3, HIGH); digitalWrite(RIGHT_IN4, LOW);
  } else { // Backward
    digitalWrite(RIGHT_IN1, LOW); digitalWrite(RIGHT_IN2, HIGH);
    digitalWrite(RIGHT_IN3, LOW); digitalWrite(RIGHT_IN4, HIGH);
  }
  analogWrite(RIGHT_EN, abs(rightSpeed));
}

void stopAll() {
  moveMotors(0, 0);
  digitalWrite(RELAY_1_PESTICIDE_1, HIGH);
  digitalWrite(RELAY_2_PESTICIDE_2, HIGH);
  digitalWrite(RELAY_3_FERTILIZER, HIGH);
}

void count_rotation() {
  if (millis() - last_hall_trigger_time > 50) { // 50ms debounce
    hall_count++;
    last_hall_trigger_time = millis();
  }
}

int getRelayPin(int tankNum) {
    if (tankNum == 1) return RELAY_1_PESTICIDE_1;
    if (tankNum == 2) return RELAY_2_PESTICIDE_2;
    if (tankNum == 3) return RELAY_3_FERTILIZER;
    return -1; // Invalid tank
}