const CARD_VERSION = "0.1.0";

class TransportesPTCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  setConfig(config) {
    if (!config.entities || !config.entities.length) {
      throw new Error("Please define at least one entity");
    }
    this._config = {
      title: config.title || "Próximas Chegadas",
      entities: config.entities,
      show_alerts: config.show_alerts !== false,
      max_arrivals: config.max_arrivals || 5,
      theme: config.theme || "auto",
      ...config,
    };
  }

  getCardSize() {
    return 3 + (this._config?.entities?.length || 1);
  }

  static getConfigElement() {
    return document.createElement("transportes-pt-card-editor");
  }

  static getStubConfig() {
    return {
      entities: [],
      title: "Próximas Chegadas",
      show_alerts: true,
      max_arrivals: 5,
    };
  }

  _render() {
    if (!this._hass || !this._config) return;

    const isDark =
      this._config.theme === "dark" ||
      (this._config.theme === "auto" &&
        this._hass.themes?.darkMode);

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }
        .card {
          padding: 16px;
          border-radius: 12px;
          background: var(--ha-card-background, ${isDark ? "#1c1c1e" : "#fff"});
          color: var(--primary-text-color, ${isDark ? "#fff" : "#1c1c1e"});
          box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0,0,0,0.1));
          font-family: var(--ha-card-font-family, system-ui);
        }
        .title {
          font-size: 1.1em;
          font-weight: 600;
          margin-bottom: 12px;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .title-icon {
          width: 20px;
          height: 20px;
        }
        .stop-section {
          margin-bottom: 12px;
        }
        .stop-name {
          font-size: 0.85em;
          font-weight: 500;
          color: var(--secondary-text-color, #888);
          margin-bottom: 6px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .arrival-row {
          display: flex;
          align-items: center;
          padding: 6px 0;
          border-bottom: 1px solid var(--divider-color, ${isDark ? "#333" : "#eee"});
        }
        .arrival-row:last-child {
          border-bottom: none;
        }
        .line-badge {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 42px;
          height: 24px;
          border-radius: 4px;
          font-size: 0.75em;
          font-weight: 700;
          color: #fff;
          background: var(--primary-color, #4caf50);
          margin-right: 10px;
          padding: 0 6px;
        }
        .destination {
          flex: 1;
          font-size: 0.9em;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .eta {
          font-size: 1em;
          font-weight: 700;
          min-width: 40px;
          text-align: right;
        }
        .eta-unit {
          font-size: 0.7em;
          font-weight: 400;
          color: var(--secondary-text-color, #888);
          margin-left: 2px;
        }
        .alert-banner {
          background: #ff9800;
          color: #fff;
          padding: 8px 12px;
          border-radius: 8px;
          font-size: 0.8em;
          margin-top: 8px;
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .alert-icon {
          font-size: 1.2em;
        }
        .no-data {
          color: var(--secondary-text-color, #888);
          font-size: 0.85em;
          font-style: italic;
          padding: 8px 0;
        }
      </style>
      <ha-card>
        <div class="card">
          <div class="title">
            <span>🚌</span>
            <span>${this._config.title}</span>
          </div>
          ${this._renderStops()}
          ${this._config.show_alerts ? this._renderAlerts() : ""}
        </div>
      </ha-card>
    `;
  }

  _renderStops() {
    return this._config.entities
      .map((entityId) => {
        const state = this._hass.states[entityId];
        if (!state) {
          return `<div class="stop-section"><div class="no-data">Entity ${entityId} not found</div></div>`;
        }

        const attrs = state.attributes;
        const arrivals = attrs.arrivals || [];
        const stopName = attrs.stop_id || entityId.split(".").pop();

        if (!arrivals.length) {
          return `
            <div class="stop-section">
              <div class="stop-name">${stopName}</div>
              <div class="no-data">Sem chegadas previstas</div>
            </div>
          `;
        }

        const rows = arrivals
          .slice(0, this._config.max_arrivals)
          .map((arr) => {
            const eta = this._calcEta(arr);
            return `
              <div class="arrival-row">
                <span class="line-badge">${arr.line || "?"}</span>
                <span class="destination">${arr.destination || "—"}</span>
                <span class="eta">${eta}<span class="eta-unit">min</span></span>
              </div>
            `;
          })
          .join("");

        return `
          <div class="stop-section">
            <div class="stop-name">${stopName}</div>
            ${rows}
          </div>
        `;
      })
      .join("");
  }

  _renderAlerts() {
    // Find alert binary sensors
    const alertEntities = Object.keys(this._hass.states).filter(
      (eid) =>
        eid.startsWith("binary_sensor.") &&
        this._hass.states[eid].attributes.alert_count !== undefined
    );

    let alertHtml = "";
    for (const eid of alertEntities) {
      const state = this._hass.states[eid];
      if (state.state === "on") {
        const alerts = state.attributes.alerts || [];
        for (const alert of alerts.slice(0, 2)) {
          alertHtml += `
            <div class="alert-banner">
              <span class="alert-icon">⚠️</span>
              <span>${alert.title || "Alerta de serviço"}</span>
            </div>
          `;
        }
      }
    }
    return alertHtml;
  }

  _calcEta(arrival) {
    if (arrival.estimated) {
      // Try parsing as HH:MM:SS or ISO
      try {
        const parts = arrival.estimated.split(":");
        if (parts.length === 3) {
          const now = new Date();
          const arrTime = new Date();
          arrTime.setHours(parseInt(parts[0]), parseInt(parts[1]), parseInt(parts[2]));
          const diff = Math.round((arrTime - now) / 60000);
          return diff >= 0 ? diff : 0;
        }
      } catch (e) {}
    }
    return "?";
  }
}

// Card editor for visual config
class TransportesPTCardEditor extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
  }

  setConfig(config) {
    this._config = config;
    this._render();
  }

  _render() {
    if (!this._config) return;
    this.innerHTML = `
      <div style="padding: 16px;">
        <p><strong>Transportes PT Card</strong></p>
        <p style="color: #888; font-size: 0.9em;">
          Configure the card in YAML mode. Add sensor entities for your stops.
        </p>
        <pre style="background: #f5f5f5; padding: 8px; border-radius: 4px; font-size: 0.8em;">
type: custom:transportes-pt-card
title: Próximas Chegadas
entities:
  - sensor.paragem_060002
show_alerts: true
max_arrivals: 5</pre>
      </div>
    `;
  }

  get _value() {
    return this._config;
  }
}

customElements.define("transportes-pt-card", TransportesPTCard);
customElements.define("transportes-pt-card-editor", TransportesPTCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "transportes-pt-card",
  name: "Transportes PT",
  description: "Real-time transit arrivals card for Portuguese public transit",
  preview: true,
});

console.info(`%c TRANSPORTES-PT-CARD %c v${CARD_VERSION} `, "background:#4caf50;color:#fff;font-weight:bold", "");
