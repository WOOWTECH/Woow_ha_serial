import { css } from "lit";

// Shared look: Home Assistant theme variables, so light / dark themes just work.
export const shared = css`
  :host {
    display: block;
    color: var(--primary-text-color);
    font-family: var(--paper-font-body1_-_font-family, Roboto, "Noto Sans TC", sans-serif);
  }
  .card {
    background: var(--card-background-color, #fff);
    border: 1px solid var(--divider-color, #e0e0e0);
    border-radius: var(--ha-card-border-radius, 12px);
    padding: 16px;
    margin-bottom: 16px;
  }
  .card h2 {
    margin: 0 0 12px;
    font-size: 1.1em;
    font-weight: 500;
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }
  .grow {
    flex: 1 1 auto;
    min-width: 0;
  }
  .muted {
    color: var(--secondary-text-color);
    font-size: 0.9em;
  }
  .mono {
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 0.92em;
    word-break: break-all;
  }
  .chip {
    display: inline-block;
    padding: 1px 8px;
    border-radius: 10px;
    font-size: 0.8em;
    line-height: 1.6;
    background: var(--secondary-background-color, #eee);
    color: var(--secondary-text-color);
    white-space: nowrap;
  }
  .chip.ok {
    background: rgba(67, 160, 71, 0.15);
    color: var(--success-color, #43a047);
  }
  .chip.warn {
    background: rgba(255, 152, 0, 0.15);
    color: var(--warning-color, #ff9800);
  }
  .chip.bad {
    background: rgba(219, 68, 55, 0.12);
    color: var(--error-color, #db4437);
  }
  .chip.info {
    background: rgba(3, 169, 244, 0.14);
    color: var(--info-color, #039be5);
  }
  button {
    font: inherit;
    border: 1px solid var(--divider-color, #ccc);
    background: var(--card-background-color, #fff);
    color: var(--primary-text-color);
    border-radius: 8px;
    padding: 4px 10px;
    cursor: pointer;
  }
  button:hover {
    border-color: var(--primary-color);
  }
  button.primary {
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: var(--text-primary-color, #fff);
  }
  button.link {
    border: none;
    background: none;
    color: var(--primary-color);
    padding: 2px 4px;
  }
  button.danger {
    color: var(--error-color, #db4437);
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  input,
  select {
    font: inherit;
    color: var(--primary-text-color);
    background: var(--card-background-color, #fff);
    border: 1px solid var(--divider-color, #ccc);
    border-radius: 8px;
    padding: 6px 8px;
    min-width: 0;
  }
  input:focus,
  select:focus {
    outline: 2px solid var(--primary-color);
    outline-offset: -1px;
  }
  .empty {
    padding: 24px 8px;
    text-align: center;
    color: var(--secondary-text-color);
  }
  .rx {
    color: var(--success-color, #43a047);
  }
  .tx {
    color: var(--info-color, #039be5);
  }
`;
