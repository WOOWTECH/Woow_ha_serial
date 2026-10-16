// Send log tab (HAIR's Mirror): what Home Assistant sent, who sent it, and what came back.

import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";

import { Api, PortInfo, Sent, define, errorText } from "../api";
import { Translate, ago, originLabel } from "../i18n";
import { shared } from "../styles";

export class WoowBusSendLog extends LitElement {
  @property({ attribute: false }) sent: Sent[] = [];
  @property({ attribute: false }) ports: PortInfo[] = [];
  @property({ attribute: false }) now = 0;
  @property({ attribute: false }) t!: Translate;
  @property({ attribute: false }) api!: Api;
  @property({ attribute: false }) portName!: (id: string) => string;
  @property({ attribute: false }) deviceName: (id: string) => string | undefined = () => undefined;

  @state() private status = "";

  static styles = [
    shared,
    css`
      .srow {
        display: flex;
        gap: 8px;
        align-items: flex-start;
        padding: 10px 0;
        border-top: 1px solid var(--divider-color, #eee);
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
      }
    `,
  ];

  private async run(action: () => Promise<unknown>): Promise<void> {
    try {
      await action();
    } catch (err) {
      this.status = this.t("error", { msg: errorText(err) });
    }
  }

  private resend(r: Sent): void {
    void this.run(async () => {
      const res = await this.api.send(r.port_id, { hex: r.hex });
      this.status = this.t("sent_x", { x: res.sent });
    });
  }

  private clearAll(): void {
    if (window.confirm(this.t("clear_all_confirm"))) void this.run(() => this.api.deleteSent());
  }

  render() {
    const t = this.t;
    const rows = [...this.sent].sort((a, b) => b.last_sent - a.last_sent);
    return html`<div class="card">
      <div class="row">
        <h2 class="grow">${t("tab_sendlog")}</h2>
        <span class="muted">${this.status}</span>
        ${rows.length ? html`<button @click=${() => this.clearAll()}>${t("clear_all")}</button>` : nothing}
      </div>
      ${rows.length === 0
        ? html`<div class="empty">${t("sendlog_empty")}</div>`
        : rows.map((r) => {
            const heard = Object.keys(r.heard_by);
            return html`<div class="srow">
              <div class="grow">
                <div class="row">
                  <span class="mono">${r.hex}</span>
                  ${r.text ? html`<span class="muted mono">"${r.text}"</span>` : nothing}
                </div>
                <div class="row muted">
                  <span>${this.portName(r.port_id)}</span>
                  <span>${t("times", { n: r.count })}</span>
                  <span>${ago(r.last_sent, t)}</span>
                  <span class="chip info">${originLabel(r.origin, t, this.deviceName)}</span>
                  ${r.replies
                    ? html`<span class="chip ok mono">${t("reply_ms", { x: r.reply ?? "", ms: r.reply_ms ?? 0 })}</span>`
                    : html`<span class="chip">${t("no_reply")}</span>`}
                  ${heard.length
                    ? html`<span class="chip ok">${t("heard_by", { ports: heard.map((id) => this.portName(id)).join("、") })}</span>`
                    : nothing}
                </div>
              </div>
              <div class="actions">
                <button class="link" @click=${() => this.resend(r)}>${t("send_again")}</button>
                <button class="link danger" @click=${() => this.run(() => this.api.deleteSent(r.id))}>${t("delete")}</button>
              </div>
            </div>`;
          })}
    </div>`;
  }
}

define("woow-serial-sendlog", WoowBusSendLog);
