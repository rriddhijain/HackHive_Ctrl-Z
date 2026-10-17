// HackHive guard console (D89): a bare ESP32 DevKit as the operator's hardware stopwatch and alarm light.
// BOOT button (GPIO0) + onboard LED (GPIO2); USB serial 115200 to app/console.py, one text line per message.
//
//   laptop -> board   PING                          every 1 s; the link watchdog
//                     ALERT <id> <severity> <cat>   an alert was sent to the dashboard
//                     CLEAR <id>                    acknowledged or dismissed on the dashboard
//   board -> laptop   HELLO hackhive-console 1      on boot
//                     PONG                          reply to PING
//                     MARK                          button pressed with no alarm: stopwatch started (incident onset)
//                     LAT <id> <ms>                 first ALERT after a MARK: onset -> alert as the operator saw it
//                     ACK <id>                      button pressed during an alarm: acknowledge it
//
// LED: alarm = fast blink (critical) / slow blink (other) until acknowledged; stopwatch running = solid;
// idle = a short blip every 2 s; no PING for 5 s (server down, cable out) = double blink.

const int BTN = 0, LED = 2;
const uint32_t LINK_MS = 5000, MARK_MS = 30000, DEBOUNCE_MS = 40;

uint32_t lastLine = 0, markAt = 0, lastEdge = 0;
bool marking = false, wasDown = false, critical = false;
long alertId = -1;
String line;

void onLine(const String &s) {
  lastLine = millis();
  if (s == "PING") { Serial.println("PONG"); return; }
  int a = s.indexOf(' '), b = s.indexOf(' ', a + 1);
  if (s.startsWith("ALERT ") && b > a) {
    uint32_t now = millis();
    long id = s.substring(a + 1, b).toInt();
    if (marking) { Serial.printf("LAT %ld %lu\n", id, (unsigned long)(now - markAt)); marking = false; }
    alertId = id;
    critical = s.substring(b + 1).startsWith("critical");
  } else if (s.startsWith("CLEAR ") && s.substring(a + 1).toInt() == alertId) {
    alertId = -1;
  }
}

void onPress() {
  if (alertId >= 0) { Serial.printf("ACK %ld\n", alertId); alertId = -1; return; }
  marking = true; markAt = millis();
  Serial.println("MARK");
}

bool led(uint32_t t) {
  if (alertId >= 0) return (t / (critical ? 60 : 250)) % 2;
  if (marking) return true;
  if (t - lastLine > LINK_MS) { uint32_t p = t % 1500; return p < 100 || (p > 200 && p < 300); }
  return t % 2000 < 40;
}

void setup() {
  pinMode(BTN, INPUT_PULLUP);
  pinMode(LED, OUTPUT);
  Serial.begin(115200);
  lastLine = millis() - LINK_MS;   // no laptop yet: show the link-lost pattern until the first PING
  Serial.println("HELLO hackhive-console 1");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { line.trim(); if (line.length()) onLine(line); line = ""; }
    else if (line.length() < 80) line += c;
  }
  uint32_t t = millis();
  bool down = digitalRead(BTN) == LOW;
  if (down != wasDown && t - lastEdge > DEBOUNCE_MS) {
    lastEdge = t; wasDown = down;
    if (down) onPress();
  }
  if (marking && t - markAt > MARK_MS) marking = false;   // nobody's alert came: drop the stale mark
  digitalWrite(LED, led(t));
}
