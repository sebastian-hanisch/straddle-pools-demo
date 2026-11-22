"""Straddle Carrier: Pools, Abhängigkeiten und getrennte Rechnung - interaktive Fall-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Lauffähig mit: streamlit run app.py
"""

import streamlit as st

import stp_constants as C
import stp_evaluation as ev
import stp_pools as PL
from stp_evaluation import Settings, de
from stp_layout import dunkles_design, kopf_css
from stp_pdf_export import generate_pdf
from stp_presets import (
    bounds,
    init_session_state_defaults,
    load_permalink_settings,
    randomize_seed,
    sidebar_presets,
    sync_query_params,
)
from stp_visualization import comparison_bars, coupling_map, plan_gantt, time_axis_end

st.set_page_config(page_title="Straddle Carrier – Sebastian Hanisch", layout="wide")


@st.cache_data(show_spinner="Rechne alle Verfahren auf dieser Instanz (je Modell höchstens das eingestellte Zeitlimit) …")
def _analysis(settings):
    return ev.analyse(settings)


FOOTER = (
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zum Thema: [Hafenlogistik optimieren](https://sebastianhanisch.net/hafenlogistik-optimierung.html)."
)

# Fester Kopf: nur der Titel bleibt beim Scrollen oben (Stylesheet in stp_layout.py).
st.html(kopf_css(dunkles_design()))
with st.container(key="kopf"):
    st.title("🧩 Straddle Carrier: Pools, Abhängigkeiten und getrennte Rechnung")
st.markdown(
    """
Jeder Kran hat eine feste **Reihenfolge** von Aufträgen mit **Richtzeiten** (am Kran wichtiger als am Yard). Straddle Carrier (**SC**) sind in **Pools** fest einem oder mehreren Kränen zugeordnet.
Container, die im Yard übereinander stehen, aber zu verschiedenen Kränen gehören, machen Aufträge **voneinander abhängig**, auch über Pools hinweg.
Die Demo vergleicht sieben Verfahren auf derselben Instanz: **Gesamtplanung** ohne Pooling, mit festen Pools und mit Leihen, **strikt parallele Pool-Rechnung** mit Nachbehandlung der Abhängigkeiten, ein einfaches gieriges Verfahren.
Gezeigt wird, was der **Pool-Zuschnitt** kostet und was es kostet, die Pools **getrennt zu rechnen**. Alle Instanzen sind erzeugt und alle Annahmen stehen im Abschnitt **🚧 Wo die Annahmen enden**.
"""
)

# erklaerseite:einfach:start (erzeugt von tools/set_demo_explainer.py (Website-Repo) aus tools/content/explainers/straddle-pools-erklaert.json, nicht von Hand ändern)
with st.expander("💬 In einfachen Worten"):
    st.markdown(
        """
Ein Containerterminal hat mehrere Kräne, und jeder Kran hat eine feste Liste von Aufträgen mit Richtzeiten. Straddle Carrier fahren die Container zwischen Kran und Lagerfläche und sind in Pools festen Kränen zugeordnet. Container, die im Stapel übereinanderstehen, aber zu verschiedenen Kränen gehören, machen Aufträge voneinander abhängig, auch über Pools hinweg. Die Demo plant dieselbe erzeugte Instanz auf mehrere Arten: gemeinsam ohne Pools, gemeinsam mit festen Pools, mit Aushelfen in fremden Pools und getrennt je Pool mit Nachbehandlung der Abhängigkeiten. Sie zeigt, was der Zuschnitt der Pools kostet und was es kostet, die Pools getrennt zu rechnen. Alle Instanzen sind erzeugt, alle Zeiten und Gewichte sind Annahmen.

[Ausführlich und verständlich erklärt, mit Fachteil](https://sebastianhanisch.net/straddle-pools-erklaert.html)
        """
    )
# erklaerseite:einfach:end
st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    sidebar_presets()  # Schnellstart oben, das aktive Preset ist hervorgehoben
    st.header("🏗️ Terminal und Aufträge")
    n_cranes = st.slider("Kräne", *bounds("n_cranes"), key="n_cranes", help="Zahl der Kräne am Kai; jeder hat eine feste Auftragsreihenfolge.")
    jobs_per_crane = st.slider("Aufträge je Kran", *bounds("jobs_per_crane"), key="jobs_per_crane",
                               help=f"Zahl der Aufträge in der Reihenfolge jedes Krans; höchstens {C.MAX_JOBS} Aufträge insgesamt (größere Fälle nur in der vorgerechneten Reihe).")
    seed = st.number_input("Zufalls-Seed der Instanz", *bounds("seed_input"), key="seed_input", step=1)
    st.button("🎲 Neue Instanz generieren", width="stretch", on_click=randomize_seed)
    st.header("📦 Abhängigkeiten")
    dep_pct = st.slider("Aufträge in Stapelpaaren (%)", *bounds("dep_pct"), step=C.DEP_PCT_STEP, key="dep_pct",
                        help="Anteil der Aufträge, deren Container mit einem Container eines anderen Krans im selben Stapel steht.")
    mis_pct = st.slider("Davon entgegen der Bedarfsreihenfolge (%)", *bounds("mis_pct"), step=C.MIS_PCT_STEP, key="mis_pct",
                        help="Anteil der Stapelpaare, bei denen der Auftrag, der am Stellplatz zuerst erledigt sein muss, in der Reihenfolge seines Krans später dran ist als der andere.")
    st.header("🎯 Pooling und Zielgröße")
    n_sc = st.slider("SC insgesamt", *bounds("n_sc"), key="n_sc", help="Größe der Flotte; jeder Pool bekommt mindestens einen SC.")
    strategy = st.selectbox("Pool-Zuschnitt", C.STRATEGY_KEYS, key="strategy", format_func=lambda k: PL.STRATEGY_LABELS[k],
                            help="Welche Kräne einen Pool bilden: je Kran, benachbarte Paare, Paare mit ausgeglichener Arbeitslast, Paare mit den meisten gemeinsamen Stapel-Abhängigkeiten.")
    st.caption("Die SC-Zahl je Pool folgt der Arbeitslast der Kräne des Pools. Die Wahl setzt nur den Zuschnitt, alle Regler bleiben frei.")
    w_crane = st.slider("Gewicht Verspätung am Kran", *bounds("w_crane"), key="w_crane", help="Die Verspätung am Yard wiegt immer 1.")
    penalty = st.slider("Strafe je poolfremdem Auftrag", *bounds("penalty"), step=C.PENALTY_STEP, key="penalty",
                        help="Nur beim Leihen: Notlösung, wenn ein SC einen Auftrag eines fremden Pools fährt.")
    time_limit = st.slider("Zeitlimit je Modell (s)", *bounds("time_limit"), key="time_limit", help="Danach gilt das beste gefundene Ergebnis ohne Beweis, dass es optimal ist.")

sync_query_params({"n_cranes": int(n_cranes), "jobs_per_crane": int(jobs_per_crane), "seed_input": int(seed), "dep_pct": int(dep_pct), "mis_pct": int(mis_pct),
                   "n_sc": int(n_sc), "strategy": strategy, "w_crane": int(w_crane), "penalty": int(penalty), "time_limit": int(time_limit)})

needed = PL.pool_count(int(n_cranes), strategy)
if int(n_sc) < needed:
    st.warning(f"Der Zuschnitt „{PL.STRATEGY_LABELS[strategy]}“ bildet bei {int(n_cranes)} Kränen {needed} Pools und braucht mindestens {needed} SC; eingestellt sind {int(n_sc)}. Bitte die SC-Zahl erhöhen oder einen anderen Zuschnitt wählen.")
    st.markdown("---")
    st.caption(FOOTER)
    st.stop()
if int(n_cranes) * int(jobs_per_crane) > C.MAX_JOBS:
    st.warning(f"{int(n_cranes)} Kräne mit je {int(jobs_per_crane)} Aufträgen sind {int(n_cranes) * int(jobs_per_crane)} Aufträge; live höchstens {C.MAX_JOBS}. Bitte die Auftragszahl je Kran senken.")
    st.markdown("---")
    st.caption(FOOTER)
    st.stop()

settings = Settings(int(n_cranes), int(jobs_per_crane), int(n_sc), int(dep_pct), int(mis_pct), strategy, int(w_crane), int(penalty), int(time_limit), int(seed))
a = _analysis(settings)
m = a.methods

# --- Ergebnis ------------------------------------------------------------------------------------------------------------------------------

st.markdown("## 🎯 Ergebnis")
st.caption(f"{a.inst.n_jobs} Aufträge, {a.inst.n_deps()} Abhängigkeiten ({PL.cross_arcs(a.inst, a.pools)} zwischen Pools), {a.pools.n_pools} Pools "
           f"({', '.join(str(len(a.pools.scs_of(p))) for p in range(a.pools.n_pools))} SC). Zielwert = {settings.w_crane} · Kranverspätung + {C.W_YARD} · Yard-Verspätung (Sekunden) + Strafe je poolfremdem Auftrag; kleiner ist besser.")
c1, c2, c3, c4 = st.columns(4)
# Delta immer als „mein Wert minus Referenz“; die Farbe regelt delta_color="inverse" (Vorzeichen-Falle, DEMO-PLAYBOOK §2).
c1.metric("Gesamt ohne Pooling", de(a.obj("g1")), delta="Referenz", delta_color="off")
c2.metric("Gesamt, Pools fest", de(a.obj("g2")), delta=f"{a.obj('g2') - a.obj('g1'):+,} gegen ohne Pooling".replace(",", "."), delta_color="inverse")
c3.metric("Parallel + Runde", de(a.obj("p1")), delta=f"{a.obj('p1') - a.obj('g2'):+,} gegen Pools fest".replace(",", "."), delta_color="inverse")
c4.metric("Gieriges Listenverfahren", de(a.obj("list")), delta=f"{a.obj('list') - a.obj('g2'):+,} gegen Pools fest".replace(",", "."), delta_color="inverse")

rows = []
for key in C.METHOD_KEYS:
    if key not in m:
        continue
    x = m[key]
    rows.append({
        "Verfahren": C.METHOD_LABELS[key],
        "Zielwert": de(x.cost.obj),
        "Kranverspätung (s)": de(x.cost.tard_crane),
        "Yard-Verspätung (s)": de(x.cost.tard_yard),
        "poolfremde Aufträge": str(x.cost.foreign) if key in ("g1", "g3") else "0",
        "Rechenzeit (s)": de(x.wall, 1),
        "Status": x.status,
    })
st.dataframe(rows, hide_index=True, width="stretch")
st.caption("Rechenzeit der parallelen Verfahren = längste Pool-Zeit je Durchgang (angenommen: alle Pools rechnen gleichzeitig; hier nacheinander gemessen). "
           "Status „Zeitlimit“: bestes gefundenes Ergebnis ohne Beweis, dass es optimal ist. „Teilmodelle bewiesen“ (parallele Verfahren) heißt nur, dass jedes Pool-Modell optimal gelöst ist, nicht der zusammengesetzte Plan. Stern in der Grafik: kein Optimalitätsbeweis für den Plan. „Poolfremd“ bei der Gesamtplanung ohne Pooling ist nur eine Zählung, ohne Strafe.")
st.plotly_chart(comparison_bars(a), width="stretch", key="chart_compare")
st.download_button("📄 Ergebnis als PDF", data=generate_pdf(a), file_name="straddle_pools_ergebnis.pdf", mime="application/pdf", key="primary_pdf_download")

st.markdown("### 🗓️ Der Plan")
pc1, pc2 = st.columns(2)
left = pc1.selectbox("Plan links", [k for k in C.METHOD_KEYS if k in m], index=[k for k in C.METHOD_KEYS if k in m].index("p1"), key="plan_left", format_func=lambda k: C.METHOD_LABELS[k])
right = pc2.selectbox("Plan rechts", [k for k in C.METHOD_KEYS if k in m], index=[k for k in C.METHOD_KEYS if k in m].index("g2"), key="plan_right", format_func=lambda k: C.METHOD_LABELS[k])
t_end = time_axis_end(m[left], m[right])
g1c, g2c = st.columns(2)
g1c.plotly_chart(plan_gantt(a.inst, a.pools, m[left], a.tk, a.ty, t_end, f"{C.METHOD_LABELS[left]}: Zielwert {de(m[left].cost.obj)}"), width="stretch", key="chart_plan_left")
g2c.plotly_chart(plan_gantt(a.inst, a.pools, m[right], a.tk, a.ty, t_end, f"{C.METHOD_LABELS[right]}: Zielwert {de(m[right].cost.obj)}"), width="stretch", key="chart_plan_right")
st.caption("Eine Zeile je SC; Balken = Auftrag von der ersten Operation bis der SC wieder frei ist (Wartezeiten eingeschlossen), Zahl = Auftragsnummer. Kranfarben: "
           + ", ".join(f"Kran {i + 1} {C.CRANE_COLOR_NAMES[i]}" for i in range(a.inst.n_cranes)) + ".")

# --- Kernfragen ----------------------------------------------------------------------------------------------------------------------------

st.markdown("## ❓ Kernfragen")
st.markdown("**1. Was kostet der Pool-Zuschnitt?**")
kind, text = ev.verdict_zuschnitt(a)
getattr(st, kind)(text)
st.markdown("**2. Wann hilft Leihen?**")
kind, text = ev.verdict_leihen(a)
getattr(st, kind)(text)
st.markdown("**3. Was kostet die getrennte Pool-Rechnung?**")
kind, text = ev.verdict_parallel(a)
getattr(st, kind)(text)

st.markdown("### 🔗 Wo die Pools zusammenhängen")
st.plotly_chart(coupling_map(a.inst, a.pools), width="stretch", key="chart_coupling")
st.caption(f"Zahl der Abhängigkeiten zwischen je zwei Kränen, nach Pools geordnet; orange Rahmen = Pools. Zahlen außerhalb der Rahmen sind Abhängigkeiten zwischen Pools: {PL.cross_arcs(a.inst, a.pools)} von {a.inst.n_deps()}.")

st.markdown("### 📊 Vorgerechnete Messreihe")
series = ev.load_series()
if not series:
    st.info("Die vorgerechnete Messreihe (viele Instanzen je Szenario) liegt in dieser Fassung noch nicht vor.")
else:
    srows = []
    for name, sc in series["scenarios"].items():
        for key, label in (("p0", "Parallel"), ("p1", "Parallel + Runde")):
            s = ev.series_stats(sc["records"], key)
            srows.append({"Szenario": name, "Verfahren": label, "Instanzen": s["n"], "gleich Pools fest": s["equal"], "mehr als doppelt": s["double"],
                          "größter Aufschlag": de(s["worst"]), "Mittel": de(s["mean_key"]), "Mittel Pools fest": de(s["mean_ref"])})
    st.dataframe(srows, hide_index=True, width="stretch")
    meta = series["meta"]
    st.caption(f"Je Szenario {meta['instances']} erzeugte Instanzen (24 Aufträge), Zeitlimit {meta['time_limit']} s, {meta['workers']} CP-SAT-Prozesse, gerechnet am {meta['date']}. "
               "„Gleich Pools fest“: Zielwert gleich dem der Gesamtplanung mit festen Pools (in den meisten Instanzen deren bewiesenes Optimum); „mehr als doppelt“: mehr als das Doppelte plus 50. Das Mittel wird von wenigen Instanzen bestimmt. Die parallelen Verfahren hängen davon ab, welchen von mehreren gleich guten Plänen jedes Pool-Modell liefert; die Zählungen können sich zwischen Läufen um wenige Instanzen ändern.")

st.markdown("---")

# --- Methodenvergleich ---------------------------------------------------------------------------------------------------------------------

with st.expander("🔧 Wie wir das erreichen – vollständiger Methodenvergleich"):
    tabs = st.tabs([C.METHOD_LABELS[k] for k in C.METHOD_KEYS if k in m] + ["🧮 Exakt"])
    for tab, key in zip(tabs, [k for k in C.METHOD_KEYS if k in m]):
        with tab:
            st.markdown(C.METHOD_DESCRIPTIONS[key])
            x = m[key]
            st.markdown(f"Zielwert **{de(x.cost.obj)}**, Rechenzeit **{de(x.wall, 1)} s**, Status **{x.status}**.")
    with tabs[-1]:
        st.markdown("Die Gesamtmodelle sind CP-SAT-Modelle. Ist der Status „bewiesen“, ist der Zielwert das Optimum des Modells; sonst steht hier die Schranke des Lösers.")
        erows = []
        for key in ("g1", "g2", "g3"):
            x = m[key]
            gap = "–" if x.bound is None or x.cost.obj == 0 else de(100.0 * (x.cost.obj - x.bound) / x.cost.obj, 1) + " %"
            erows.append({"Verfahren": C.METHOD_LABELS[key], "Zielwert": de(x.cost.obj), "Schranke": "–" if x.bound is None else de(x.bound, 0), "Status": x.status, "Abstand zur Schranke": gap})
        st.dataframe(erows, hide_index=True, width="stretch")
        st.caption("Der Abstand zur Schranke ist (Zielwert − Schranke) / Zielwert; bei bewiesenem Optimum 0 %. Zeitlimit-Ergebnisse sind nie als „optimal“ ausgewiesen.")

with st.expander("📐 Mathematische Formulierung"):
    # erklaerseite:lesehilfe:start (erzeugt von tools/set_demo_explainer.py (Website-Repo) aus tools/content/explainers/straddle-pools-erklaert.json, nicht von Hand ändern)
    st.markdown(
        r"""
**Lesehilfe.** Gegeben sind Aufträge $j$ mit Kran $c_j$, Art Laden $L$ oder Löschen $D$ und Stellplatz $s_j$, Straddle Carrier (SC) $k$ mit Startposition $o_k$, Richtzeiten $\mathrm{tk}_j$ (Kran) und $\mathrm{ty}_j$ (Yard), eine Fahrzeit $\tau(u,v)$ zwischen Orten, Übergabezeit $H$ und Operationszeit $S$, Abhängigkeiten $\mathcal D$ zwischen Aufträgen, die Auftragsreihenfolgen der Kräne, Pools $\pi$ sowie Gewichte und Strafe. Gesucht sind die Zuordnung der Aufträge zu den SC, ihre Reihenfolge je SC und alle Zeiten, sodass der gewichtete Zielwert aus Verspätungen und Strafe möglichst klein ist.

| Symbol | Bedeutung |
|---|---|
| $j$, $i$, $l$ | Aufträge (je eine Container-Bewegung); der Index $0$ steht für den Standort eines SC, am Anfang und am Ende der Rundreise |
| $c_j$, $s_j$ | Kran und Stellplatz im Yard von Auftrag $j$ |
| $L$, $D$ | Art des Auftrags: Laden (Stellplatz zum Kran) bzw. Löschen (Kran zum Stellplatz) |
| $k$, $o_k$ | SC und seine Startposition |
| $\pi(k)$, $\pi(c)$ | Pool des SC $k$ bzw. des Krans $c$ |
| $\mathrm{tk}_j$, $r_j$ | Richtzeit von Auftrag $j$ am Kran, $\mathrm{tk}_j = 120 + 75\,r_j$ mit $r_j$ als Position in der Kranreihenfolge (der erste Auftrag hat $r_j = 0$); beim Löschen übernimmt der SC frühestens zu dieser Zeit, beim Laden darf er früher am Kran sein |
| $\mathrm{ty}_j$ | Richtzeit am Yard: $\mathrm{tk}_j - d_j - S$ beim Laden, $\mathrm{tk}_j + H + d_j$ beim Löschen |
| $\tau(u,v)$, $d_j$ | Fahrzeit zwischen den Orten $u$ und $v$ (Manhattan-Weg durch 6 m/s, ganze Sekunden) bzw. Fahrzeit von Auftrag $j$ zwischen Kran und Stellplatz |
| $\mathrm{erste\ Position}_j$, $\mathrm{letzte\ Position}_j$ | erster und letzter Ort von Auftrag $j$ (Laden: Stellplatz, dann Kran; Löschen: Kran, dann Stellplatz) |
| $H$, $S$ | Übergabezeit am Kran (20 s) bzw. Operationszeit am Stellplatz (15 s) |
| $\mathcal D$ | Menge der Abhängigkeiten $(i,j)$: die Stellplatz-Operation von $j$ beginnt erst nach der von $i$ |
| $(p,q)$ | zwei aufeinanderfolgende Aufträge der Kranreihenfolge |
| $w_K$, $w_Y$, $\lambda$ | Gewichte der Verspätung am Kran bzw. am Yard (die Marken $K$ und $Y$ stehen für Kran und Yard) und Strafe je poolfremdem Auftrag |
| $x_{jk}$ | $1$, wenn SC $k$ den Auftrag $j$ fährt, sonst $0$ |
| $z^k_{ij}$ | $1$, wenn bei SC $k$ der Auftrag $j$ auf $i$ folgt ($i = 0$: erster Auftrag des SC; $j = 0$: Rückkehr nach dem letzten Auftrag), sonst $0$ |
| $f_j$, $a_j$, $y_j$, $e_j$ | Beginn der ersten Operation, Beginn der Übergabe am Kran, Beginn der Operation am Stellplatz bzw. Zeitpunkt, zu dem der SC wieder frei ist |
| $T^K_j$, $T^Y_j$ | Verspätung von Auftrag $j$ am Kran bzw. am Yard in Sekunden ($T \ge 0$ meint beide) |

[Schritt für Schritt erklärt, mit Herleitung und Literatur](https://sebastianhanisch.net/straddle-pools-erklaert.html#fachleute)
        """
    )
    # erklaerseite:lesehilfe:end
    st.markdown(
        "**Gegeben:** Aufträge $J$ (Kran $c_j$, Art Laden $L$ oder Löschen $D$, Stellplatz $s_j$), SC $V$ mit Startposition $o_k$, Richtzeiten $\\mathrm{tk}_j$ (Kran) und $\\mathrm{ty}_j$ (Yard), "
        "Fahrzeit $\\tau(u,v)$ (Manhattan-Weg durch 6 m/s, ganze Sekunden), $d_j = \\tau(\\text{Kran}_{c_j}, s_j)$, Übergabezeit $H = 20$, Operationszeit $S = 15$, "
        "Richtzeiten $\\mathrm{tk}_j = 120 + 75\\,r_j$ ($r_j$ = Position in der Kranreihenfolge, der erste Auftrag hat $r_j = 0$) und $\\mathrm{ty}_j = \\mathrm{tk}_j - d_j - S$ (Laden) bzw. $\\mathrm{ty}_j = \\mathrm{tk}_j + H + d_j$ (Löschen), "
        "Abhängigkeiten $(i,j) \\in \\mathcal D$ (Stellplatz-Operation von $j$ erst nach der von $i$), Kranreihenfolgen $(p,q)$ (aufeinanderfolgende Aufträge eines Krans), "
        "Pool $\\pi(k)$ des SC und $\\pi(c)$ des Krans, Gewichte $w_K, w_Y$, Strafe $\\lambda$.\n\n"
        "**Gesucht:** Zuordnung $x_{jk}$ und Reihenfolge der Aufträge je SC (Bogen $z^k_{ij}$ = Auftrag $j$ folgt auf $i$ bei SC $k$; $0$ = Start am Standort des SC), Zeiten $f_j, a_j, y_j, e_j$."
    )
    st.latex(r"\min \; w_K \sum_{j} T^K_j + w_Y \sum_{j} T^Y_j + \lambda \sum_{j,k:\ \pi(k) \neq \pi(c_j)} x_{jk} \quad \text{(Gesamtplanung ohne Pooling: } \lambda = 0\text{; mit festen Pools: } x_{jk}=0 \text{ für } \pi(k)\neq\pi(c_j)\text{)}")
    st.latex(r"\sum_k x_{jk} = 1,\qquad \sum_i z^k_{ij} = x_{jk} = \sum_l z^k_{jl},\qquad \sum_j z^k_{0j} = \sum_j z^k_{j0} \le 1")
    st.latex(r"z^k_{0j} = 1 \Rightarrow f_j \ge \tau(o_k, \mathrm{erste\ Position}_j),\qquad z^k_{ij} = 1 \Rightarrow f_j \ge e_i + \tau(\mathrm{letzte\ Position}_i, \mathrm{erste\ Position}_j)")
    st.latex(r"L:\ f_j = y_j,\ a_j \ge y_j + S + d_j,\ e_j = a_j + H \qquad D:\ f_j = a_j \ge \mathrm{tk}_j,\ y_j \ge a_j + H + d_j,\ e_j = y_j + S")
    st.latex(r"y_j \ge y_i + S\ \ ((i,j)\in\mathcal D),\qquad a_q \ge a_p + H\ \ ((p,q)\ \text{Kranreihenfolge}),\qquad T^K_j \ge a_j - \mathrm{tk}_j,\ T^Y_j \ge y_j - \mathrm{ty}_j,\ T \ge 0")
    st.latex(r"x_{jk},\ z^k_{ij} \in \{0,1\},\qquad f_j, a_j, y_j, e_j, T^K_j, T^Y_j \ge 0")
    st.markdown(
        "Der Index $0$ steht für den Standort des SC, am Anfang und am Ende der Rundreise. Die Bedingungen zu den Zeiten schließen Teiltouren aus, weil jeder Auftrag mindestens $H + S + d_j > 0$ dauert. **Parallel:** je Pool dasselbe Modell nur über die Aufträge und SC des Pools "
        "und ohne die Bedingungen $(i,j) \\in \\mathcal D$ zu anderen Pools; danach werden die Zeiten des zusammengesetzten Plans mit allen Bedingungen neu gerechnet. Eine Runde setzt für Aufträge mit fremdem Blocker $y_j \\ge$ Ende der Blocker-Operation laut erstem Plan."
    )

with st.expander("🚧 Wo die Annahmen enden"):
    st.markdown(
        "- **Erzeugte Instanzen:** Aufträge, Stellplätze und Stapelpaare stammen aus einem Zufallsgenerator (Zufalls-Seed), nicht aus einem Terminal. Alle Zahlen gelten für diese Instanzen.\n"
        "- **Terminal:** Kai oben, Yard-Blöcke darunter, Manhattan-Wege mit 6 m/s, Operation 15 s, Übergabe 20 s; keine Einbahnregeln, keine Staus.\n"
        "- **Richtzeiten:** am Kran 120 s + 75 s je Position in der Kranreihenfolge; am Yard aus der nominalen Fahrt abgeleitet. Die Richtzeiten sind Daten: ein Kran wartet nicht auf einen SC und verschiebt keine späteren Richtzeiten.\n"
        "- **Kranreihenfolge:** Übergaben an einem Kran in der Reihenfolge der Positionen mit mindestens 20 s Abstand.\n"
        "- **Laden vor der Richtzeit:** Ein Ladeauftrag darf früher als seine Richtzeit am Kran sein (der SC wartet dann am Kran); das kostet nichts, Verspätung zählt nur nach der Richtzeit. Beim Löschen übernimmt der SC den Container frühestens zur Richtzeit.\n"
        "- **Abhängigkeiten:** nur zwischen Aufträgen gleicher Art an verschiedenen Kränen; ein Blocker darf vorgezogen werden (der SC wartet dann am Yard). Umstapeln gibt es nicht.\n"
        "- **Gewichte:** Verspätung am Kran, am Yard und Strafe je poolfremdem Auftrag sind Annahmen der Demo; die Rangfolge der Verfahren kann daran hängen.\n"
        "- **Keine Störungen:** keine Fahrzeitstreuung, keine Ausfälle.\n"
        "- **Rechnen:** Die Gesamtmodelle laufen mit 2 CP-SAT-Prozessen und dem eingestellten Zeitlimit; Ergebnisse ohne Beweis können sich zwischen Läufen und Rechnern unterscheiden.\n"
        "- **Gleich gute Pläne:** Auch bewiesene Pool-Modelle haben oft mehrere gleich gute Lösungen. Die parallelen Verfahren hängen davon ab, welche davon der Löser liefert; ein anderer Zufalls-Seed des Lösers kann ihren Zielwert ändern (siehe README, „Wiederholbarkeit“)."
    )

st.markdown("---")
st.caption(FOOTER)
