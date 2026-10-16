# Changelog

## 0.4.1 — 2026-10-16

- Parity choices use lowercase translation keys (n / e / o), as hassfest requires; stored settings are unchanged (N / E / O).

## 0.4.0 — 2026-10-16

First public release.

- On-board RS485 / RS232 ports and external serial ports bound from other integrations (HA-WF485-V3 recognised automatically).
- Admin panel "WOOW Serial" (Overview, Devices, Monitor, Send log), English and Traditional Chinese.
- Monitor: frames grouped by header / address, checksum detection by group vote.
- Send log: origin, replies, and echoes heard on other ports (kept out of the monitor and keypads).
- Devices: command templates with parameters, values and checksums; switch / light / cover / media player / select entities plus a button per command; state feedback rules, sensors, polling.
- Keypads: buttons as device triggers (rename-safe), event entity, `woow_serial_button` event, bindings that drive other devices with a runaway guard, LISTEN to learn a button.
- Service `woow_serial.send`, event `woow_serial_frame`.
