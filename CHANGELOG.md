# Changelog

## 0.5.1 — 2026-10-16

- WOOWTECH brand images (`brand/`): Home Assistant 2026.x shows a custom integration's own icon and logo.
- Service field descriptions no longer contain template syntax in braces, which hassfest reads as placeholders; the syntax stays in the fields' examples and in `describe`.

## 0.5.0 — 2026-10-16

Built for AI agents, with a template library checked against real protocols.

- **Services for agents** (ha-mcp, scripts): describe, list_ports, get_monitor, get_send_log, listen, list_devices, get_device, preview_command, test_pattern, list_templates, get_activity, save_device, create_from_template, delete_device, run_command, learn_command, learn_button, and `send` by port name. Ports, devices and commands can be named by name. Input is checked in the handler, so REST callers (ha-mcp) get the reason instead of a bare "400: Bad Request". Configuration changes need an admin user.
- **Home Assistant's MCP server**: the services are also the tools of an LLM API "WOOW Serial".
- **Activity log** and panel tab: what agents (services), people (panel) and entity actions changed or sent, with the caller's note, in the panel's language.
- **Template library**: Dooya and A-OK curtain motors, Waveshare Modbus relay, XY-MD02, Epson ESC/VP21, BenQ, Denon / Marantz, Extron SIS and "1V2." HDMI matrices; "From template" in the panel; local templates in `<config>/woow_serial/templates`. Template texts follow the language.
- A command with **wait_ms** now holds its port until the answer arrives (or the time is up), on-board and external ports alike: on half-duplex RS485 the next request no longer collides with the answer. The templates set it on every answered command.
- **Joined frames are taken apart**: an HA-WF485-V3 joins frames less than ~0.1 s apart, and some keypads send a press twice back to back. A received frame that matches nothing but is made entirely of known pieces (the HEX patterns of the port's devices, and our own recent sends that a device echoes) is handled piece by piece.
- Waits on external ports allow 0.5 s more: the answer travels through the other integration.
- Commands: **then** (a follow-up command, usually a query, for equipment that only acknowledges a setting).
- Rules and sensors: **reply_to** (only the answer to a given command — Modbus answers do not name the register).
- `send`: **expect** (wait for the first frame matching a receive pattern; its captures are returned) and the reply's checksums and timing.
- Text patterns take `{param}`; parameters of text commands may be any text.
- A position or brightness read back outside the device range is ignored (Dooya answers FF before its limits are set).
- Fixed: a device deleted and made again under the same name inherited the old entity's state.
- services.yaml carries the English texts too: ha-mcp (8.7) shows only those.
- Tests: every template against the makers' documented frames; a virtual bus against simulated equipment (tools/sim); a live matrix over RS485 / RS232 loops (tools/sim/matrix.py).

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
