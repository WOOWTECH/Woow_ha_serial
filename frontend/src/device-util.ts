// Helpers shared by the device list, the editor and the panel.

import { Device, DeviceState, Format, Row } from "./api";
import { Translate } from "./i18n";

export function blankDevice(portId: string): Device {
  return {
    id: "",
    name: "",
    type: "switch",
    port_id: portId,
    manufacturer: "",
    model: "",
    params: {},
    commands: [],
    actions: {},
    options: [],
    rules: [],
    sensors: [],
    buttons: [],
    ranges: {},
    poll_command: "",
    poll_interval: 0,
  };
}

/** Short, human chips for a device's live state ("On", "Position 30 %", "Voltage 52.1 V"). */
export function stateSummary(device: Device, data: DeviceState | undefined, t: Translate): string[] {
  if (!data) return [];
  const out: string[] = [];
  if (typeof data.power === "boolean") out.push(data.power ? t("state_on") : t("state_off"));
  if (typeof data.position === "number") out.push(t("state_position", { n: Math.round(data.position) }));
  if (typeof data.brightness === "number") out.push(t("state_brightness", { n: Math.round((data.brightness / 255) * 100) }));
  if (typeof data.volume === "number") out.push(t("state_volume", { n: Math.round(data.volume * 100) }));
  if (data.mute === true) out.push(t("state_muted"));
  for (const key of ["source", "option"]) if (typeof data[key] === "string") out.push(String(data[key]));
  if (typeof data.last_button === "string") out.push(t("state_last_button", { x: data.last_button }));
  for (const sensor of device.sensors.slice(0, 4)) {
    const value = data[`sensor:${sensor.id}`];
    if (value !== undefined && value !== null) out.push(`${sensor.name} ${value}${sensor.unit ? ` ${sensor.unit}` : ""}`);
  }
  return out;
}

/** A monitor row as a receive pattern: the exact bytes, or the exact text as a regular expression. */
export function frameAsPattern(hex: string, text: string | null): { pattern: string; format: Format } {
  if (text) {
    // printable() already writes \r, \n, \xHH, \\ the way a regular expression reads them; escape the rest.
    return { pattern: `^${text.replace(/[.*+?^$\{}()|[\]]/g, "\\$&")}$`, format: "text" };
  }
  return { pattern: hex, format: "hex" };
}

export function rowAsPattern(row: Row): { pattern: string; format: Format } {
  return frameAsPattern(row.hex, row.text);
}

/** A monitor row as a command: readable text, or HEX. */
export function rowAsCommand(row: Row): { payload: string; format: Format } {
  if (row.text) return { payload: row.text, format: "text" };
  return { payload: row.hex, format: "hex" };
}
