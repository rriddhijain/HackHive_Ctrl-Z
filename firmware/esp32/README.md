# ESP32 guard console (D89)

A bare ESP32 DevKit on USB is the operator's hardware stopwatch and alarm light. `app/console.py` (started by the
server when `console.enabled` in `config.yaml`) finds it as `/dev/cu.usbserial-*`; no board = nothing changes.

**The light:** our board has no user LED on GPIO2, so the light that shows is the USB chip's data-activity LED. The
alarm pulse is made of data (both sides send filler lines during an alarm); GPIO2 is driven anyway, for boards that
have an LED there.

**Use:** press **BOOT** when an incident starts → the first alert stops the stopwatch and the dashboard's
Console chip shows onset → alert in ms. Every alert pulses the LED (300 ms on / 100 ms off = critical, 600/400 = other) until you press BOOT again,
which acknowledges it like the dashboard button. Idle = dark apart from a short blip every 3 s (the link check).

**Flash** (Arduino IDE installed with the ESP32 core 3.3.x; nothing else needed):

```sh
CLI="/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli"
"$CLI" compile --fqbn esp32:esp32:esp32 --build-property "tools.ctags.pattern=/usr/bin/true" --build-path /tmp/esp32build firmware/esp32/console
"$CLI" upload -p /dev/cu.usbserial-0001 --fqbn esp32:esp32:esp32 --input-dir /tmp/esp32build firmware/esp32/console
```

The `ctags` override is needed on Apple Silicon without Rosetta (the bundled ctags is x86-only); the sketch declares
every function before use, so it needs no generated prototypes. Close the server first: only one program can hold
the port. Check after flashing: `uv run python -m app.console --board`.
