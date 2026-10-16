// Devices tab (HAIR's Devices): the managed devices, their live state, and the editor.

import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";

import { Api, Device, DeviceState, DeviceType, PortInfo, define } from "../api";
import { blankDevice, stateSummary } from "../device-util";
import { Translate, isKey } from "../i18n";
import { shared } from "../styles";
import "./device-editor";

export class WoowBusDevices extends LitElement {
  @property({ attribute: false }) devices: Device[] = [];
  @property({ attribute: false }) states: Record<string, DeviceState> = {};
  @property({ attribute: false }) types: Record<string, DeviceType> = {};
  @property({ attribute: false }) valueActions: Record<string, string> = {};
  @property({ attribute: false }) ports: PortInfo[] = [];
  @property({ attribute: false }) now = 0;
  @property({ attribute: false }) t!: Translate;
  @property({ attribute: false }) api!: Api;
  @property({ attribute: false }) portName!: (id: string) => string;
  /** A device to open in the editor (set by the panel, e.g. "Add to device" → new device). */
  @property({ attribute: false }) open: Device | null = null;

  @state() private editing: Device | null = null;

  static styles = [
    shared,
    css`
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
        gap: 12px;
      }
      .dev {
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 10px;
        padding: 12px;
        display: grid;
        gap: 6px;
        cursor: pointer;
        background: var(--card-background-color, #fff);
      }
      .dev:hover {
        border-color: var(--primary-color);
      }
      .state {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
      }
    `,
  ];

  protected willUpdate(changed: Map<string, unknown>): void {
    if (changed.has("open") && this.open) {
      this.editing = this.open;
      this.dispatchEvent(new CustomEvent("opened", { bubbles: true, composed: true }));
    }
  }

  private typeLabel(type: string): string {
    const key = `type_${type}`;
    return isKey(key) ? this.t(key) : type;
  }

  private close(): void {
    this.editing = null;
  }

  render() {
    const t = this.t;
    if (this.editing) {
      const current = this.editing.id ? this.devices.find((d) => d.id === this.editing?.id) ?? this.editing : this.editing;
      return html`<woow-serial-device-editor
        .device=${current}
        .devices=${this.devices}
        .types=${this.types}
        .valueActions=${this.valueActions}
        .ports=${this.ports}
        .state=${this.states[current.id]}
        .t=${this.t}
        .api=${this.api}
        .portName=${this.portName}
        @close=${this.close}
      ></woow-serial-device-editor>`;
    }
    const devices = [...this.devices].sort((a, b) => a.name.localeCompare(b.name));
    return html`<div class="card">
      <div class="row" style="margin-bottom:12px">
        <h2 class="grow" style="margin:0">${t("tab_devices")}</h2>
        <button class="primary" ?disabled=${!this.ports.length} @click=${() => (this.editing = blankDevice(this.ports[0]?.id ?? ""))}>
          ${t("add_device")}
        </button>
      </div>
      ${devices.length === 0
        ? html`<div class="empty">${t("devices_empty")}</div>`
        : html`<div class="grid">
            ${devices.map((d) => {
              const summary = stateSummary(d, this.states[d.id], t);
              return html`<div class="dev" @click=${() => (this.editing = d)}>
                <div class="row"><b class="grow">${d.name}</b><span class="chip">${this.typeLabel(d.type)}</span></div>
                <div class="muted">${this.portName(d.port_id)}${d.manufacturer || d.model ? ` · ${[d.manufacturer, d.model].filter(Boolean).join(" ")}` : ""}</div>
                ${summary.length ? html`<div class="state">${summary.map((s) => html`<span class="chip info">${s}</span>`)}</div>` : nothing}
                <div class="muted">${t("entities_count", { n: d.entities?.length ?? 0 })}</div>
              </div>`;
            })}
          </div>`}
    </div>`;
  }
}

define("woow-serial-devices", WoowBusDevices);
