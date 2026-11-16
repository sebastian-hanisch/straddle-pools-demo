"""Plotly-Figuren (alle Achsen fest, `fixedrange`): Plan als Gantt, Kopplungskarte der Kräne, Vergleich der Verfahren."""

import plotly.graph_objects as go

import stp_constants as C
import stp_pools as PL
import stp_terminal as T


def _fix(fig, height):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    fig.update_layout(height=height, margin=dict(l=70, r=20, t=40, b=45), legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    return fig


def time_axis_end(*methods, inst=None) -> int:
    """Gemeinsames Zeitende der Gantt-Diagramme, auf volle 100 s aufgerundet."""
    end = max(max(t.e for t in m.times) for m in methods)
    return int(-(-end // 100) * 100)


def plan_gantt(inst, pools, method, tk, ty, t_end: int | None = None, title: str = ""):
    """Eine Zeile je SC; Balken = Auftrag von Beginn der ersten Operation bis Freiwerden des SC (Wartezeiten eingeschlossen), nach Kran gefärbt.
    Dunkle Raute = Richtzeit am Kran, rote Linie = Verspätung am Kran, gestrichelte Linien = Abhängigkeiten (orange: zwischen Pools)."""
    times = method.times
    n_sc = pools.n_sc
    fig = go.Figure()
    rows = [f"SC {k + 1} (Pool {pools.sc_pool[k] + 1})" for k in range(n_sc)]
    for c in range(inst.n_cranes):
        xs, bases, ys, texts, hovers = [], [], [], [], []
        for k, route in enumerate(method.routes):
            for j in route:
                if inst.jobs[j].c != c:
                    continue
                t = times[j]
                xs.append(t.e - t.f)
                bases.append(t.f)
                ys.append(rows[k])
                texts.append(str(j + 1))
                hovers.append(f"Auftrag {j + 1} ({'Laden' if inst.jobs[j].kind == 'L' else 'Löschen'}, Kran {c + 1})<br>Kranübergabe ab {t.a} s (Richtzeit {tk[j]} s)<br>"
                              f"Stellplatz ab {t.y} s (Richtzeit {ty[j]} s)")
        fig.add_trace(go.Bar(orientation="h", x=xs, base=bases, y=ys, text=texts, textposition="inside", insidetextanchor="middle", hovertext=hovers,
                             hoverinfo="text", marker=dict(color=C.CRANE_COLORS[c % 4], line=dict(color=C.LINE_COLOR, width=0.5)), name=f"Kran {c + 1}"))
    lx, ly, mx, my = [], [], [], []
    for k, route in enumerate(method.routes):
        for j in route:
            t = times[j]
            mx.append(tk[j])
            my.append(rows[k])
            if t.a > tk[j]:
                lx += [tk[j], t.a, None]
                ly += [rows[k], rows[k], None]
    fig.add_trace(go.Scatter(x=mx, y=my, mode="markers", marker=dict(symbol="diamond", size=7, color="#333333"), name="Richtzeit am Kran", hoverinfo="skip"))
    if lx:
        fig.add_trace(go.Scatter(x=lx, y=ly, mode="lines", line=dict(color=C.LATE_COLOR, width=3), name="Verspätung am Kran", hoverinfo="skip"))
    for cross, color, name in ((False, C.LINE_COLOR, "Abhängigkeit (im Pool)"), (True, "#e08a00", "Abhängigkeit (zwischen Pools)")):
        dx, dy = [], []
        for job in inst.jobs:
            for p in job.preds:
                if (PL.pool_of_job(inst, pools, p) != PL.pool_of_job(inst, pools, job.id)) != cross:
                    continue
                dx += [times[p].y + T.SERVICE, times[job.id].y, None]
                dy += [rows[times[p].sc], rows[times[job.id].sc], None]
        if dx:
            fig.add_trace(go.Scatter(x=dx, y=dy, mode="lines", line=dict(color=color, width=1.5, dash="dot"), name=name, hoverinfo="skip"))
    fig.update_xaxes(title="Zeit (s)", range=[0, t_end or time_axis_end(method)])
    fig.update_yaxes(autorange="reversed", categoryorder="array", categoryarray=rows)
    fig.update_layout(barmode="overlay", title=dict(text=title, x=0, font=dict(size=14)))
    return _fix(fig, 90 + 46 * n_sc)


def coupling_map(inst, pools):
    """Kopplungskarte: Zahl der Abhängigkeiten zwischen je zwei Kränen, nach Pools geordnet; Rahmen = Pools. Außerhalb der Rahmen liegende Zahlen sind Abhängigkeiten zwischen Pools."""
    order = sorted(range(inst.n_cranes), key=lambda c: (pools.crane_pool[c], c))
    mat = PL.coupling(inst)
    z = [[mat[a][b] for b in order] for a in order]
    labels = [f"Kran {c + 1}" for c in order]
    fig = go.Figure(go.Heatmap(z=z, x=labels, y=labels, colorscale=[[0, "rgba(255,255,255,0)"], [1, "#2a6fb0"]], zmin=0, zmax=max(1, max(max(r) for r in z)),
                               texttemplate="%{z}", showscale=False, hovertemplate="%{y} und %{x}: %{z} Abhängigkeiten<extra></extra>", xgap=2, ygap=2))
    pos = 0
    for p in range(pools.n_pools):
        n = len(pools.cranes_of(p))
        fig.add_shape(type="rect", x0=pos - 0.5, x1=pos + n - 0.5, y0=pos - 0.5, y1=pos + n - 0.5, line=dict(color="#e08a00", width=3))
        pos += n
    fig.update_yaxes(autorange="reversed")
    return _fix(fig, 300)


def comparison_bars(a):
    """Zielwert je Verfahren (kleiner ist besser); ein Stern markiert Pläne ohne Optimalitätsbeweis (das Listenverfahren trägt keinen Stern: es ist keine Optimierung)."""
    keys = [k for k in C.METHOD_KEYS if k in a.methods]
    vals = [a.methods[k].cost.obj for k in keys]
    texts = [f"{v:,.0f}".replace(",", ".") + ("" if (a.methods[k].proven or k == "list") else " *") for k, v in zip(keys, vals)]
    fig = go.Figure(go.Bar(x=[C.METHOD_SHORT[k] for k in keys], y=vals, marker_color=[C.METHOD_COLORS[k] for k in keys], text=texts, textposition="outside", cliponaxis=False,
                           hovertext=[C.METHOD_LABELS[k] for k in keys], hoverinfo="text"))
    fig.update_yaxes(title="Zielwert (kleiner ist besser)", rangemode="tozero")
    fig.update_layout(showlegend=False)
    return _fix(fig, C.CHART_HEIGHT)
