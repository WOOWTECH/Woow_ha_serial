// WOOW Serial sidebar panel. Holds the state; the tabs render it.
// Data: one snapshot, then a live feed (woow_serial/subscribe) of frames, ports, monitor, send log,
// devices and device states.

import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";

import {
  Api,
  Device,
  DeviceState,
  DeviceType,
  FeedEvent,
  Group,
  HomeAssistant,
  LiveFrame,
  PortInfo,
  Row,
  Sent,
  define,
  errorText,
  newId,
} from "./api";
import { blankDevice, rowAsCommand, rowAsPattern } from "./device-util";
import { Key, Translate, explain, makeTranslate } from "./i18n";
import { shared } from "./styles";
import "./views/devices";
import "./views/monitor";
import "./views/overview";
import "./views/sendlog";

type Tab = "overview" | "devices" | "monitor" | "sendlog";
const TABS: Tab[] = ["overview", "devices", "monitor", "sendlog"];
const LIVE_KEEP = 300;
const KIND_ORDER: Record<string, number> = { serial: 0, external: 1 };
const MENU = "M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z";
const NEW = "__new__";

export class WoowBusPanel extends LitElement {
  @property({ attribute: false }) narrow = false;
  @property({ attribute: false }) route?: unknown;
  @property({ attribute: false }) panel?: unknown;

  @state() private tab: Tab = "overview";
  @state() private ports: Record<string, PortInfo> = {};
  @state() private groups: Record<string, Group> = {};
  @state() private rows: Record<string, Row> = {};
  @state() private groupPrefix: Record<string, number> = {};
  @state() private sent: Record<string, Sent> = {};
  @state() private devices: Record<string, Device> = {};
  @state() private deviceStates: Record<string, DeviceState> = {};
  @state() private deviceTypes: Record<string, DeviceType> = {};
  @state() private valueActions: Record<string, string> = {};
  @state() private openDevice: Device | null = null;
  @state() private live: LiveFrame[] = [];
  @state() private dropped = 0;
  @state() private paused = false;
  @state() private loaded = false;
  @state() private error = "";
  @state() private now = Date.now();
  // "Add to device" dialog
  @state() private addRow: Row | null = null;
  @state() private addMode: "command" | "button" = "command";
  @state() private addTarget = NEW;
  @state() private addName = "";
  @state() private addNote = "";

  private _hass?: HomeAssistant;
  private t: Translate = makeTranslate("en");
  private readonly api = new Api(() => this._hass as HomeAssistant);
  private unsubscribe?: () => Promise<void>;
  private connecting = false;
  private ticker?: number;

  static styles = [
    shared,
    css`
      :host {
        min-height: 100vh;
        background: var(--primary-background-color);
      }
      .toolbar {
        display: flex;
        align-items: center;
        gap: 8px;
        height: 56px;
        padding: 0 16px;
        background: var(--app-header-background-color, var(--primary-color));
        color: var(--app-header-text-color, var(--text-primary-color, #fff));
        font-size: 20px;
      }
      .toolbar button {
        border: none;
        background: none;
        color: inherit;
        padding: 8px;
        line-height: 0;
      }
      .tabs {
        display: flex;
        gap: 4px;
        padding: 0 12px;
        background: var(--app-header-background-color, var(--primary-color));
        overflow-x: auto;
      }
      .tab {
        border: none;
        border-bottom: 3px solid transparent;
        border-radius: 0;
        background: none;
        color: var(--app-header-text-color, var(--text-primary-color, #fff));
        opacity: 0.75;
        padding: 10px 14px;
        white-space: nowrap;
      }
      .tab.active {
        opacity: 1;
        border-bottom-color: var(--app-header-text-color, var(--text-primary-color, #fff));
      }
      .content {
        max-width: 1200px;
        margin: 0 auto;
        padding: 16px;
      }
      .count {
        margin-left: 6px;
        font-size: 0.8em;
        opacity: 0.85;
      }
      .scrim {
        position: fixed;
        inset: 0;
        z-index: 10;
        background: rgba(0, 0, 0, 0.4);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 16px;
      }
      .dialog {
        width: min(460px, 100%);
        background: var(--card-background-color, #fff);
        border-radius: 12px;
        padding: 20px;
        display: grid;
        gap: 12px;
      }
      .dialog h2 {
        margin: 0;
        font-size: 1.15em;
        font-weight: 500;
      }
      .dialog label {
        display: grid;
        gap: 4px;
        font-size: 0.85em;
        color: var(--secondary-text-color);
      }
      .dialog input,
      .dialog select {
        font-size: 1.05em;
      }
    `,
  ];

  set hass(hass: HomeAssistant) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this.t = makeTranslate(hass.locale?.language ?? hass.language ?? "en");
      if (this.isConnected) void this.connect();
      this.requestUpdate();
    }
  }

  get hass(): HomeAssistant {
    return this._hass as HomeAssistant;
  }

  connectedCallback(): void {
    super.connectedCallback();
    if (this._hass && !this.unsubscribe) void this.connect();
    this.ticker = window.setInterval(() => (this.now = Date.now()), 5000);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    window.clearInterval(this.ticker);
    void this.unsubscribe?.();
    this.unsubscribe = undefined;
  }

  private async connect(): Promise<void> {
    if (this.connecting || this.unsubscribe) return;
    this.connecting = true;
    try {
      // Subscribe first: updates that race the snapshot are upserts, so nothing is lost.
      this.unsubscribe = await this.api.subscribe((event) => this.onEvent(event));
      const snap = await this.api.snapshot();
      this.ports = Object.fromEntries(snap.ports.map((p) => [p.id, p]));
      this.groups = Object.fromEntries(snap.catalog.groups.map((g) => [g.id, g]));
      this.rows = Object.fromEntries(snap.catalog.rows.map((r) => [r.id, r]));
      this.groupPrefix = snap.catalog.prefix;
      this.sent = Object.fromEntries(snap.mirror.rows.map((r) => [r.id, r]));
      this.devices = Object.fromEntries(snap.devices.devices.map((d) => [d.id, d]));
      this.deviceStates = snap.devices.states;
      this.deviceTypes = snap.devices.types;
      this.valueActions = snap.devices.value_actions;
      this.loaded = true;
      this.error = "";
    } catch (err) {
      this.error = errorText(err);
    } finally {
      this.connecting = false;
    }
  }

  private onEvent(event: FeedEvent): void {
    switch (event.kind) {
      case "frames":
        if (!this.paused) {
          this.live = [...event.frames.reverse(), ...this.live].slice(0, LIVE_KEEP);
          this.dropped += event.dropped;
        }
        break;
      case "ports": {
        const ports = { ...this.ports };
        for (const p of event.ports) ports[p.id] = p;
        for (const id of event.removed) delete ports[id];
        this.ports = ports;
        break;
      }
      case "catalog": {
        const groups = { ...this.groups };
        const rows = { ...this.rows };
        for (const g of event.groups) groups[g.id] = g;
        for (const r of event.rows) rows[r.id] = r;
        for (const id of event.removed) {
          delete groups[id];
          delete rows[id];
        }
        this.groups = groups;
        this.rows = rows;
        break;
      }
      case "mirror": {
        const sent = { ...this.sent };
        for (const r of event.rows) sent[r.id] = r;
        for (const id of event.removed) delete sent[id];
        this.sent = sent;
        break;
      }
      case "devices": {
        const devices = { ...this.devices };
        for (const d of event.devices) devices[d.id] = d;
        for (const id of event.removed) delete devices[id];
        this.devices = devices;
        break;
      }
      case "device_state":
        this.deviceStates = { ...this.deviceStates, ...event.states };
        break;
    }
  }

  private onLiveControl(e: CustomEvent<"pause" | "resume" | "clear">): void {
    if (e.detail === "clear") {
      this.live = [];
      this.dropped = 0;
    } else {
      this.paused = e.detail === "pause";
    }
  }

  private readonly portName = (id: string): string => this.ports[id]?.name ?? "?";
  private readonly deviceName = (id: string): string | undefined => this.devices[id]?.name;

  private get portList(): PortInfo[] {
    return Object.values(this.ports).sort(
      (a, b) => (KIND_ORDER[a.kind] ?? 9) - (KIND_ORDER[b.kind] ?? 9) || a.name.localeCompare(b.name),
    );
  }

  private toggleMenu(): void {
    this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
  }

  // ---- "Add to device" / "Make a button" (from the monitor) -----------------------------
  private candidates(row: Row, mode: "command" | "button"): Device[] {
    return Object.values(this.devices).filter(
      (d) => d.port_id === row.port_id && (mode === "button" ? d.type === "keypad" : d.type !== "keypad"),
    );
  }

  private startAdd(row: Row, mode: "command" | "button" = "command"): void {
    const onPort = this.candidates(row, mode);
    this.addMode = mode;
    this.addRow = row;
    this.addTarget = onPort[0]?.id ?? NEW;
    this.addName = row.alias || "";
    this.addNote = "";
  }

  private async confirmAdd(): Promise<void> {
    const row = this.addRow;
    if (!row) return;
    const t = this.t;
    const name = this.addName.trim() || row.hex.slice(0, 20);
    const button = this.addMode === "button";
    const command = { id: newId(), name, repeat: 1, gap_ms: 100, wait_ms: 0, ...rowAsCommand(row) };
    const pressed = { id: newId(), name, debounce_ms: 300, target: "", action: "", value: null, ...rowAsPattern(row) };
    if (this.addTarget === NEW) {
      // A new device opens in the editor, unsaved, so its name and type get chosen first.
      this.openDevice = button
        ? { ...blankDevice(row.port_id), type: "keypad", buttons: [pressed] }
        : { ...blankDevice(row.port_id), type: "other", commands: [command] };
      this.addRow = null;
      this.tab = "devices";
      return;
    }
    const device = this.devices[this.addTarget];
    if (!device) return;
    const changed = button
      ? { ...structuredClone(device), buttons: [...device.buttons, pressed] }
      : { ...structuredClone(device), commands: [...device.commands, command] };
    delete changed.entities;
    delete changed.bindable;
    try {
      const res = await this.api.saveDevice(changed);
      if (res.error) {
        this.addNote = explain(res.error, t);
        return;
      }
      this.addRow = null;
    } catch (err) {
      this.addNote = t("error", { msg: errorText(err) });
    }
  }

  private renderAddDialog() {
    const row = this.addRow;
    if (!row) return nothing;
    const t = this.t;
    const button = this.addMode === "button";
    const onPort = this.candidates(row, this.addMode);
    return html`<div class="scrim" @click=${(e: Event) => e.target === e.currentTarget && (this.addRow = null)}>
      <div class="dialog">
        <h2>${button ? t("make_button") : t("add_to_device")}</h2>
        <div class="mono">${row.hex}${row.text ? html` <span class="muted">"${row.text}"</span>` : nothing}</div>
        <label
          >${button ? t("choose_keypad") : t("choose_device")}
          <select @change=${(e: Event) => (this.addTarget = (e.target as HTMLSelectElement).value)}>
            ${onPort.map((d) => html`<option value=${d.id} ?selected=${d.id === this.addTarget}>${d.name}</option>`)}
            <option value=${NEW} ?selected=${this.addTarget === NEW}>${button ? t("new_keypad") : t("new_device")}</option>
          </select>
        </label>
        <label
          >${button ? t("button_name") : t("command_name")}
          <input .value=${this.addName} @input=${(e: Event) => (this.addName = (e.target as HTMLInputElement).value)}
            @keydown=${(e: KeyboardEvent) => e.key === "Enter" && this.confirmAdd()} />
        </label>
        ${this.addNote ? html`<div class="chip bad" style="white-space:normal">${this.addNote}</div>` : nothing}
        <div class="row">
          <span class="grow"></span>
          <button @click=${() => (this.addRow = null)}>${t("cancel")}</button>
          <button class="primary" @click=${() => this.confirmAdd()}>${button ? t("make_button") : t("add_to_device")}</button>
        </div>
      </div>
    </div>`;
  }

  // ---- tabs ---------------------------------------------------------------------------
  private renderTab() {
    const ports = this.portList;
    switch (this.tab) {
      case "devices":
        return html`<woow-serial-devices
          .devices=${Object.values(this.devices)}
          .states=${this.deviceStates}
          .types=${this.deviceTypes}
          .valueActions=${this.valueActions}
          .ports=${ports}
          .now=${this.now}
          .t=${this.t}
          .api=${this.api}
          .portName=${this.portName}
          .open=${this.openDevice}
          @opened=${() => (this.openDevice = null)}
        ></woow-serial-devices>`;
      case "monitor":
        return html`<woow-serial-monitor
          .ports=${ports}
          .groups=${Object.values(this.groups)}
          .rows=${Object.values(this.rows)}
          .groupPrefix=${this.groupPrefix}
          .now=${this.now}
          .t=${this.t}
          .api=${this.api}
          .portName=${this.portName}
          @prefix-changed=${(e: CustomEvent<{ portId: string; length: number }>) =>
            (this.groupPrefix = { ...this.groupPrefix, [e.detail.portId]: e.detail.length })}
          @add-to-device=${(e: CustomEvent<Row>) => this.startAdd(e.detail)}
          @make-button=${(e: CustomEvent<Row>) => this.startAdd(e.detail, "button")}
        ></woow-serial-monitor>`;
      case "sendlog":
        return html`<woow-serial-sendlog
          .sent=${Object.values(this.sent)}
          .ports=${ports}
          .now=${this.now}
          .t=${this.t}
          .api=${this.api}
          .portName=${this.portName}
          .deviceName=${this.deviceName}
        ></woow-serial-sendlog>`;
      default:
        return html`<woow-serial-overview
          .ports=${ports}
          .live=${this.live}
          .dropped=${this.dropped}
          .paused=${this.paused}
          .t=${this.t}
          .api=${this.api}
          .portName=${this.portName}
          .deviceName=${this.deviceName}
          @live-control=${this.onLiveControl}
        ></woow-serial-overview>`;
    }
  }

  render() {
    const t = this.t;
    const counts: Partial<Record<Tab, number>> = {
      devices: Object.keys(this.devices).length,
      monitor: Object.keys(this.groups).length,
      sendlog: Object.keys(this.sent).length,
    };
    return html`
      <div class="toolbar">
        ${this.narrow
          ? html`<button @click=${this.toggleMenu} aria-label="menu">
              <svg viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d=${MENU}></path></svg>
            </button>`
          : nothing}
        <div>${t("title")}</div>
      </div>
      <div class="tabs">
        ${TABS.map(
          (tab) => html`<button class="tab ${this.tab === tab ? "active" : ""}" @click=${() => (this.tab = tab)}>
            ${t(`tab_${tab}` as Key)}${counts[tab] ? html`<span class="count">${counts[tab]}</span>` : nothing}
          </button>`,
        )}
      </div>
      <div class="content">
        ${this.error
          ? html`<div class="card"><div class="chip bad">${t("error", { msg: this.error })}</div></div>`
          : this.loaded
            ? this.renderTab()
            : html`<div class="empty">${t("loading")}</div>`}
      </div>
      ${this.renderAddDialog()}
    `;
  }
}

define("woow-serial-panel", WoowBusPanel);
