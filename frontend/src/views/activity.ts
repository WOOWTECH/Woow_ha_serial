// Activity tab: who changed or sent what (agents through services, people in the panel, entity actions).

import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";

import { Activity, define } from "../api";
import { Translate, ago, clock, explain, isKey } from "../i18n";
import { shared } from "../styles";

const value = (e: Event) => (e.target as HTMLSelectElement).value;

export class WoowSerialActivity extends LitElement {
  @property({ attribute: false }) entries: Activity[] = [];
  @property({ attribute: false }) now = 0;
  @property({ attribute: false }) t!: Translate;
  @property({ attribute: false }) deviceName: (id: string) => string | undefined = () => undefined;
  @property({ attribute: false }) portName!: (id: string) => string;

  @state() private channel = "";

  static styles = [
    shared,
    css`
      .entry {
        display: grid;
        grid-template-columns: 7.5em 1fr;
        gap: 4px 12px;
        padding: 10px 0;
        border-top: 1px solid var(--divider-color, #eee);
      }
      .when {
        color: var(--secondary-text-color);
        font-size: 0.85em;
      }
      .note {
        font-style: italic;
        color: var(--secondary-text-color);
      }
      .fail {
        color: var(--error-color, #db4437);
      }
    `,
  ];

  private channelLabel(channel: string): string {
    const key = `channel_${channel}`;
    return isKey(key) ? this.t(key) : channel;
  }

  /** The entry's message in the panel's language (types, actions and fields too); else the English summary. */
  private message(e: Activity): string {
    const key = `log_${e.msg}`;
    if (!e.msg || !isKey(key)) return e.summary;
    const t = this.t;
    const label = (prefix: string, value: unknown) => {
      const k = `${prefix}_${value}`;
      return isKey(k) ? t(k) : String(value ?? "");
    };
    const args: Record<string, string | number> = { ...(e.args ?? {}) };
    if ("type" in args) args.type = label("type", args.type);
    if ("action" in args) args.action = label("act", args.action);
    if ("field" in args) args.field = label("field", args.field);
    const error = e.detail?.error as { code: string } | undefined;
    if (e.msg === "device_save_failed" && error?.code) args.error = explain(error, t);
    return t(key, args);
  }

  render() {
    const t = this.t;
    const rows = this.entries.filter((e) => !this.channel || e.channel === this.channel).sort((a, b) => b.t - a.t);
    return html`<div class="card">
      <div class="row">
        <h2 class="grow">${t("tab_activity")}</h2>
        <select @change=${(e: Event) => (this.channel = value(e))}>
          <option value="">${t("all_channels")}</option>
          ${["service", "panel", "entity"].map((c) => html`<option value=${c}>${this.channelLabel(c)}</option>`)}
        </select>
      </div>
      <div class="muted">${t("activity_hint")}</div>
      ${rows.length === 0
        ? html`<div class="empty">${t("activity_empty")}</div>`
        : rows.map(
            (e) => html`<div class="entry">
              <div class="when" title=${new Date(e.t * 1000).toLocaleString()}>${ago(e.t, t)}<br />${clock(e.t).slice(0, 8)}</div>
              <div>
                <div class="row">
                  <span class="chip ${e.channel === "service" ? "info" : ""}">${this.channelLabel(e.channel)}</span>
                  ${e.user ? html`<span class="chip">${e.user}</span>` : nothing}
                  ${e.device_id && this.deviceName(e.device_id) ? html`<span class="chip ok">${this.deviceName(e.device_id)}</span>` : nothing}
                  ${e.port_id ? html`<span class="muted">${this.portName(e.port_id)}</span>` : nothing}
                </div>
                <div class=${e.ok ? "" : "fail"} title=${e.summary}>${e.ok ? "" : "✗ "}${this.message(e)}</div>
                ${e.note ? html`<div class="note">${t("quoted", { x: e.note })}</div>` : nothing}
              </div>
            </div>`,
          )}
    </div>`;
  }
}

define("woow-serial-activity", WoowSerialActivity);
