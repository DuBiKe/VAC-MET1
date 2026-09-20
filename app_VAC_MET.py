# app_VAC_MET.py
# App interattiva di dimostrazione dell'ipotesi del protocollo VAC-MET:
# relazione tra accoppiamento ventricolo-arterioso (VAC = Ea/Ees, asse x)
# e rapporto VCO2/DO2 (asse y), con effetti ipotetici di fluidi,
# noradrenalina e dobutamina.
#
# Avvio:  pip install streamlit plotly
#         streamlit run app_VAC_MET.py
#
# ATTENZIONE: modello dimostrativo con coefficienti IPOTETICI.
# Non rappresenta dati sperimentali. Non per uso clinico.

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from vac_met_model import (Determinants, apply_therapies, compute_state,
                           free_mode_shift, u_curve, PPV_THRESHOLD)

st.set_page_config(page_title="VAC-MET — Dimostrazione ipotesi", layout="wide")

st.title("VAC-MET — Relazione tra VAC e rapporto VCO\u2082/DO\u2082")
st.caption(
    "Dimostrazione interattiva dell'ipotesi del protocollo VAC-MET: "
    "relazione a U tra accoppiamento ventricolo-arterioso (Ea/Ees) ed "
    "efficienza metabolica (VCO\u2082/DO\u2082), con nadir atteso a VAC \u2248 1. "
    "Modello semplificato con coefficienti ipotetici — **non per uso clinico**."
)

# ----------------------------- Sidebar -----------------------------------
st.sidebar.header("Impostazioni")
modalita = st.sidebar.radio(
    "Modalità",
    ["Fisiologica", "Libera"],
    index=0,
    help="Fisiologica: VAC e VCO\u2082/DO\u2082 sono calcolati dai determinanti. "
         "Libera: posiziona il punto direttamente con gli slider (scopo didattico).",
)

if modalita == "Fisiologica":
    with st.sidebar.expander("Determinanti meccanici", expanded=True):
        ees = st.slider("Ees — contrattilità (mmHg/mL)", 0.5, 4.0, 1.3, 0.1)
        pas = st.slider("PAS (mmHg)", 80, 180, 110, 5)
        sv = st.slider("Gittata sistolica SV (mL)", 30, 100, 60, 5)
        hr = st.slider("Frequenza cardiaca (bpm)", 40, 140, 95, 5)
    with st.sidebar.expander("Determinanti metabolici e ossigenazione"):
        hb = st.slider("Emoglobina (g/dL)", 6.0, 15.0, 9.0, 0.5)
        sao2 = st.slider("SaO\u2082 (%)", 80, 100, 96, 1)
        pao2 = st.slider("PaO\u2082 (mmHg)", 50, 300, 90, 10)
        vo2 = st.slider("VO\u2082 (mL/min)", 150, 350, 240, 10)
        rq = st.slider("Quoziente respiratorio (RQ)", 0.7, 1.2, 0.85, 0.05)
else:
    with st.sidebar.expander("Posizionamento libero del punto", expanded=True):
        vac_lib = st.slider("VAC (Ea/Ees)", 0.2, 2.5, 1.4, 0.05)
        ratio_lib = st.slider("VCO\u2082/DO\u2082", 0.05, 0.60, 0.30, 0.01)

with st.sidebar.expander("Fluid responsiveness", expanded=True):
    ppv = st.slider("PPV (%)", 0, 25, 14, 1,
                    help=f"Soglia di risposta ai fluidi: PPV \u2265 {PPV_THRESHOLD:.0f}%")

with st.sidebar.expander("Terapie", expanded=True):
    fluids_ml = st.slider("Fluidi somministrati (mL)", 0, 1000, 0, 250)
    ne_dose = st.slider("Noradrenalina (\u00b5g/kg/min)", 0.0, 2.0, 0.0, 0.05)
    dobu_dose = st.slider("Dobutamina (\u00b5g/kg/min)", 0, 20, 0, 1)

with st.sidebar.expander("Effetti avanzati (coefficienti ipotetici)"):
    amp = st.slider("Ampiezza della curva a U", 0.0, 3.0, 1.0, 0.1)
    if modalita == "Fisiologica":
        cNE_Ea = st.slider("NE \u2192 Ea (per \u00b5g/kg/min)", 0.0, 2.0, 1.0, 0.1)
        cNE_Ees = st.slider("NE \u2192 Ees (per \u00b5g/kg/min)", 0.0, 1.0, 0.25, 0.05)
        cD_Ees = st.slider("Dobutamina \u2192 Ees (per \u00b5g/kg/min)", 0.0, 0.30, 0.12, 0.01)
        cD_Ea = st.slider("Dobutamina \u2192 Ea (per \u00b5g/kg/min)", 0.0, 0.05, 0.015, 0.005)
        oer_max = st.slider("OERmax (estrazione O\u2082 critica)", 0.40, 0.80, 0.60, 0.05)
        k_ana = st.slider("Componente anaerobica VCO\u2082 (k)", 0.0, 2.0, 0.5, 0.1)

# ----------------------------- Calcoli -----------------------------------
if modalita == "Fisiologica":
    ea0 = 0.9 * pas / sv
    det0 = Determinants(ees=ees, ea=ea0, sv=sv, hr=hr, hb=hb,
                        sao2=sao2, pao2=pao2, vo2=vo2, rq=rq)
    s0 = compute_state(det0, oer_max, k_ana)
    det1, responder = apply_therapies(det0, ppv, fluids_ml, ne_dose, dobu_dose,
                                      cNE_Ea, cNE_Ees, cD_Ees, cD_Ea)
    s1 = compute_state(det1, oer_max, k_ana)
    x0, y0, x1, y1 = s0["vac"], s0["ratio"], s1["vac"], s1["ratio"]
else:
    x0, y0 = vac_lib, ratio_lib
    x1, y1, responder = free_mode_shift(x0, y0, ppv, fluids_ml, ne_dose, dobu_dose)
    s0 = s1 = None

terapia_attiva = (fluids_ml > 0) or (ne_dose > 0) or (dobu_dose > 0)

# ----------------------------- Grafico -----------------------------------
x = np.linspace(0.2, 2.5, 300)
curve_y, y_min = u_curve(x, x0, y0, amp)
y_top = max(float(curve_y.max()), y0, y1) * 1.15

fig = go.Figure()
# Zone di accoppiamento
fig.add_vrect(x0=0.2, x1=0.6, fillcolor="orange", opacity=0.08, line_width=0,
              annotation_text="VAC < 0,6", annotation_position="top left")
fig.add_vrect(x0=0.6, x1=1.2, fillcolor="green", opacity=0.08, line_width=0,
              annotation_text="Accoppiamento ottimale", annotation_position="top")
fig.add_vrect(x0=1.2, x1=2.5, fillcolor="red", opacity=0.08, line_width=0,
              annotation_text="Disaccoppiamento", annotation_position="top right")
# Curva a U ipotizzata
fig.add_trace(go.Scatter(x=x, y=curve_y, mode="lines", name="Curva ipotizzata",
                         line=dict(color="#0279EE", width=3)))
fig.add_vline(x=1.0, line_dash="dash", line_color="grey",
              annotation_text="Nadir (VAC = 1)", annotation_position="bottom right")
# Punto basale e post-terapia
fig.add_trace(go.Scatter(x=[x0], y=[y0], mode="markers", name="Stato basale",
                         marker=dict(color="#0279EE", size=16, symbol="circle")))
if terapia_attiva:
    fig.add_trace(go.Scatter(x=[x1], y=[y1], mode="markers", name="Post-terapia",
                             marker=dict(color="#FF9400", size=16, symbol="diamond")))
    fig.add_annotation(x=x1, y=y1, ax=x0, ay=y0, xref="x", yref="y",
                       axref="x", ayref="y", showarrow=True, arrowhead=3,
                       arrowsize=1.5, arrowwidth=2.5, arrowcolor="#FF9400")

fig.update_layout(
    xaxis_title="VAC (Ea/Ees)",
    yaxis_title="VCO\u2082/DO\u2082",
    xaxis=dict(range=[0.2, 2.5]),
    yaxis=dict(range=[0, y_top]),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    height=560, margin=dict(t=60),
    font=dict(family="Liberation Sans, Arial, sans-serif"),
)
st.plotly_chart(fig, use_container_width=True)
st.caption("La curva a U \u00e8 la relazione ipotizzata (da validare nello studio); "
           "\u00e8 ancorata allo stato basale del paziente a scopo dimostrativo.")

# ----------------------------- Metriche ----------------------------------
st.info(f"PPV = {ppv}% \u2192 paziente **{'RESPONDER' if responder else 'NON RESPONDER'}** "
        f"ai fluidi (soglia {PPV_THRESHOLD:.0f}%)")

if modalita == "Fisiologica":
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VAC (Ea/Ees)", f"{s1['vac']:.2f}",
              f"{s1['vac'] - s0['vac']:+.2f}" if terapia_attiva else None)
    c2.metric("VCO\u2082/DO\u2082", f"{s1['ratio']:.3f}",
              f"{s1['ratio'] - s0['ratio']:+.3f}" if terapia_attiva else None)
    c3.metric("DO\u2082 (mL/min)", f"{s1['do2']:.0f}",
              f"{s1['do2'] - s0['do2']:+.0f}" if terapia_attiva else None)
    c4.metric("Gittata cardiaca (L/min)", f"{s1['co']:.1f}",
              f"{s1['co'] - s0['co']:+.1f}" if terapia_attiva else None)

    if s1["anaerobic"]:
        st.warning(f"DO\u2082 ({s1['do2']:.0f} mL/min) < DO\u2082 critica "
                   f"({s1['do2crit']:.0f} mL/min): componente anaerobica del VCO\u2082 attiva.")

    with st.expander("Dettaglio dei calcoli (basale vs post-terapia)"):
        import pandas as pd
        righe = {
            "Ea (mmHg/mL)": (s0["ea"], s1["ea"]),
            "Ees (mmHg/mL)": (s0["ees"], s1["ees"]),
            "VAC (Ea/Ees)": (s0["vac"], s1["vac"]),
            "PAS implicita (mmHg)": (s0["pas"], s1["pas"]),
            "SV (mL)": (s0["sv"], s1["sv"]),
            "FC (bpm)": (s0["hr"], s1["hr"]),
            "Gittata cardiaca (L/min)": (s0["co"], s1["co"]),
            "CaO\u2082 (mL/dL)": (s0["cao2"], s1["cao2"]),
            "DO\u2082 (mL/min)": (s0["do2"], s1["do2"]),
            "DO\u2082 critica (mL/min)": (s0["do2crit"], s1["do2crit"]),
            "VCO\u2082 aerobico (mL/min)": (s0["vco2_aer"], s1["vco2_aer"]),
            "VCO\u2082 anaerobico (mL/min)": (s0["vco2_ana"], s1["vco2_ana"]),
            "VCO\u2082 totale (mL/min)": (s0["vco2"], s1["vco2"]),
            "VCO\u2082/DO\u2082": (s0["ratio"], s1["ratio"]),
        }
        df = pd.DataFrame(righe, index=["Basale", "Post-terapia"]).T.round(3)
        st.dataframe(df, use_container_width=True)
else:
    c1, c2 = st.columns(2)
    c1.metric("VAC (Ea/Ees)", f"{x1:.2f}",
              f"{x1 - x0:+.2f}" if terapia_attiva else None)
    c2.metric("VCO\u2082/DO\u2082", f"{y1:.3f}",
              f"{y1 - y0:+.3f}" if terapia_attiva else None)

# ------------------------- Interpretazione -------------------------------
if terapia_attiva:
    st.subheader("Interpretazione (ipotesi del protocollo)")
    d_nadir = abs(x1 - 1) - abs(x0 - 1)
    if d_nadir < -0.02:
        st.markdown("- Il punto si **avvicina al nadir** (VAC \u2192 1): l'efficienza meccanica migliora.")
    elif d_nadir > 0.02:
        st.markdown("- Il punto si **allontana dal nadir**: il VAC peggiora (disaccoppiamento meccanico).")
    else:
        st.markdown("- Il VAC resta **sostanzialmente invariato**.")
    dr = (y1 - y0) / y0 if y0 > 0 else 0.0
    if dr < -0.03:
        st.markdown("- Il rapporto VCO\u2082/DO\u2082 **diminuisce**: l'adeguatezza metabolica migliora "
                    "(risposta concordante attesa dall'ipotesi).")
    elif dr > 0.03:
        st.markdown("- Il rapporto VCO\u2082/DO\u2082 **aumenta**: possibile peggioramento del bilancio "
                    "offerta/domanda di O\u2082 (risposta concordante attesa dall'ipotesi).")
    else:
        st.markdown("- Il rapporto VCO\u2082/DO\u2082 resta **sostanzialmente invariato**.")

# ----------------------------- Note --------------------------------------
st.divider()
st.markdown(
    "**Modello e formule.** Ea = 0,9 \u00d7 PAS / SV; VAC = Ea/Ees "
    "(Ees stimabile al letto del paziente con il metodo single-beat di Chen); "
    "DO\u2082 = GC \u00d7 CaO\u2082 \u00d7 10; VCO\u2082 = RQ \u00d7 VO\u2082 + componente anaerobica "
    "se DO\u2082 < DO\u2082 critica (VO\u2082/OERmax). "
    "Gli effetti di fluidi (solo se PPV \u2265 12%), noradrenalina (Ea\u2191\u2191 > Ees\u2191) "
    "e dobutamina (Ees\u2191\u2191, Ea stabile o \u2193) sono **coefficienti ipotetici** "
    "calibrati qualitativamente sulla letteratura citata nel protocollo VAC-MET. "
    "Questa app dimostra un'ipotesi da validare sperimentalmente: "
    "**non \u00e8 uno strumento clinico**."
)
