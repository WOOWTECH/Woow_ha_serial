// Monitor tab (HAIR's Sniffer): every frame the ports heard, grouped by sender, with counts.

import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";

import { Api, Group, PortInfo, Row, copyText, define, errorText } from "../api";
import { Translate, ago, checksumLabel } from "../i18n";
import { shared } from "../styles";

const value = (e: Event) => (e.target as HTMLInputElement).value;
const WIDE = new Set(["crc16_modbus", "crc16_ccitt", "crc16_xmodem", "sum16"]);

export class WoowBusMonitor extends LitElement {
  @property({ attribute: false }) ports: PortInfo[] = [];
  @property({ attribute: false }) groups: Group[] = [];
  @property({ attribute: false }) rows: Row[] = [];
  @property({ attribute: false }) groupPrefix: Record<string, number> = {};
  @property({ attribute: false }) now = 0;
  @property({ attribute: false }) t!: Translate;
  @property({ attribute: false }) api!: Api;
  @property({ attribute: false }) portName!: (id: string) => string;

  @state() private portFilter = "";
  @state() private showHidden = false;
  @state() private open = new Set<string>();
  @state() private status = "";

  static styles = [
    shared,
    css`
      .toolbar {
        position: sticky;
        top: 0;
        z-index: 1;
      }
      .group {
        border-top: 1px solid var(--divider-color, #eee);
      }
      .group:first-child {
        border-top: none;
      }
      .group.is-hidden {
        opacity: 0.6;
      }
      .ghead {
        display: flex;
        gap: 8px;
        align-items: flex-start;
        padding: 10px 0;
        cursor: pointer;
      }
      .caret {
        width: 1em;
        color: var(--secondary-text-color);
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 2px;
      }
      .rows {
        margin: 0 0 10px 1.5em;
      }
      .rrow {
        display: flex;
        gap: 8px;
        align-items: flex-start;
        padding: 6px 0;
        border-top: 1px dashed var(--divider-color, #eee);
      }
      .pre {
        font-weight: 600;
      }
      .ck {
        color: var(--success-color, #43a047);
        font-weight: 600;
      }
    `,
  ];

  private toggle(id: string): void {
    const open = new Set(this.open);
    if (open.has(id)) open.delete(id);
    else open.add(id);
    this.open = open;
  }

  private flash(text: string): void {
    this.status = text;
    window.setTimeout(() => {
      if (this.status === text) this.status = "";
    }, 3000);
  }

  private async run(action: () => Promise<unknown>): Promise<void> {
    try {
      await action();
    } catch (err) {
      this.flash(this.t("error", { msg: errorText(err) }));
    }
  }

  private renameGroup(g: Group): void {
    const name = window.prompt(this.t("alias_prompt"), g.alias);
    if (name !== null) void this.run(() => this.api.updateGroup(g.id, { alias: name.trim() }));
  }

  private renameRow(r: Row): void {
    const name = window.prompt(this.t("alias_prompt"), r.alias);
    if (name !== null) void this.run(() => this.api.updateRow(r.id, name.trim()));
  }

  private deleteGroup(g: Group): void {
    if (window.confirm(this.t("delete_group_confirm"))) void this.run(() => this.api.deleteGroup(g.id));
  }

  private resend(r: Row): void {
    void this.run(async () => {
      const res = await this.api.send(r.port_id, { hex: r.hex });
      this.flash(this.t("sent_x", { x: res.sent }));
    });
  }

  private applyPrefix(portId: string, length: number): void {
    if (!window.confirm(this.t("prefix_confirm"))) {
      this.requestUpdate();
      return;
    }
    void this.run(async () => {
      await this.api.setPrefix(portId, length);
      this.dispatchEvent(new CustomEvent("prefix-changed", { detail: { portId, length }, bubbles: true, composed: true }));
    });
  }

  private clearPort(portId: string): void {
    if (window.confirm(this.t("clear_port_confirm", { port: this.portName(portId) }))) {
      void this.run(() => this.api.clearCatalog(portId));
    }
  }

  /** Header / address bytes in bold, the checksum the group agrees on in green. */
  private bytes(r: Row, g: Group) {
    const parts = r.hex.split(" ");
    const head = g.key === "text" || g.key === "*" ? 0 : g.key.split(" ").length;
    const width = g.checksum && r.checks.includes(g.checksum) ? (WIDE.has(g.checksum.split("@")[0]) ? 2 : 1) : 0;
    const tail = width && parts.length > head + width ? width : 0;
    return html`<span class="pre">${parts.slice(0, head).join(" ")}</span> ${parts
        .slice(head, parts.length - tail)
        .join(" ")}
      <span class="ck">${parts.slice(parts.length - tail).join(" ")}</span>`;
  }

  private renderGroup(g: Group, rows: Row[]) {
    const t = this.t;
    const open = this.open.has(g.id);
    const key = g.key === "text" ? t("text_group") : g.key === "*" ? t("all_bytes") : g.key;
    return html`<div class="group ${g.hidden ? "is-hidden" : ""}">
      <div class="ghead" @click=${() => this.toggle(g.id)}>
        <span class="caret">${open ? "▾" : "▸"}</span>
        <div class="grow">
          <div class="row">
            <b class=${g.alias ? "" : "mono"}>${g.alias || key}</b>
            ${g.alias ? html`<span class="muted mono">${key}</span>` : nothing}
            ${g.checksum ? html`<span class="chip ok">${t("checksum_is", { name: checksumLabel(g.checksum, t) })}</span>` : nothing}
            ${g.hidden ? html`<span class="chip">${t("hidden")}</span>` : nothing}
          </div>
          <div class="muted">
            ${this.portName(g.port_id)} · ${t("frames_count", { n: g.count })} · ${t("variants", { n: g.rows })} ·
            ${ago(g.last_seen, t)}${g.rate ? ` · ${t("per_second", { n: g.rate })}` : ""}
          </div>
        </div>
        <div class="actions" @click=${(e: Event) => e.stopPropagation()}>
          <button class="link" @click=${() => this.renameGroup(g)}>${t("rename")}</button>
          <button class="link" @click=${() => this.run(() => this.api.updateGroup(g.id, { hidden: !g.hidden }))}>
            ${g.hidden ? t("unhide") : t("hide")}
          </button>
          <button class="link danger" @click=${() => this.deleteGroup(g)}>${t("delete")}</button>
        </div>
      </div>
      ${open
        ? html`<div class="rows">
            ${rows.map(
              (r) => html`<div class="rrow">
                <div class="grow">
                  <div class="mono">${this.bytes(r, g)}</div>
                  ${r.text ? html`<div class="muted mono">"${r.text}"</div>` : nothing}
                  <div class="muted">
                    ${r.alias ? html`<b>${r.alias}</b> · ` : nothing}${t("times", { n: r.count })} · ${ago(r.last_seen, t)}
                  </div>
                </div>
                <div class="actions">
                  <button class="link" @click=${() =>
                    this.dispatchEvent(new CustomEvent("add-to-device", { detail: r, bubbles: true, composed: true }))}>
                    ${t("add_to_device")}
                  </button>
                  <button class="link" @click=${() =>
                    this.dispatchEvent(new CustomEvent("make-button", { detail: r, bubbles: true, composed: true }))}>
                    ${t("make_button")}
                  </button>
                  <button class="link" @click=${() => this.resend(r)}>${t("send_again")}</button>
                  <button class="link" @click=${() => this.renameRow(r)}>${t("rename")}</button>
                  <button class="link" @click=${() => { copyText(r.hex); this.flash(t("copied")); }}>${t("copy")}</button>
                  <button class="link danger" @click=${() => this.run(() => this.api.deleteRow(r.id))}>${t("delete")}</button>
                </div>
              </div>`,
            )}
          </div>`
        : nothing}
    </div>`;
  }

  render() {
    const t = this.t;
    const byGroup = new Map<string, Row[]>();
    for (const r of this.rows) {
      const list = byGroup.get(r.group_id);
      if (list) list.push(r);
      else byGroup.set(r.group_id, [r]);
    }
    for (const list of byGroup.values()) list.sort((a, b) => b.last_seen - a.last_seen);
    const groups = this.groups
      .filter((g) => (!this.portFilter || g.port_id === this.portFilter) && (this.showHidden || !g.hidden))
      .sort((a, b) => a.order - b.order || b.last_seen - a.last_seen);
    const port = this.ports.find((p) => p.id === this.portFilter);
    return html`
      <div class="card toolbar row">
        <select @change=${(e: Event) => (this.portFilter = value(e))}>
          <option value="">${t("all_ports")}</option>
          ${this.ports.map((p) => html`<option value=${p.id} ?selected=${p.id === this.portFilter}>${p.name}</option>`)}
        </select>
        <label class="row muted">
          <input type="checkbox" .checked=${this.showHidden} @change=${(e: Event) => (this.showHidden = (e.target as HTMLInputElement).checked)} />
          ${t("show_hidden")}
        </label>
        <span class="grow muted">${this.status}</span>
        ${port
          ? html`<span class="muted">${t("group_by")}</span>
              <input type="number" min="0" max="8" style="width:4em" .value=${String(this.groupPrefix[port.id] ?? 2)}
                @change=${(e: Event) => this.applyPrefix(port.id, Math.min(8, Math.max(0, Number(value(e)) || 0)))} />
              <span class="muted">${t("bytes")}</span>`
          : nothing}
        ${port ? html`<button @click=${() => this.clearPort(port.id)}>${t("clear")}</button>` : nothing}
      </div>
      <div class="card">
        ${groups.length ? groups.map((g) => this.renderGroup(g, byGroup.get(g.id) ?? [])) : html`<div class="empty">${t("monitor_empty")}</div>`}
      </div>
    `;
  }
}

define("woow-serial-monitor", WoowBusMonitor);
