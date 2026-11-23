"""Permalink (Begrenzen), Presets und Zufalls-Seed-Button (Standardmuster aus dem Demo-Portfolio)."""

import random
from dataclasses import dataclass

import streamlit as st

import stp_constants as C


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: type
    default: object
    lo: float | None = None
    hi: float | None = None
    choices: tuple | None = None


SETTING_SPECS = {
    "n_cranes": SettingSpec("kraene", int, C.N_CRANES_DEFAULT, *C.N_CRANES_RANGE),
    "orders_per_crane": SettingSpec("auftraege", int, C.ORDERS_PER_CRANE_DEFAULT, *C.ORDERS_PER_CRANE_RANGE),
    "seed_input": SettingSpec("seed", int, C.SEED_DEFAULT, *C.SEED_RANGE),
    "dep_pct": SettingSpec("stapel", int, C.DEP_PCT_DEFAULT, *C.DEP_PCT_RANGE),
    "mis_pct": SettingSpec("fehlstapel", int, C.MIS_PCT_DEFAULT, *C.MIS_PCT_RANGE),
    "n_sc": SettingSpec("sc", int, C.N_SC_DEFAULT, *C.N_SC_RANGE),
    "strategy": SettingSpec("zuschnitt", str, C.STRATEGY_DEFAULT, choices=C.STRATEGY_KEYS),
    "w_crane": SettingSpec("gewicht", int, C.W_CRANE_DEFAULT, *C.W_CRANE_RANGE),
    "penalty": SettingSpec("strafe", int, C.PENALTY_DEFAULT, *C.PENALTY_RANGE),
    "time_limit": SettingSpec("zeit", int, C.TIME_LIMIT_DEFAULT, *C.TIME_LIMIT_RANGE),
}
# Schlüssel der Preset-Wörterbücher (stp_constants.PRESETS) -> Schlüssel im Session State
PRESET_KEYS = {"n_cranes": "n_cranes", "orders_per_crane": "orders_per_crane", "seed": "seed_input", "dep_pct": "dep_pct", "mis_pct": "mis_pct",
               "n_sc": "n_sc", "strategy": "strategy", "w_crane": "w_crane", "penalty": "penalty", "time_limit": "time_limit"}


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def clamp(spec: SettingSpec, value):
    """Wert auf die Grenzen des Reglers begrenzen; Auswahlwerte außerhalb der Liste bleiben ungültig (None)."""
    if spec.choices is not None:
        return value if value in spec.choices else None
    if spec.lo is not None:
        value = max(spec.lo, value)
    if spec.hi is not None:
        value = min(spec.hi, value)
    return value


def load_permalink_settings():
    """Einmal je Sitzung: Werte aus der Adresszeile übernehmen, auf die Reglergrenzen begrenzt."""
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            try:
                value = clamp(spec, spec.caster(qp[spec.url_param]))
            except (ValueError, TypeError):
                continue
            if value is not None:
                st.session_state[state_key] = value
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """`values`: {state_key: aktueller Wert}; die Adresszeile spiegelt die Konfiguration."""
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = str(value)
    except Exception:
        pass


def apply_preset(name):
    for key, state_key in PRESET_KEYS.items():
        if key in C.PRESETS[name]:
            st.session_state[state_key] = C.PRESETS[name][key]


def aktives_preset():
    """Name des Presets, dessen Werte GENAU den aktuellen Einstellungen entsprechen, sonst None.

    Zustandslos: verglichen wird jeder Regler aus SETTING_SPECS (ein Preset ohne Eintrag für einen Regler meint dessen
    Standardwert) mit dem Session State. Ein später ergänzter Regler braucht nur seinen Eintrag in SETTING_SPECS,
    dann hebt auch seine Änderung die Markierung auf (tests/test_layout.py prüft das für jeden Regler)."""
    preset_key_of = {state_key: key for key, state_key in PRESET_KEYS.items()}
    for name, preset in C.PRESETS.items():
        if all(
            st.session_state.get(state_key, spec.default) == preset.get(preset_key_of.get(state_key), spec.default)
            for state_key, spec in SETTING_SPECS.items()
        ):
            return name
    return None


def sidebar_presets():
    """Schnellstart oben in der Seitenleiste; das aktive Preset ist hervorgehoben (`type="primary"`)."""
    if not C.PRESETS:
        return
    st.header("🎯 Schnellstart")
    st.caption("Ein Beispielszenario laden:")
    aktiv = aktives_preset()
    for name in C.PRESETS:
        st.button(
            name, width="stretch", on_click=apply_preset, args=(name,), help=C.PRESET_HELP.get(name, ""), key=f"preset_{name}",
            type="primary" if aktiv == name else "secondary",
        )


def randomize_seed():
    st.session_state["seed_input"] = random.randint(0, C.SEED_RANGE[1])
