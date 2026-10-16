// Types and websocket calls shared by the panel views (backend: websocket_api.py).

export interface HomeAssistant {
  connection: {
    subscribeMessage<T>(callback: (msg: T) => void, msg: Record<string, unknown>): Promise<() => Promise<void>>;
  };
  callWS<T>(msg: Record<string, unknown>): Promise<T>;
  language: string;
  locale?: { language: string };
}

export interface PortInfo {
  id: string;
  name: string;
  kind: "serial" | "external";
  port: string;
  model: string;
  settings: string;
  available: boolean;
  rx_frames?: number;
  tx_frames?: number;
  rx_bytes?: number;
  tx_bytes?: number;
  errors?: number;
  tx_entity?: string;
  rx_entity?: string;
}

export interface Group {
  id: string;
  port_id: string;
  key: string;
  alias: string;
  hidden: boolean;
  order: number;
  count: number;
  first_seen: number;
  last_seen: number;
  rows: number;
  checksum: string | null;
  rate: number;
}

export interface Row {
  id: string;
  group_id: string;
  port_id: string;
  hex: string;
  length: number;
  text: string | null;
  checks: string[];
  alias: string;
  count: number;
  first_seen: number;
  last_seen: number;
}

export interface Sent {
  id: string;
  port_id: string;
  hex: string;
  length: number;
  text: string | null;
  count: number;
  first_sent: number;
  last_sent: number;
  origin: string;
  origins: Record<string, number>;
  replies: number;
  reply: string | null;
  reply_ms: number | null;
  heard_by: Record<string, number>;
}

export interface LiveFrame {
  t: number;
  port: string;
  dir: "rx" | "tx";
  hex: string;
  text: string | null;
  origin: string | null;
  echo: boolean;
}

export type Format = "hex" | "text";

export interface Command {
  id: string;
  name: string;
  payload: string;
  format: Format;
  repeat: number;
  gap_ms: number;
  wait_ms: number;
}

export interface Rule {
  id: string;
  pattern: string;
  format: Format;
  field: string;
  value: string;
}

export interface SensorDef {
  id: string;
  name: string;
  pattern: string;
  format: Format;
  capture: string;
  scale: number;
  offset: number;
  unit: string;
  device_class: string;
  precision: number | null;
}

export interface OptionDef {
  name: string;
  command: string;
}

export interface Button {
  id: string;
  name: string;
  pattern: string;
  format: Format;
  debounce_ms: number;
  target: string;
  action: string;
  value: number | null;
  alias_history?: string[];
}

export interface Device {
  id: string;
  name: string;
  type: string;
  port_id: string;
  manufacturer: string;
  model: string;
  params: Record<string, string>;
  commands: Command[];
  actions: Record<string, string>;
  options: OptionDef[];
  rules: Rule[];
  sensors: SensorDef[];
  buttons: Button[];
  ranges: Record<string, [number, number]>;
  poll_command: string;
  poll_interval: number;
  entities?: string[];
  bindable?: string[];
}

export interface DeviceType {
  platform: string | null;
  actions: string[];
  fields: string[];
  options?: boolean;
  buttons?: boolean;
}

export type DeviceState = Record<string, unknown>;

export interface DevicesSnapshot {
  devices: Device[];
  states: Record<string, DeviceState>;
  types: Record<string, DeviceType>;
  value_actions: Record<string, string>;
}

/** An error the backend explains with a code (devices.DeviceError / template.TemplateError). */
export interface CodedError {
  code: string;
  [key: string]: unknown;
}

export interface Snapshot {
  ports: PortInfo[];
  catalog: { groups: Group[]; rows: Row[]; prefix: Record<string, number> };
  mirror: { rows: Sent[] };
  devices: DevicesSnapshot;
}

export type FeedEvent =
  | { kind: "frames"; frames: LiveFrame[]; dropped: number }
  | { kind: "ports"; ports: PortInfo[]; removed: string[] }
  | { kind: "catalog"; groups: Group[]; rows: Row[]; removed: string[] }
  | { kind: "mirror"; rows: Sent[]; removed: string[] }
  | { kind: "devices"; devices: Device[]; removed: string[] }
  | { kind: "device_state"; states: Record<string, DeviceState> };

export interface SendResult {
  sent: string;
  reply: string | null;
  timeout: boolean;
}

export interface SendPayload {
  hex?: string;
  text?: string;
  wait_ms?: number;
}

export class Api {
  constructor(private readonly hass: () => HomeAssistant) {}

  subscribe(callback: (event: FeedEvent) => void): Promise<() => Promise<void>> {
    return this.hass().connection.subscribeMessage<FeedEvent>(callback, { type: "woow_serial/subscribe" });
  }

  snapshot(): Promise<Snapshot> {
    return this.hass().callWS({ type: "woow_serial/snapshot" });
  }

  send(portId: string, payload: SendPayload): Promise<SendResult> {
    return this.hass().callWS({ type: "woow_serial/send", port_id: portId, ...payload });
  }

  /** The checksum value to append, or (without an algorithm) the ones a frame already ends in. */
  checksum(hex: string, algorithm?: string, start = 0): Promise<{ detected: string[]; value?: string; frame?: string }> {
    return this.hass().callWS({ type: "woow_serial/checksum", hex, start, ...(algorithm ? { algorithm } : {}) });
  }

  updateGroup(groupId: string, changes: { alias?: string; hidden?: boolean; order?: number }): Promise<void> {
    return this.hass().callWS({ type: "woow_serial/catalog/update_group", group_id: groupId, ...changes });
  }

  updateRow(rowId: string, alias: string): Promise<void> {
    return this.hass().callWS({ type: "woow_serial/catalog/update_row", row_id: rowId, alias });
  }

  deleteGroup(groupId: string): Promise<void> {
    return this.hass().callWS({ type: "woow_serial/catalog/delete", group_id: groupId });
  }

  deleteRow(rowId: string): Promise<void> {
    return this.hass().callWS({ type: "woow_serial/catalog/delete", row_id: rowId });
  }

  clearCatalog(portId?: string): Promise<void> {
    return this.hass().callWS({ type: "woow_serial/catalog/clear", ...(portId ? { port_id: portId } : {}) });
  }

  setPrefix(portId: string, length: number): Promise<void> {
    return this.hass().callWS({ type: "woow_serial/catalog/prefix", port_id: portId, length });
  }

  deleteSent(rowId?: string): Promise<void> {
    return this.hass().callWS({ type: "woow_serial/mirror/delete", ...(rowId ? { row_id: rowId } : {}) });
  }

  saveDevice(device: Partial<Device>): Promise<{ device?: Device; error?: CodedError }> {
    return this.hass().callWS({ type: "woow_serial/devices/save", device });
  }

  deleteDevice(deviceId: string): Promise<void> {
    return this.hass().callWS({ type: "woow_serial/devices/delete", device_id: deviceId });
  }

  runCommand(deviceId: string, commandId: string, value?: number): Promise<{ sent: string; reply: string | null }> {
    return this.hass().callWS({
      type: "woow_serial/devices/run",
      device_id: deviceId,
      command_id: commandId,
      ...(value === undefined ? {} : { value }),
    });
  }

  preview(payload: string, format: Format, params: Record<string, string>, value?: number): Promise<{ sent?: string; fields?: string[]; error?: CodedError }> {
    return this.hass().callWS({
      type: "woow_serial/template/preview",
      payload,
      format,
      params,
      ...(value === undefined ? {} : { value }),
    });
  }

  /** The next frame the port hears, e.g. a keypad press to learn (null on timeout). */
  async listen(portId: string, timeout = 15): Promise<{ hex: string; text: string | null } | null> {
    const res = await this.hass().callWS<{ hex?: string; text?: string | null; timeout?: boolean }>({
      type: "woow_serial/listen",
      port_id: portId,
      timeout,
    });
    return res.hex ? { hex: res.hex, text: res.text ?? null } : null;
  }

  testPattern(pattern: string, format: Format, portId: string, params: Record<string, string>): Promise<{
    matches?: { frame: string; captures: Record<string, unknown> }[];
    captures?: string[];
    error?: CodedError;
  }> {
    return this.hass().callWS({ type: "woow_serial/pattern/test", pattern, format, port_id: portId, params });
  }
}

export function newId(): string {
  return Math.random().toString(16).slice(2, 14).padEnd(12, "0");
}

export function errorText(err: unknown): string {
  if (err && typeof err === "object" && "message" in err) {
    return String((err as { message: unknown }).message);
  }
  return String(err);
}

/** Copy that also works over plain http (navigator.clipboard needs a secure context). */
export function copyText(text: string): void {
  if (navigator.clipboard && window.isSecureContext) {
    void navigator.clipboard.writeText(text);
    return;
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  document.execCommand("copy");
  area.remove();
}

/** Define a custom element once, so a reloaded bundle does not throw on the second define. */
export function define(name: string, cls: CustomElementConstructor): void {
  if (!customElements.get(name)) {
    customElements.define(name, cls);
  }
}
