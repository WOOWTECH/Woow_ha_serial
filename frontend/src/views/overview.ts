// Overview tab: port cards, a send box, and the live frame feed.

import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";

import { Api, LiveFrame, PortInfo, SendPayload, define, errorText } from "../api";
import { Translate, checksumLabel, clock, originLabel } from "../i18n";
import { shared } from "../styles";

const CHECKSUMS = ["crc16_modbus", "crc16_ccitt", "crc16_xmodem", "sum16", "crc8", "crc8_maxim", "xor8", "sum8", "sum8_neg"];
const value = (e: Event) => (e.target as HTMLInputElement).value;

export class WoowBusOverview extends LitElement {
  @property({ attribute: false }) ports: PortInfo[] = [];
  @property({ attribute: false }) live: LiveFrame[] = [];
  @property({ attribute: false }) dropped = 0;
  @property({ attribute: false }) paused = false;
  @property({ attribute: false }) t!: Translate;
  @property({ attribute: false }) api!: Api;
  @property({ attribute: false }) portName!: (id: string) => string;
  @property({ attribute: false }) deviceName: (id: string) => string | undefined = () => undefined;

  @state() private portId = "";
  @state() private mode: "hex" | "text" = "hex";
  @state() private payload = "";
  @state() private algorithm = "";
  @state() private start = 0;
  @state() private waitMs = 500;
  @state() private busy = false;
  @state() private result: { ok: boolean; text: string } | null = null;
  @state() private liveFilter = "";

  static styles = [
    shared,
    css`
      .ports {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
        gap: 12px;
      }
      .port {
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 10px;
        padding: 10px 12px;
        display: grid;
        gap: 4px;
      }
      .dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--error-color, #db4437);
        flex: none;
      }
      .dot.on {
        background: var(--success-color, #43a047);
      }
      .result {
        margin-top: 10px;
        padding: 8px 10px;
        border-radius: 8px;
        background: rgba(67, 160, 71, 0.12);
      }
      .result.bad {
        background: rgba(219, 68, 55, 0.12);
      }
      .live {
        max-height: 60vh;
        overflow: auto;
        margin-top: 8px;
      }
      .lrow {
        display: flex;
        align-items: baseline;
        gap: 8px;
        padding: 4px 0;
        border-bottom: 1px solid var(--divider-color, #eee);
      }
      .pname {
        flex: none;
        max-width: 10em;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .send-row + .send-row {
        margin-top: 8px;
      }
    `,
  ];

  private get selected(): PortInfo | undefined {
    return this.ports.find((p) => p.id === this.portId) ?? this.ports[0];
  }

  private control(action: "pause" | "resume" | "clear"): void {
    this.dispatchEvent(new CustomEvent("live-control", { detail: action, bubbles: true, composed: true }));
  }

  private async send(): Promise<void> {
    const port = this.selected;
    if (!port || !this.payload.trim() || this.busy) return;
    const t = this.t;
    this.busy = true;
    this.result = null;
    try {
      let payload: SendPayload;
      if (this.mode === "text") {
        payload = { text: this.payload };
      } else {
        let hex = this.payload;
        if (this.algorithm) {
          hex = (await this.api.checksum(hex, this.algorithm, this.start)).frame ?? hex;
        }
        payload = { hex };
      }
      const res = await this.api.send(port.id, { ...payload, wait_ms: this.waitMs });
      let text = t("sent_x", { x: res.sent });
      if (res.reply) text += `   ${t("reply_x", { x: res.reply })}`;
      else if (res.timeout) text += `   ${t("timeout")}`;
      this.result = { ok: !res.timeout, text };
    } catch (err) {
      this.result = { ok: false, text: t("error", { msg: errorText(err) }) };
    } finally {
      this.busy = false;
    }
  }

  private renderPort(p: PortInfo) {
    const t = this.t;
    const kind = p.kind === "external" ? t("kind_external") : t("kind_serial");
    return html`<div class="port">
      <div class="row">
        <span class="dot ${p.available ? "on" : ""}" title=${p.available ? t("online") : t("offline")}></span>
        <b class="grow">${p.name}</b>
        <span class="chip ${p.kind === "external" ? "info" : ""}">${kind}</span>
      </div>
      <div class="muted ${p.kind === "external" ? "" : "mono"}" title=${p.kind === "external" ? `${p.tx_entity} / ${p.rx_entity}` : p.model}>
        ${p.kind === "external" ? p.model : p.port}
      </div>
      <div class="muted">${p.settings || "—"}</div>
      <div class="row muted">
        <span>${t("frames_in", { n: p.rx_frames ?? 0 })}</span>
        <span>${t("frames_out", { n: p.tx_frames ?? 0 })}</span>
        ${p.errors ? html`<span class="chip bad">${t("errors", { n: p.errors })}</span>` : nothing}
      </div>
    </div>`;
  }

  private renderSend() {
    const t = this.t;
    const port = this.selected;
    const placeholder = this.mode === "hex" ? t("ph_hex") : t("ph_text");
    return html`<div class="card">
      <h2>${t("send_title")}</h2>
      <div class="row send-row">
        <select @change=${(e: Event) => (this.portId = value(e))} aria-label=${t("port")}>
          ${this.ports.map((p) => html`<option value=${p.id} ?selected=${p.id === port?.id}>${p.name}</option>`)}
        </select>
        <select @change=${(e: Event) => (this.mode = value(e) as "hex" | "text")}>
          <option value="hex" ?selected=${this.mode === "hex"}>${t("mode_hex")}</option>
          <option value="text" ?selected=${this.mode === "text"}>${t("mode_text")}</option>
        </select>
        <input
          class="grow mono"
          .value=${this.payload}
          placeholder=${placeholder}
          @input=${(e: Event) => (this.payload = value(e))}
          @keydown=${(e: KeyboardEvent) => e.key === "Enter" && this.send()}
        />
      </div>
      <div class="row send-row">
        ${this.mode === "hex"
          ? html`<span class="muted">${t("append_checksum")}</span>
              <select @change=${(e: Event) => (this.algorithm = value(e))}>
                <option value="">${t("none")}</option>
                ${CHECKSUMS.map((c) => html`<option value=${c} ?selected=${c === this.algorithm}>${checksumLabel(c, t)}</option>`)}
              </select>
              ${this.algorithm
                ? html`<span class="muted">${t("start_at")}</span>
                    <input type="number" min="1" max="17" style="width:4em" .value=${String(this.start + 1)}
                      @input=${(e: Event) => (this.start = Math.max(0, (Number(value(e)) || 1) - 1))} />`
                : nothing}`
          : nothing}
        <span class="muted">${t("wait_ms")}</span>
        <input type="number" min="0" max="60000" step="100" style="width:6em" .value=${String(this.waitMs)}
          @input=${(e: Event) => (this.waitMs = Math.max(0, Number(value(e)) || 0))} />
        <span class="grow"></span>
        <button class="primary" ?disabled=${this.busy || !port} @click=${() => this.send()}>${t("send")}</button>
      </div>
      ${this.result ? html`<div class="result mono ${this.result.ok ? "" : "bad"}">${this.result.text}</div>` : nothing}
    </div>`;
  }

  private renderLive() {
    const t = this.t;
    const frames = this.liveFilter ? this.live.filter((f) => f.port === this.liveFilter) : this.live;
    return html`<div class="card">
      <div class="row">
        <h2 class="grow">${t("live_title")}</h2>
        <select @change=${(e: Event) => (this.liveFilter = value(e))}>
          <option value="">${t("all_ports")}</option>
          ${this.ports.map((p) => html`<option value=${p.id}>${p.name}</option>`)}
        </select>
        <button @click=${() => this.control(this.paused ? "resume" : "pause")}>${this.paused ? t("resume") : t("pause")}</button>
        <button @click=${() => this.control("clear")}>${t("clear")}</button>
      </div>
      ${this.dropped ? html`<div class="chip warn">${t("dropped", { n: this.dropped })}</div>` : nothing}
      ${frames.length === 0
        ? html`<div class="empty">${t("live_empty")}</div>`
        : html`<div class="live">
            ${frames.map(
              (f) => html`<div class="lrow">
                <span class="muted mono">${clock(f.t)}</span>
                <span class=${f.dir}>${f.dir === "rx" ? "⬇" : "⬆"}</span>
                <span class="pname">${this.portName(f.port)}</span>
                <span class="mono grow">${f.hex}${f.text ? html` <span class="muted">"${f.text}"</span>` : nothing}</span>
                ${f.dir === "tx" ? html`<span class="chip info">${originLabel(f.origin, t, this.deviceName)}</span>` : nothing}
                ${f.echo ? html`<span class="chip">${t("echo")}</span>` : nothing}
              </div>`,
            )}
          </div>`}
    </div>`;
  }

  render() {
    const t = this.t;
    return html`
      <div class="card">
        ${this.ports.length
          ? html`<div class="ports">${this.ports.map((p) => this.renderPort(p))}</div>`
          : html`<div class="empty">${t("no_ports")}</div>`}
      </div>
      ${this.ports.length ? this.renderSend() : nothing} ${this.renderLive()}
    `;
  }
}

define("woow-serial-overview", WoowBusOverview);
