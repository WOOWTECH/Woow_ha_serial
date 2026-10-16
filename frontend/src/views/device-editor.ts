// Device editor: commands (templates with live preview and test), entity action mapping, options,
// value ranges, state feedback rules and sensors (tried against the monitor), polling.

import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";

import {
  Api,
  Button,
  CodedError,
  Command,
  Device,
  DeviceState,
  DeviceType,
  Format,
  PortInfo,
  Rule,
  SensorDef,
  define,
  errorText,
  newId,
} from "../api";
import { frameAsPattern, stateSummary } from "../device-util";
import { Translate, explain, isKey } from "../i18n";
import { shared } from "../styles";

const val = (e: Event) => (e.target as HTMLInputElement).value;
const num = (e: Event, fallback = 0) => {
  const n = Number(val(e));
  return Number.isFinite(n) ? n : fallback;
};

type Preview = { sent?: string; fields?: string[]; error?: CodedError };
type Note = { ok: boolean; text: string };

export class WoowBusDeviceEditor extends LitElement {
  @property({ attribute: false }) device!: Device;
  @property({ attribute: false }) devices: Device[] = [];
  @property({ attribute: false }) types: Record<string, DeviceType> = {};
  @property({ attribute: false }) valueActions: Record<string, string> = {};
  @property({ attribute: false }) ports: PortInfo[] = [];
  @property({ attribute: false }) state?: DeviceState;
  @property({ attribute: false }) t!: Translate;
  @property({ attribute: false }) api!: Api;
  @property({ attribute: false }) portName!: (id: string) => string;

  @state() private draft!: Device;
  @state() private params: [string, string][] = [];
  @state() private dirty = false;
  @state() private status: Note | null = null;
  @state() private busy = false;
  @state() private previews: Record<string, Preview> = {};
  @state() private tried: Record<string, Note> = {};
  @state() private listening: string | null = null;
  private loadedId: string | undefined;
  private timers = new Map<string, number>();

  static styles = [
    shared,
    css`
      .form {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 10px 12px;
      }
      label {
        display: grid;
        gap: 4px;
        font-size: 0.85em;
        color: var(--secondary-text-color);
      }
      label > input,
      label > select {
        font-size: 1.1em;
      }
      .hint {
        margin: -6px 0 10px;
        color: var(--secondary-text-color);
        font-size: 0.85em;
        white-space: pre-wrap;
      }
      .item {
        border-top: 1px solid var(--divider-color, #eee);
        padding: 10px 0;
        display: grid;
        gap: 6px;
      }
      .item .row > input,
      .item .row > select {
        min-width: 0;
      }
      .wide {
        flex: 1 1 260px;
      }
      .small {
        width: 6.5em;
      }
      .tiny {
        width: 4.5em;
      }
      .note {
        font-size: 0.85em;
      }
      .note.ok {
        color: var(--success-color, #43a047);
      }
      .note.bad {
        color: var(--error-color, #db4437);
      }
      .footer {
        position: sticky;
        bottom: 0;
        z-index: 2;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
        padding: 12px 16px;
        margin: 0 -16px -16px;
        background: var(--card-background-color, #fff);
        border-top: 1px solid var(--divider-color, #e0e0e0);
      }
      .actions-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
        gap: 8px 12px;
      }
    `,
  ];

  protected willUpdate(changed: Map<string, unknown>): void {
    if (changed.has("device") && (!this.draft || this.device.id !== this.loadedId || !this.dirty)) {
      this.load(this.device);
    }
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    for (const timer of this.timers.values()) window.clearTimeout(timer);
  }

  private load(device: Device): void {
    const draft = structuredClone(device);
    delete draft.entities;
    this.draft = draft;
    this.params = Object.entries(draft.params);
    this.loadedId = device.id;
    this.dirty = false;
    for (const command of draft.commands) this.schedulePreview(command, 0);
  }

  private get spec(): DeviceType {
    return this.types[this.draft.type] ?? { platform: null, actions: [], fields: [] };
  }

  private paramObject(): Record<string, string> {
    return Object.fromEntries(this.params.filter(([k]) => k.trim()).map(([k, v]) => [k.trim(), v.trim()]));
  }

  private change(mutate: (d: Device) => void): void {
    const next = structuredClone(this.draft);
    mutate(next);
    this.draft = next;
    this.dirty = true;
  }

  private label(prefix: string, key: string): string {
    const full = `${prefix}${key}`;
    return isKey(full) ? this.t(full) : key;
  }

  // ---- previews and tries ---------------------------------------------------------------
  private schedulePreview(command: Command, delay = 300): void {
    window.clearTimeout(this.timers.get(command.id));
    this.timers.set(
      command.id,
      window.setTimeout(async () => {
        let result: Preview;
        try {
          result = await this.api.preview(command.payload, command.format, this.paramObject(), 0);
        } catch (err) {
          result = { error: { code: "malformed", detail: errorText(err) } };
        }
        this.previews = { ...this.previews, [command.id]: result };
      }, delay),
    );
  }

  private previewAll(): void {
    for (const command of this.draft.commands) this.schedulePreview(command);
  }

  private async tryPattern(id: string, pattern: string, format: Format): Promise<void> {
    const t = this.t;
    try {
      const res = await this.api.testPattern(pattern, format, this.draft.port_id, this.paramObject());
      let note: Note;
      if (res.error) {
        note = { ok: false, text: explain(res.error, t) };
      } else if (!res.matches?.length) {
        note = { ok: false, text: t("no_matches") };
      } else {
        const sample = res.matches
          .slice(0, 3)
          .map((m) => `${m.frame}  ${JSON.stringify(m.captures)}`)
          .join("\n");
        note = { ok: true, text: `${t("matches", { n: res.matches.length })}\n${sample}` };
      }
      this.tried = { ...this.tried, [id]: note };
    } catch (err) {
      this.tried = { ...this.tried, [id]: { ok: false, text: t("error", { msg: errorText(err) }) } };
    }
  }

  private async listenFor(button: Button): Promise<void> {
    const t = this.t;
    this.listening = button.id;
    this.tried = { ...this.tried, [button.id]: { ok: true, text: t("listening") } };
    try {
      const heard = await this.api.listen(this.draft.port_id, 15);
      if (!heard) {
        this.tried = { ...this.tried, [button.id]: { ok: false, text: t("listen_timeout") } };
        return;
      }
      const learned = frameAsPattern(heard.hex, heard.text);
      this.change((x) => {
        const target = x.buttons.find((b) => b.id === button.id);
        if (target) {
          target.pattern = learned.pattern;
          target.format = learned.format;
        }
      });
      this.tried = { ...this.tried, [button.id]: { ok: true, text: t("heard", { x: heard.hex }) } };
    } catch (err) {
      this.tried = { ...this.tried, [button.id]: { ok: false, text: t("error", { msg: errorText(err) }) } };
    } finally {
      this.listening = null;
    }
  }

  private bindLabel(target: Device | undefined, action: string): string {
    const t = this.t;
    if (action === "toggle") return t("act_toggle");
    if (action.startsWith("option:")) return t("option_x", { x: action.slice(7) });
    if (action.startsWith("command:")) {
      const id = action.slice(8);
      return t("command_x", { x: target?.commands.find((c) => c.id === id)?.name ?? id });
    }
    return this.label("act_", action);
  }

  private async test(command: Command): Promise<void> {
    const t = this.t;
    if (!this.draft.id || this.dirty) {
      this.status = { ok: false, text: t("save_first") };
      return;
    }
    let value: number | undefined;
    if (this.previews[command.id]?.fields?.includes("value")) {
      const answer = window.prompt(t("value_prompt"), "0");
      if (answer === null) return;
      value = Number(answer);
    }
    try {
      const res = await this.api.runCommand(this.draft.id, command.id, value);
      this.status = {
        ok: true,
        text: t("sent_x", { x: res.sent }) + (res.reply ? `   ${t("reply_x", { x: res.reply })}` : ""),
      };
    } catch (err) {
      this.status = { ok: false, text: t("error", { msg: errorText(err) }) };
    }
  }

  // ---- save / delete / leave ------------------------------------------------------------
  private async save(): Promise<void> {
    const t = this.t;
    const payload: Device = { ...structuredClone(this.draft), params: this.paramObject() };
    this.busy = true;
    try {
      const res = await this.api.saveDevice(payload);
      if (res.error) {
        this.status = { ok: false, text: explain(res.error, t) };
        return;
      }
      if (res.device) this.load(res.device);
      this.status = { ok: true, text: t("saved") };
    } catch (err) {
      this.status = { ok: false, text: t("error", { msg: errorText(err) }) };
    } finally {
      this.busy = false;
    }
  }

  private async removeDevice(): Promise<void> {
    if (!window.confirm(this.t("confirm_delete_device", { name: this.draft.name }))) return;
    try {
      await this.api.deleteDevice(this.draft.id);
      this.dispatchEvent(new CustomEvent("close", { bubbles: true, composed: true }));
    } catch (err) {
      this.status = { ok: false, text: this.t("error", { msg: errorText(err) }) };
    }
  }

  private leave(): void {
    if (this.dirty && !window.confirm(`${this.t("unsaved")} — ${this.t("back")}?`)) return;
    this.dispatchEvent(new CustomEvent("close", { bubbles: true, composed: true }));
  }

  // ---- sections -------------------------------------------------------------------------
  private formatSelect(current: Format, onChange: (f: Format) => void) {
    const formats: Format[] = ["hex", "text"];
    return html`<select class="small" @change=${(e: Event) => onChange(val(e) as Format)}>
      ${formats.map((f) => html`<option value=${f} ?selected=${f === current}>${this.label("format_", f)}</option>`)}
    </select>`;
  }

  private commandSelect(current: string, onChange: (id: string) => void, emptyLabel?: string) {
    return html`<select @change=${(e: Event) => onChange(val(e))}>
      <option value="" ?selected=${!current}>${emptyLabel ?? this.t("not_used")}</option>
      ${this.draft.commands.map((c) => html`<option value=${c.id} ?selected=${c.id === current}>${c.name || "?"}</option>`)}
    </select>`;
  }

  private renderBasic() {
    const t = this.t;
    const d = this.draft;
    return html`<div class="card">
      <h2>${t("sec_basic")}</h2>
      <div class="form">
        <label>${t("name")}<input .value=${d.name} @input=${(e: Event) => this.change((x) => (x.name = val(e)))} /></label>
        <label
          >${t("type")}
          <select
            @change=${(e: Event) =>
              this.change((x) => {
                x.type = val(e);
                const spec = this.types[x.type];
                x.actions = Object.fromEntries(Object.entries(x.actions).filter(([a]) => spec?.actions.includes(a)));
                if (!spec?.options) x.options = [];
                x.rules = x.rules.filter((r) => spec?.fields.includes(r.field));
              })}
          >
            ${Object.keys(this.types).map((k) => html`<option value=${k} ?selected=${k === d.type}>${this.label("type_", k)}</option>`)}
          </select>
        </label>
        <label
          >${t("port")}
          <select @change=${(e: Event) => this.change((x) => (x.port_id = val(e)))}>
            ${this.ports.map((p) => html`<option value=${p.id} ?selected=${p.id === d.port_id}>${p.name}</option>`)}
          </select>
        </label>
        <label>${t("manufacturer")}<input .value=${d.manufacturer} @input=${(e: Event) => this.change((x) => (x.manufacturer = val(e)))} /></label>
        <label>${t("model")}<input .value=${d.model} @input=${(e: Event) => this.change((x) => (x.model = val(e)))} /></label>
      </div>
      ${this.state && d.id
        ? html`<div class="row" style="margin-top:10px">
            ${stateSummary(d, this.state, t).map((s) => html`<span class="chip info">${s}</span>`)}
          </div>`
        : nothing}
    </div>`;
  }

  private renderParams() {
    const t = this.t;
    const set = (index: number, part: 0 | 1, text: string) => {
      const next = this.params.map((p) => [...p] as [string, string]);
      next[index][part] = text;
      this.params = next;
      this.dirty = true;
      this.previewAll();
    };
    return html`<div class="card">
      <h2>${t("sec_params")}</h2>
      <div class="hint">${t("params_hint")}</div>
      ${this.params.map(
        ([name, value], i) => html`<div class="row" style="margin-bottom:6px">
          <input class="small mono" placeholder=${t("param_name")} .value=${name} @input=${(e: Event) => set(i, 0, val(e))} />
          <input class="grow mono" placeholder=${t("param_value")} .value=${value} @input=${(e: Event) => set(i, 1, val(e))} />
          <button class="link danger" @click=${() => {
            this.params = this.params.filter((_, j) => j !== i);
            this.dirty = true;
            this.previewAll();
          }}>${t("remove")}</button>
        </div>`,
      )}
      <button @click=${() => {
        this.params = [...this.params, [this.params.length ? "" : "addr", ""]];
        this.dirty = true;
      }}>${t("add_param")}</button>
    </div>`;
  }

  private renderCommands() {
    const t = this.t;
    const edit = (index: number, mutate: (c: Command) => void) => {
      this.change((x) => mutate(x.commands[index]));
      this.schedulePreview(this.draft.commands[index]);
    };
    return html`<div class="card">
      <h2>${t("sec_commands")}</h2>
      <div class="hint mono">${t("commands_hint")}</div>
      ${this.draft.commands.map((c, i) => {
        const preview = this.previews[c.id];
        return html`<div class="item">
          <div class="row">
            <input class="small" placeholder=${t("command_name")} .value=${c.name} @input=${(e: Event) => edit(i, (x) => (x.name = val(e)))} />
            ${this.formatSelect(c.format, (f) => edit(i, (x) => (x.format = f)))}
            <input class="wide mono" .value=${c.payload} @input=${(e: Event) => edit(i, (x) => (x.payload = val(e)))} />
          </div>
          <div class="row muted">
            <span>${t("repeat")}</span>
            <input class="tiny" type="number" min="1" max="20" .value=${String(c.repeat)}
              @input=${(e: Event) => edit(i, (x) => (x.repeat = Math.min(20, Math.max(1, num(e, 1)))))} />
            <span>${t("wait_reply")}</span>
            <input class="small" type="number" min="0" max="60000" step="100" .value=${String(c.wait_ms)}
              @input=${(e: Event) => edit(i, (x) => (x.wait_ms = Math.max(0, num(e))))} />
            <span class="grow"></span>
            <button class="link" @click=${() => this.test(c)}>${t("test")}</button>
            <button class="link danger" @click=${() =>
              this.change((x) => {
                x.commands.splice(i, 1);
                x.actions = Object.fromEntries(Object.entries(x.actions).filter(([, id]) => id !== c.id));
                x.options = x.options.filter((o) => o.command !== c.id);
                if (x.poll_command === c.id) x.poll_command = "";
              })}>${t("remove")}</button>
          </div>
          ${preview?.error
            ? html`<div class="note bad">${explain(preview.error, t)}</div>`
            : preview?.sent
              ? html`<div class="note ok mono">${t("will_send", { x: preview.sent })}${preview.fields?.includes("value") ? "  (value = 0)" : ""}</div>`
              : nothing}
        </div>`;
      })}
      <button @click=${() => {
        const command: Command = {
          id: newId(), name: "", payload: "", format: "hex", repeat: 1, gap_ms: 100, wait_ms: 0,
        };
        this.change((x) => x.commands.push(command));
      }}>${t("add_command")}</button>
    </div>`;
  }

  private renderActions() {
    const t = this.t;
    const actions = this.spec.actions;
    if (!actions.length) return nothing;
    return html`<div class="card">
      <h2>${t("sec_actions")}</h2>
      <div class="hint">${t("actions_hint")}</div>
      <div class="actions-grid">
        ${actions.map(
          (a) => html`<label>${this.label("act_", a)}
            ${this.commandSelect(this.draft.actions[a] ?? "", (id) =>
              this.change((x) => {
                if (id) x.actions[a] = id;
                else delete x.actions[a];
              }),
            )}</label>`,
        )}
      </div>
    </div>`;
  }

  private renderButtons() {
    const t = this.t;
    if (!this.spec.buttons) return nothing;
    const targets = this.devices.filter((d) => d.id && d.id !== this.draft.id && (d.bindable?.length ?? 0) > 0);
    return html`<div class="card">
      <h2>${t("sec_buttons")}</h2>
      <div class="hint">${t("buttons_hint")}</div>
      ${this.draft.buttons.map((b, i) => {
        const note = this.tried[b.id];
        const edit = (mutate: (x: Button) => void) => this.change((x) => mutate(x.buttons[i]));
        const target = this.devices.find((d) => d.id === b.target);
        return html`<div class="item">
          <div class="row">
            <input class="small" placeholder=${t("button_name")} .value=${b.name} @input=${(e: Event) => edit((x) => (x.name = val(e)))} />
            <input class="wide mono" placeholder=${t("pattern")} .value=${b.pattern} @input=${(e: Event) => edit((x) => (x.pattern = val(e)))} />
            ${this.formatSelect(b.format, (f) => edit((x) => (x.format = f)))}
          </div>
          <div class="row muted">
            <span>${t("debounce")}</span>
            <input class="small" type="number" min="0" max="10000" step="50" .value=${String(b.debounce_ms)}
              @input=${(e: Event) => edit((x) => (x.debounce_ms = Math.min(10000, Math.max(0, Math.round(num(e, 300))))))} />
            <span>${t("binding")}</span>
            <select @change=${(e: Event) =>
              edit((x) => {
                x.target = val(e);
                x.action = "";
                x.value = null;
              })}>
              <option value="" ?selected=${!b.target}>${t("binding_none")}</option>
              ${targets.map((d) => html`<option value=${d.id} ?selected=${d.id === b.target}>${d.name}</option>`)}
            </select>
            ${b.target
              ? html`<select @change=${(e: Event) => edit((x) => (x.action = val(e)))}>
                  <option value="" ?selected=${!b.action}>${t("not_used")}</option>
                  ${(target?.bindable ?? []).map(
                    (a) => html`<option value=${a} ?selected=${a === b.action}>${this.bindLabel(target, a)}</option>`,
                  )}
                </select>`
              : nothing}
            ${b.action in this.valueActions
              ? html`<span>${t("value_pct")}</span>
                  <input class="tiny" type="number" min="0" max="100" .value=${b.value === null ? "" : String(b.value)}
                    @input=${(e: Event) => edit((x) => (x.value = val(e) === "" ? null : Math.min(100, Math.max(0, num(e)))))} />`
              : nothing}
            <span class="grow"></span>
            <button class="link" ?disabled=${this.listening !== null} @click=${() => this.listenFor(b)}>${t("listen")}</button>
            <button class="link" @click=${() => this.tryPattern(b.id, b.pattern, b.format)}>${t("try_pattern")}</button>
            <button class="link danger" @click=${() => this.change((x) => x.buttons.splice(i, 1))}>${t("remove")}</button>
          </div>
          ${note ? html`<div class="note mono ${note.ok ? "ok" : "bad"}" style="white-space:pre-wrap">${note.text}</div>` : nothing}
        </div>`;
      })}
      <button @click=${() =>
        this.change((x) =>
          x.buttons.push({ id: newId(), name: "", pattern: "", format: "hex", debounce_ms: 300, target: "", action: "", value: null }),
        )}>${t("add_button")}</button>
    </div>`;
  }

  private renderChoices() {
    const t = this.t;
    if (!this.spec.options) return nothing;
    return html`<div class="card">
      <h2>${t("sec_options")}</h2>
      <div class="hint">${t("options_hint")}</div>
      ${this.draft.options.map(
        (o, i) => html`<div class="row" style="margin-bottom:6px">
          <input class="grow" placeholder=${t("option_name")} .value=${o.name} @input=${(e: Event) => this.change((x) => (x.options[i].name = val(e)))} />
          ${this.commandSelect(o.command, (id) => this.change((x) => (x.options[i].command = id)))}
          <button class="link danger" @click=${() => this.change((x) => x.options.splice(i, 1))}>${t("remove")}</button>
        </div>`,
      )}
      <button @click=${() => this.change((x) => x.options.push({ name: "", command: "" }))}>${t("add_option")}</button>
    </div>`;
  }

  private renderRanges() {
    const t = this.t;
    const fields = this.spec.actions.filter((a) => a in this.valueActions).map((a) => this.valueActions[a]);
    if (!fields.length) return nothing;
    return html`<div class="card">
      <h2>${t("sec_ranges")}</h2>
      <div class="hint">${t("ranges_hint")}</div>
      ${fields.map((f) => {
        const range = this.draft.ranges[f] ?? [0, 100];
        const set = (index: 0 | 1, value: number) =>
          this.change((x) => {
            const next: [number, number] = [...(x.ranges[f] ?? [0, 100])] as [number, number];
            next[index] = value;
            x.ranges[f] = next;
          });
        return html`<div class="row" style="margin-bottom:6px">
          <span class="small">${this.label("field_", f)}</span>
          <span class="muted">${t("range_at0")}</span>
          <input class="small" type="number" .value=${String(range[0])} @input=${(e: Event) => set(0, num(e))} />
          <span class="muted">${t("range_at100")}</span>
          <input class="small" type="number" .value=${String(range[1])} @input=${(e: Event) => set(1, num(e, 100))} />
        </div>`;
      })}
    </div>`;
  }

  private renderRules() {
    const t = this.t;
    const fields = this.spec.fields;
    if (!fields.length) return nothing;
    return html`<div class="card">
      <h2>${t("sec_rules")}</h2>
      <div class="hint">${t("rules_hint")}</div>
      ${this.draft.rules.map((r, i) => {
        const note = this.tried[r.id];
        const edit = (mutate: (x: Rule) => void) => this.change((x) => mutate(x.rules[i]));
        return html`<div class="item">
          <div class="row">
            <input class="wide mono" placeholder=${t("pattern")} .value=${r.pattern} @input=${(e: Event) => edit((x) => (x.pattern = val(e)))} />
            ${this.formatSelect(r.format, (f) => edit((x) => (x.format = f)))}
          </div>
          <div class="row">
            <span class="muted">${t("field")}</span>
            <select @change=${(e: Event) => edit((x) => (x.field = val(e)))}>
              ${fields.map((f) => html`<option value=${f} ?selected=${f === r.field}>${this.label("field_", f)}</option>`)}
            </select>
            <span class="muted">${t("value")}</span>
            <input class="small mono" placeholder=${t("value_hint")} title=${t("value_hint")} .value=${r.value} @input=${(e: Event) => edit((x) => (x.value = val(e)))} />
            <span class="grow"></span>
            <button class="link" @click=${() => this.tryPattern(r.id, r.pattern, r.format)}>${t("try_pattern")}</button>
            <button class="link danger" @click=${() => this.change((x) => x.rules.splice(i, 1))}>${t("remove")}</button>
          </div>
          ${note ? html`<div class="note mono ${note.ok ? "ok" : "bad"}" style="white-space:pre-wrap">${note.text}</div>` : nothing}
        </div>`;
      })}
      <button @click=${() =>
        this.change((x) =>
          x.rules.push({ id: newId(), pattern: "", format: "hex", field: fields[0], value: "" }),
        )}>${t("add_rule")}</button>
    </div>`;
  }

  private renderSensors() {
    const t = this.t;
    return html`<div class="card">
      <h2>${t("sec_sensors")}</h2>
      <div class="hint">${t("sensors_hint")}</div>
      ${this.draft.sensors.map((s, i) => {
        const note = this.tried[s.id];
        const edit = (mutate: (x: SensorDef) => void) => this.change((x) => mutate(x.sensors[i]));
        return html`<div class="item">
          <div class="row">
            <input class="small" placeholder=${t("name")} .value=${s.name} @input=${(e: Event) => edit((x) => (x.name = val(e)))} />
            <input class="wide mono" placeholder=${t("pattern")} .value=${s.pattern} @input=${(e: Event) => edit((x) => (x.pattern = val(e)))} />
            ${this.formatSelect(s.format, (f) => edit((x) => (x.format = f)))}
          </div>
          <div class="row muted">
            <span>${t("capture")}</span>
            <input class="small mono" .value=${s.capture} @input=${(e: Event) => edit((x) => (x.capture = val(e)))} />
            <span>${t("scale")}</span>
            <input class="tiny" type="number" step="any" .value=${String(s.scale)} @input=${(e: Event) => edit((x) => (x.scale = num(e, 1)))} />
            <span>${t("offset")}</span>
            <input class="tiny" type="number" step="any" .value=${String(s.offset)} @input=${(e: Event) => edit((x) => (x.offset = num(e)))} />
            <span>${t("unit")}</span>
            <input class="tiny" .value=${s.unit} @input=${(e: Event) => edit((x) => (x.unit = val(e)))} />
            <span>${t("device_class")}</span>
            <input class="small" placeholder="voltage" .value=${s.device_class} @input=${(e: Event) => edit((x) => (x.device_class = val(e)))} />
            <span>${t("precision")}</span>
            <input class="tiny" type="number" min="0" max="6" .value=${s.precision === null ? "" : String(s.precision)}
              @input=${(e: Event) => edit((x) => (x.precision = val(e) === "" ? null : Math.max(0, Math.round(num(e)))))} />
            <span class="grow"></span>
            <button class="link" @click=${() => this.tryPattern(s.id, s.pattern, s.format)}>${t("try_pattern")}</button>
            <button class="link danger" @click=${() => this.change((x) => x.sensors.splice(i, 1))}>${t("remove")}</button>
          </div>
          ${note ? html`<div class="note mono ${note.ok ? "ok" : "bad"}" style="white-space:pre-wrap">${note.text}</div>` : nothing}
        </div>`;
      })}
      <button @click=${() =>
        this.change((x) =>
          x.sensors.push({
            id: newId(), name: "", pattern: "", format: "hex", capture: "value",
            scale: 1, offset: 0, unit: "", device_class: "", precision: null,
          }),
        )}>${t("add_sensor")}</button>
    </div>`;
  }

  private renderPoll() {
    const t = this.t;
    return html`<div class="card">
      <h2>${t("sec_poll")}</h2>
      <div class="hint">${t("poll_hint")}</div>
      <div class="row">
        <span class="muted">${t("poll_command")}</span>
        ${this.commandSelect(this.draft.poll_command, (id) =>
          this.change((x) => {
            x.poll_command = id;
            if (id && !x.poll_interval) x.poll_interval = 30;
          }), t("no_poll"))}
        ${this.draft.poll_command
          ? html`<span class="muted">${t("poll_interval")}</span>
              <input class="small" type="number" min="1" max="86400" .value=${String(this.draft.poll_interval)}
                @input=${(e: Event) => this.change((x) => (x.poll_interval = Math.max(1, Math.round(num(e, 30)))))} />`
          : nothing}
      </div>
    </div>`;
  }

  render() {
    if (!this.draft) return nothing;
    const t = this.t;
    return html`
      ${this.renderBasic()} ${this.renderParams()} ${this.renderButtons()} ${this.renderCommands()} ${this.renderActions()}
      ${this.renderChoices()} ${this.renderRanges()} ${this.renderRules()} ${this.renderSensors()} ${this.renderPoll()}
      <div class="footer">
        <button @click=${this.leave}>${t("back")}</button>
        ${this.draft.id ? html`<button class="danger" @click=${this.removeDevice}>${t("delete_device")}</button>` : nothing}
        <span class="grow note ${this.status ? (this.status.ok ? "ok" : "bad") : ""}" style="white-space:pre-wrap"
          >${this.status?.text ?? (this.dirty ? t("unsaved") : "")}</span
        >
        <button class="primary" ?disabled=${this.busy} @click=${this.save}>${t("save")}</button>
      </div>
    `;
  }
}

define("woow-serial-device-editor", WoowBusDeviceEditor);
