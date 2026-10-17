// HackHive guard console (D89): a bare ESP32 DevKit as the operator's hardware stopwatch and alarm light.
// BOOT button (GPIO0) + onboard LED (GPIO2); USB serial 115200 to app/console.py, one text line per message.
//
//   laptop -> board   PING <id> <severity> | PING -  every 3 s: the link watchdog AND the alarm the server still
//                                                 wants acknowledged (newest), so a lost CLEAR or a restart self-heals
//                     ALERT <id> <severity> <cat>   an alert was sent to the dashboard
//                     CLEAR <id>                    acknowledged or dismissed on the dashboard
//   board -> laptop   HELLO hackhive-console 1      on boot
//                     PONG <id> | PONG -            reply to PING: the alarm the LED is showing
//                     MARK                          button pressed with no alarm: stopwatch started (incident onset)
//                     LAT <id> <ms>                 first ALERT after a MARK: onset -> alert as the operator saw it
//                     ACK <id>                      button pressed during an alarm: acknowledge it
//   both ways         ~~~~ (filler lines)           alarm bursts, ignored by the reader (see below)
//
// The light: this board has no user LED on GPIO2 (it is driven anyway, for boards that do); the LED that shows is the
// USB-UART's data-activity light. So the alarm pulse is made of data: during an alarm's "on" phase both sides send
// filler lines and the light glows; idle is quiet except the PING every 3 s (one short blip).
// LED: alarm = bold pulse, 300/100 ms (critical) or 600/400 ms (other), until acknowledged; stopwatch running = solid;
// idle = dark (acknowledged means silent); no PING for 5 s (server down, cable out) = double blink.

const int BTN = 0, LED = 2;
const uint32_t LINK_MS = 8000, MARK_MS = 30000, DEBOUNCE_MS = 40;

uint32_t lastLine = 0, markAt = 0, lastEdge = 0;
bool marking = false, wasDown = false, critical = false;
long alertId = -1, lastAcked = -1;
String line;

void onLine(const String &s) {
  lastLine = millis();
  if (s[0] == '~') return;                                  // the laptop's alarm burst
  int a = s.indexOf(' '), b = s.indexOf(' ', a + 1);
  if (s.startsWith("PING")) {
    if (a > 0 && s.substring(a + 1) == "-") alertId = -1;
    else if (b > a && a > 0) {
      long id = s.substring(a + 1, b).toInt();
      if (id != lastAcked) { alertId = id; critical = s.substring(b + 1).startsWith("critical"); }   // our ACK in flight
    }
    if (alertId >= 0) Serial.printf("PONG %ld\n", alertId); else Serial.println("PONG -");
    return;
  }
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
  if (alertId >= 0) { Serial.printf("ACK %ld\n", alertId); lastAcked = alertId; alertId = -1; return; }
  marking = true; markAt = millis();
  Serial.println("MARK");
}

// Alarm pulse {on ms, period ms}: long and mostly on, so the small onboard LED reads bright from across a desk
// (it's already at full drive; a fast 50 % flicker looked dim).
const uint32_t CRIT_ON = 300, CRIT_PERIOD = 400, OTHER_ON = 600, OTHER_PERIOD = 1000;

bool led(uint32_t t) {
  if (alertId >= 0) return critical ? t % CRIT_PERIOD < CRIT_ON : t % OTHER_PERIOD < OTHER_ON;
  if (marking) return true;
  if (t - lastLine > LINK_MS) { uint32_t p = t % 1500; return p < 100 || (p > 200 && p < 300); }
  return false;
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
  bool on = led(t);
  digitalWrite(LED, on);
  if (on && alertId >= 0 && Serial.availableForWrite() >= 64)   // never blocks: only when the UART has room
    Serial.println("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~");
}
