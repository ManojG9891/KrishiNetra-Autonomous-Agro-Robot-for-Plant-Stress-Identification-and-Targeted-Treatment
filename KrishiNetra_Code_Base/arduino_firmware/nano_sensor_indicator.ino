// --- LIBRARIES ---
#include <Servo.h>
#include <DHT.h>

// =======================================================================================
//   PIN DEFINITIONS (FINAL - Based on validated test code)
// =======================================================================================
const int DHT_PIN = 4;
#define DHTTYPE DHT11

const int SERVO_PAN_PIN = 5;
const int SERVO_TILT_PIN = 3;
const int SERVO_PIPE_PIN = 6;

const int BUZZER_PIN = 7;
const int LED_RED_PIN = 8;
const int LED_GREEN_PIN = 9;
const int LED_YELLOW_PIN = 10;

// --- OBJECT INITIALIZATION ---
Servo servoPan, servoTilt, servoPipe;
DHT dht(DHT_PIN, DHTTYPE);

// --- GLOBAL VARIABLES ---
String command;

// =======================================================================================
//   SETUP
// =======================================================================================

void setup() {
  Serial.begin(115200);
  servoPan.attach(SERVO_PAN_PIN); servoTilt.attach(SERVO_TILT_PIN); servoPipe.attach(SERVO_PIPE_PIN);
  dht.begin();
  pinMode(BUZZER_PIN, OUTPUT); pinMode(LED_RED_PIN, OUTPUT); pinMode(LED_GREEN_PIN, OUTPUT); pinMode(LED_YELLOW_PIN, OUTPUT);
  servoPan.write(90); servoTilt.write(90); servoPipe.write(90);
  stopAllIndicators();
  Serial.println("<STATUS:Nano_Ready>");
}


// =======================================================================================
//   MAIN LOOP
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
  if (cmd.startsWith("PAN:")) handleSmoothServo(cmd, servoPan);
  else if (cmd.startsWith("TILT:")) handleSmoothServo(cmd, servoTilt);
  else if (cmd.startsWith("PIPE:")) handleSmoothServo(cmd, servoPipe);
  else if (cmd == "PIPE_EXTEND") handlePipeExtend();
  else if (cmd.startsWith("INDICATE:")) handleIndication(cmd);
  else if (cmd == "BUZZER_ON") tone(BUZZER_PIN, 1000);
  else if (cmd == "STOP_NANO") stopAllIndicators();
  else if (cmd == "get_data") {
    float h = dht.readHumidity();
    float t = dht.readTemperature();
    Serial.print("<DATA:SENSORS:T:");
    if (isnan(t)) { Serial.print("err"); } else { Serial.print(t, 1); }
    Serial.print(",H:");
    if (isnan(h)) { Serial.print("err"); } else { Serial.print(h, 1); }
    Serial.println(">");
  } else { Serial.println("<ERROR:UNKNOWN_NANO_CMD>"); }
}

// =======================================================================================
//   HELPER FUNCTIONS
// =======================================================================================

/**
 * @brief RESTORED: Moves a servo smoothly from its current position to a target angle.
 * The delays in this function are critical for preventing timer conflicts.
 */
void handleSmoothServo(String& cmd, Servo& servo) {
  int colon = cmd.indexOf(':');
  int targetAngle = cmd.substring(colon + 1).toInt();
  targetAngle = constrain(targetAngle, 0, 180);

  int currentAngle = servo.read();
  
  if (targetAngle > currentAngle) {
    for (int pos = currentAngle; pos <= targetAngle; pos += 1) {
      servo.write(pos);
      delay(15); // This delay gives the processor time to handle other tasks
    }
  } else {
    for (int pos = currentAngle; pos >= targetAngle; pos -= 1) {
      servo.write(pos);
      delay(15);
    }
  }
  Serial.println("<ACK:SERVO_OK>");
}

/**
 * @brief Autonomous sequence for the spray pipe.
 */
void handlePipeExtend() {
  // *** FIX IS HERE: Create named String variables to pass to the function ***
  String extendCmd = "PIPE:135";
  handleSmoothServo(extendCmd, servoPipe);
  
  delay(500);
  
  String retractCmd = "PIPE:90";
  handleSmoothServo(retractCmd, servoPipe);
  
  Serial.println("<ACK:PIPE_OK>");
}

void handleIndication(String& cmd) {
    int colon = cmd.indexOf(':');
    String type = cmd.substring(colon + 1);
    stopAllIndicators();
    if (type == "error") {
        digitalWrite(LED_RED_PIN, HIGH);
        tone(BUZZER_PIN, 500);
    } else if (type == "success") {
        for(int i=0; i<2; i++){
          digitalWrite(LED_GREEN_PIN, HIGH);
          tone(BUZZER_PIN, 1500); delay(100); noTone(BUZZER_PIN);
          digitalWrite(LED_GREEN_PIN, LOW);
          delay(100);
        }
    } else if (type == "working") {
        digitalWrite(LED_YELLOW_PIN, HIGH);
    }
    Serial.println("<ACK:INDICATE_OK>");
}

void stopAllIndicators() {
  noTone(BUZZER_PIN);
  digitalWrite(LED_RED_PIN, LOW);
  digitalWrite(LED_GREEN_PIN, LOW);
  digitalWrite(LED_YELLOW_PIN, LOW);
}