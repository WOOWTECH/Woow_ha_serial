# WOOW Serial

[繁體中文](README.md)

Turn RS485 / RS232 equipment into native Home Assistant devices: watch the frames on the line in a sidebar panel, learn them, build devices and entities from them, and let wall keypads trigger automations. No YAML.

The admin panel follows the approach of [HAIR](https://github.com/DAB-LABS/HAIR), the Home Assistant infrared admin panel.

## Features

- **Ports**
  - On-board serial ports: RS485 (SC16IS752, `/dev/ttySC*`) and RS232 (`/dev/ttyAMA0`) on a Raspberry Pi.
  - External devices: serial ports provided by another integration, such as the WOOWTECH HA-WF485-V3 (ESPHome). Picking the device fills in the binding.
- **Monitor**
  - Every frame each port hears, grouped by header / address and counted.
  - Detects 9 checksums (CRC16/Modbus, CRC16/CCITT, SUM8, XOR8, ...).
  - Name or hide frames, or turn them into a device command or a keypad button.
- **Devices**
  - Commands become covers, lights, switches, media players and selects, with a button entity per command.
  - Device replies update the state. Values can be read into sensors, and devices can be polled.
- **Keypads**
  - Every button of a wall keypad (or any input that sends frames by itself) is a device trigger in the automation editor, and renaming it does not break existing automations.
  - A button can also drive another device directly.
- **Send log**
  - Every frame Home Assistant sent, who sent it (service, entity, panel, device), and whether and how fast the device answered.
  - If another port on the same line hears it, the send log shows it. That proves it reached the wire, and such echoes never reach the monitor or keypads.
- **Built-in templates**: Dooya and A-OK curtain motors, Waveshare Modbus relays, XY-MD02 temperature / humidity, Epson and BenQ projectors, Denon / Marantz receivers, Extron and "1V2." HDMI matrices. Every template's frames were checked byte for byte against the maker's documented examples. Your own templates can be added.
- **Made for AI agents**: everything the panel does is a Home Assistant service with response data, for [ha-mcp](https://github.com/homeassistant-ai/ha-mcp) or Home Assistant's own MCP server. Each change an agent makes is listed in the panel's Activity tab with the reason it gave.
- **Service and events**: `woow_serial.send` sends HEX or text and can wait for the reply; the events `woow_serial_frame` and `woow_serial_button` work as automation triggers.
- English and Traditional Chinese. No extra Python packages.

## Requirements

- Home Assistant 2026.10 or later (HAOS or container).
- On-board ports must be visible to Home Assistant (they are on HAOS on a Raspberry Pi 5).
- External devices: any integration that sends through a text entity and shows received data in a sensor. The HA-WF485-V3 is recognised automatically.

For CAN, use the separate [WOOW CAN](https://github.com/WOOWTECH/Woow_ha_can) integration.

## Installation

**HACS (recommended)**
1. HACS → menu → Custom repositories → `https://github.com/WOOWTECH/Woow_ha_serial`, category Integration.
2. Search for "WOOW Serial" and download it.
3. Restart Home Assistant.

**Manual**: copy `custom_components/woow_serial` into Home Assistant's `custom_components/` and restart.

## Setup

Settings → Devices & services → Add integration → WOOW Serial, then choose:

| Option | What it does |
|---|---|
| On-board serial port | Pick `/dev/ttySC0` etc. and set baud rate, data bits, parity and stop bits. RS485 drops its own echo by default |
| External device | Pick the device, e.g. an HA-WF485-V3; its send / receive entities are filled in. For other integrations, choose the entities yourself |
| Admin panel | Created automatically on first install. "WOOW Serial" appears in the sidebar |

Each port's settings can be changed later; the port reloads by itself.

## Admin panel

| Tab | Content |
|---|---|
| Overview | Port status and counters, a send box (with automatic checksum and wait-for-reply), live frames |
| Devices | Devices and keypads, and their editor |
| Monitor | Frames heard, grouped by sender |
| Send log | Frames sent, their origin, replies, and which other ports heard them |
| Activity | Who changed or sent what: agents and scripts (services), people in the panel, entity actions, with their reasons |

### Building a device

For a known model, choose "From template" on the Devices tab: pick the template and the port, fill in the address. Otherwise:

1. Operate the equipment once with its original remote or panel. The frame shows up in the Monitor.
2. Choose "Add to device" on that frame: an existing device, or a new one.
3. In the editor:
   - Pick the device type.
   - Map functions to commands (Open → the open command).
   - Optionally add state feedback rules.
4. Save. The entities appear and can be used on dashboards and in automations.

### Command templates

Write commands the way the protocol sheet prints them; braces put values in:

| Syntax | Meaning |
|---|---|
| `55 01 02 03 01` | Fixed HEX. Spaces, commas and `0x55` are fine |
| `{addr}` | A device parameter: HEX in HEX commands (a device address), text in text commands (an output number such as `2`) |
| `{value:u8}` | A value. Types: `u8 s8 u16 u16le s16 s16le u24 u32 u32le s32 s32le bcd bcd2` |
| `{crc16_modbus}` | A checksum over all bytes before it. `{sum8@1}` starts at the second byte |
| `PWR ON\r` | Text format: `\r \n \t \xHH` escapes; values as `{value:03d}` |

`{value}` comes from the entity (brightness, position, volume) and is scaled to the device's own numbers by the value ranges, e.g. volume 0–60 or a reversed 100–0.

Each command can also have:
- **Repeat** and a gap: how many times it is sent.
- **Wait for reply**: set it on every command the equipment answers (Modbus, most RS485 motors, RS232 AV gear). The port is held until the answer arrives (or the time is up), so the next request cannot collide with the answer on a half-duplex RS485 line. The built-in templates do this.
- **Then send**: another command a moment later, usually a query. Much equipment only acknowledges a setting (an Epson projector answers `:`), and the query tells the real state.

Checksums: `crc16_modbus`, `crc16_ccitt`, `crc16_xmodem`, `sum16`, `crc8`, `crc8_maxim`, `xor8`, `sum8`, `sum8_neg`.

### Receive patterns (state feedback, sensors, buttons)

| Syntax | Meaning |
|---|---|
| `??` | Any byte |
| `{pos:u8}` | Read a number, named `pos` |
| `{addr}` | Must equal the device parameter |
| `{crc16_modbus}` | The checksum must be right; frames with a wrong one are ignored |
| `*` | At the end: ignore the remaining bytes |
| `^PWR=(?P<p>\d+)` | Text format: a regular expression with named groups |

For example, a Dooya curtain reporting its position: `55 {addr} 01 01 {pos:u8} {crc16_modbus}`, state "Position", value `{pos}`. "Try" in the editor tests a pattern on the frames in the monitor.

- In text patterns `{param}` stands for a device parameter, e.g. `Out0*{output} In0*3 All` for an Extron matrix.
- **Only the reply to**: a Modbus answer does not name the register it answers, so each channel of a relay board should take only the answer to its own read. Choose this on the rule or sensor.
- A position or brightness read back outside the device's value range is ignored: a Dooya motor answers `FF` before its limits are set, which is not "fully open". A volume past the range counts as its end.

### Keypads

1. Add a device of type Keypad, or choose "Make a button" on a frame in the Monitor.
2. For each button, press Listen and then the physical button: the pattern fills itself in.
3. In the automation editor, pick Device → the keypad. Each button is a trigger: "'Scene 1' pressed".
4. To drive a device directly, choose it and an action under "Also does": toggle, open the curtain, pick a source, ...

Frames of the same button within 300 ms count as one press (adjustable), so holding a button fires about 3 times a second. A binding that fires more than 10 times in 5 seconds is paused for 60 seconds and logged, so a loop cannot run away.

## Service and events

```yaml
# Send and wait for the reply
action: woow_serial.send
data:
  config_entry_id: <the port, picked from a list in the UI>
  hex: "01 03 00 00 00 02 C4 0B"
  wait_ms: 1000
response_variable: r   # r.reply.hex, r.timeout
```

```yaml
# Trigger on given data
triggers:
  - trigger: event
    event_type: woow_serial_frame
    event_data:
      name: RS485-1
      hex: "A5 5A 01"
```

```yaml
# Other equipment is polled on the line: wait for the answer that matches
action: woow_serial.send
data:
  port: RS485-1
  hex: "04 04 00 01 00 02 20 5E"
  expect: "04 04 04 {t:s16} {h:u16} {crc16_modbus}"
  wait_ms: 2000
response_variable: r   # r.reply.captures.t = -55 (-5.5 °C)
```

`woow_serial_button` event data: `keypad`, `button`, `button_id`, `hex`, and every value the pattern reads.

## Built-in templates

| Template | Type | Line | Parameters |
|---|---|---|---|
| Dooya curtain motor (RS485, protocol A4) | Cover | 9600 8N1 | `addr`, factory `FE FE` |
| A-OK curtain motor (RS485) | Cover (reversed position, mapped) | 2400 8N1 | `id`, `ch` (channel mask) |
| Waveshare Modbus RTU relay (one channel) | Switch (a device per channel) | 9600 8N1 | `addr`, `coil` (`00 00`–`00 07`) |
| XY-MD02 temperature and humidity sensor | Sensors | 9600 8N1 | `addr` |
| Epson projector (ESC/VP21) | Media player | 9600 8N1 | — |
| BenQ projector | Media player | as set in its menu; TK860 ships at 115200 | — |
| Denon / Marantz AV receiver | Media player | 9600 8N1 | — |
| Extron matrix switcher output (SIS) | Select | 9600 8N1 | `output` |
| HDMI matrix output ("1V2." protocol) | Select | 9600 8N1 | `output` |

Each template names the maker's document it follows and site notes (address clashes, baud rate, direction). Your own templates go in `<config>/woow_serial/templates/*.json`, in the same format; one with the same id replaces the built-in one.

## For AI agents

Agents act without asking for confirmation; every change is listed in the Activity tab. The full guide for agents is [`llms.txt`](llms.txt). In short:

- **Connecting**
  - [ha-mcp](https://github.com/homeassistant-ai/ha-mcp): call `woow_serial.*` with `ha_call_service` and `return_response: true`.
  - Home Assistant's MCP server (admin): the services are also tools of the LLM API "WOOW Serial", named `woow-serial__<service>` when the server offers all LLM APIs, or served alone at `/api/mcp/woow_serial`.
- **Workflow**: `describe`, then `list_ports`. Known models: `list_templates`, `create_from_template`. Other equipment: learn it with `get_monitor`, `listen` or `learn_command` / `learn_button`, then `save_device`. Operate through the entities or `run_command`; check with `get_device`, `get_send_log`, `get_activity`.
- **Names work everywhere** in place of ids. A definition that cannot be saved comes back as a coded error to fix and resend.
- **Permissions**: configuration changes (saving, deleting, learning, creating from a template) need an admin user; operating equipment does not.
- Give each change a `note`: one sentence on why. It is shown in the activity log.

## Notes

- A port serves one program at a time: it is opened exclusively.
- The frame gap decides where one frame ends. Automatic is 24 character times, at least 20 ms. Raise it in the port settings for devices that pause inside a frame; the HA-WF485-V3 needs 100 ms.
- External devices report through a sensor entity: the same data twice in a row is only seen twice if the sensor goes back to its idle value (such as IDLE) in between. The HA-WF485-V3 does: it joins two frames less than about 0.1 s apart, and shows the same content again only after about 0.35 s (back at IDLE).
- Joined frames are taken apart: a received frame that matches no pattern as a whole but is made entirely of known frames (the HEX patterns of the port's devices, and frames we just sent that a device echoes) is handled piece by piece — a keypad sending a press twice back to back, or a key press joined to a poll answer by a WF485. A frame with any unknown byte is left alone, so no press is ever made up.
- Waits on external ports allow 0.5 s more, for the answer's trip through the other integration.
- RS485 is half duplex: equipment that sends by itself (wall keypads) can collide with polling. Keep poll intervals modest.

## Development

```bash
cd frontend && npm install && npm run build   # panel (Lit + TypeScript + rollup), built into custom_components/woow_serial/frontend/
pip install homeassistant==2026.10.1 pytest && pytest tests   # unit tests
```

- `tests/test_templates.py`: every built-in template's frames against the maker's documented examples, byte for byte.
- `tests/test_sim_bus.py`: a virtual bus. The templates drive simulated equipment written separately from the same documents (`tools/sim/protocols.py`), so each checks the other — no hardware, runs in CI.
- `tools/sim/matrix.py`: the live test matrix on two RS485 / RS232 loops, with the on-board port and an HA-WF485-V3 taking turns as the controller and the simulator on the other end, driven through the services an agent uses.
- The rest of `tools/` are checks and live tests used on real hardware.

## License

MIT. The admin panel follows the approach of [HAIR](https://github.com/DAB-LABS/HAIR) by DAB-LABS (MIT).
