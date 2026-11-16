"""Presets: Vollständigkeit, gültige Werte, Standard-Preset gleich Standardeinstellungen, Permalink-Begrenzung."""

import pytest

import stp_constants as C
import stp_evaluation as ev
import stp_pools as PL
import stp_presets as P


def test_jedes_preset_hat_hilfetext_und_nur_bekannte_schluessel():
    assert set(C.PRESETS) == set(C.PRESET_HELP)
    for name, preset in C.PRESETS.items():
        assert set(preset) <= set(P.PRESET_KEYS), name
        assert C.PRESET_HELP[name]


def test_preset_werte_liegen_in_den_reglergrenzen():
    for name, preset in C.PRESETS.items():
        for key, state_key in P.PRESET_KEYS.items():
            if key not in preset:
                continue
            spec = P.SETTING_SPECS[state_key]
            if spec.choices is not None:
                assert preset[key] in spec.choices, (name, key)
            else:
                assert spec.lo <= preset[key] <= spec.hi, (name, key)


def test_jedes_preset_ist_live_rechenbar():
    for name, preset in C.PRESETS.items():
        s = ev.Settings(**preset)
        assert s.n_cranes * s.jobs_per_crane <= C.MAX_JOBS, name
        assert s.n_sc >= PL.pool_count(s.n_cranes, s.strategy), name


def test_standard_preset_gleich_den_standardeinstellungen():
    assert ev.Settings(**C.PRESETS["Kleiner Hafen"]) == ev.Settings()
    assert next(iter(C.PRESETS)) == "Kleiner Hafen"


def test_setting_specs_decken_jeden_preset_schluessel_ab():
    assert set(P.PRESET_KEYS.values()) == set(P.SETTING_SPECS)
    assert set(P.PRESET_KEYS) >= {"n_cranes", "jobs_per_crane", "seed", "dep_pct", "mis_pct", "n_sc", "strategy", "w_crane", "penalty", "time_limit"}


def test_url_parameter_sind_eindeutig():
    params = [s.url_param for s in P.SETTING_SPECS.values()]
    assert len(params) == len(set(params))


def test_begrenzen_der_permalink_werte():
    spec = P.SETTING_SPECS["n_sc"]
    assert P.clamp(spec, 0) == spec.lo and P.clamp(spec, 999) == spec.hi and P.clamp(spec, 5) == 5
    strat = P.SETTING_SPECS["strategy"]
    assert P.clamp(strat, "adjacent") == "adjacent" and P.clamp(strat, "unsinn") is None and P.clamp(strat, "single") is None


def test_zeitlimit_obergrenze_gilt_nur_mit_umgebungsvariable(monkeypatch):
    monkeypatch.delenv(C.MAX_SECONDS_ENV, raising=False)
    assert C.time_limit(20) == 20
    monkeypatch.setenv(C.MAX_SECONDS_ENV, "3")
    assert C.time_limit(20) == 3 and C.time_limit(2) == 2


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_preset_einstellungen_lassen_sich_als_settings_bauen(name):
    s = ev.Settings(**C.PRESETS[name])
    assert s.seed == C.PRESETS[name].get("seed", C.SEED_DEFAULT)
