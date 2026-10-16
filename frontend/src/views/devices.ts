// Devices tab (HAIR's Devices): the managed devices, their live state, and the editor.

import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";

import { Api, Device, DeviceState, DeviceType, PortInfo, TemplateSummary, define, errorText } from "../api";
import { blankDevice, stateSummary } from "../device-util";
import { Translate, explain, isKey } from "../i18n";
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
  @property({ attribute: false }) templates: TemplateSummary[] = [];

  @state() private editing: Device | null = null;
  @state() private picking = false;
  @state() private templateId = "";
  @state() private portId = "";
  @state() private newName = "";
  @state() private params: Record<string, string> = {};
  @state() private pickNote = "";

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
        width: min(520px, 100%);
        max-height: 90vh;
        overflow: auto;
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

  private choose(id: string): void {
    const template = this.templates.find((x) => x.id === id);
    this.templateId = id;
    this.params = Object.fromEntries((template?.params ?? []).map((p) => [p.key, p.default]));
    this.newName = "";
    this.pickNote = "";
  }

  private async createFromTemplate(): Promise<void> {
    const t = this.t;
    if (!this.templateId || !this.portId) return;
    try {
      const res = await this.api.createFromTemplate(this.templateId, this.portId, this.newName.trim(), this.params);
      if (res.error) {
        this.pickNote = explain(res.error, t);
        return;
      }
      this.picking = false;
      if (res.device) this.editing = res.device;
    } catch (err) {
      this.pickNote = t("error", { msg: errorText(err) });
    }
  }

  private renderPicker() {
    const t = this.t;
    const template = this.templates.find((x) => x.id === this.templateId);
    return html`<div class="scrim" @click=${(e: Event) => e.target === e.currentTarget && (this.picking = false)}>
      <div class="dialog">
        <h2>${t("from_template")}</h2>
        <label>${t("template")}
          <select @change=${(e: Event) => this.choose((e.target as HTMLSelectElement).value)}>
            <option value="" ?selected=${!this.templateId}>—</option>
            ${this.templates.map(
              (x) => html`<option value=${x.id} ?selected=${x.id === this.templateId}>${this.typeLabel(x.type)} · ${x.name}</option>`,
            )}
          </select>
        </label>
        ${template
          ? html`<div class="muted">${template.description}</div>
              ${template.notes ? html`<div class="muted">${template.notes}</div>` : nothing}
              <div class="muted mono">${t("template_port", { x: Object.entries(template.port).map(([k, v]) => `${k}=${v}`).join(" ") })}</div>
              <label>${t("port")}
                <select @change=${(e: Event) => (this.portId = (e.target as HTMLSelectElement).value)}>
                  <option value="" ?selected=${!this.portId}>—</option>
                  ${this.ports.map((p) => html`<option value=${p.id} ?selected=${p.id === this.portId}>${p.name} · ${p.settings}</option>`)}
                </select>
              </label>
              <label>${t("name")}<input .value=${this.newName} placeholder=${template.name}
                @input=${(e: Event) => (this.newName = (e.target as HTMLInputElement).value)} /></label>
              ${template.params.map(
                (p) => html`<label>${p.key}${p.description ? ` — ${p.description}` : ""}
                  <input class="mono" .value=${this.params[p.key] ?? ""}
                    @input=${(e: Event) => (this.params = { ...this.params, [p.key]: (e.target as HTMLInputElement).value })} />
                </label>`,
              )}`
          : nothing}
        ${this.pickNote ? html`<div class="chip bad" style="white-space:normal">${this.pickNote}</div>` : nothing}
        <div class="row">
          <span class="grow"></span>
          <button @click=${() => (this.picking = false)}>${t("cancel")}</button>
          <button class="primary" ?disabled=${!template || !this.portId} @click=${() => this.createFromTemplate()}>${t("create")}</button>
        </div>
      </div>
    </div>`;
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
        ${this.templates.length
          ? html`<button ?disabled=${!this.ports.length} @click=${() => {
              this.picking = true;
              this.portId = this.portId || this.ports[0]?.id || "";
            }}>${t("from_template")}</button>`
          : nothing}
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
    </div>
    ${this.picking ? this.renderPicker() : nothing}`;
  }
}

define("woow-serial-devices", WoowBusDevices);
