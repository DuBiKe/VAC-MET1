"""Modello fisiologico dimostrativo per l'app VAC-MET.

Tutti i coefficienti degli effetti terapeutici sono IPOTETICI e hanno solo
scopo dimostrativo/didattico (ipotesi del protocollo VAC-MET).
Non rappresentano dati sperimentali e non sono per uso clinico.

Formule principali (coerenti con il protocollo VAC-MET):
- Ea = 0,9 x PAS / SV            (elastanza arteriosa efficace)
- VAC = Ea / Ees                 (accoppiamento ventricolo-arterioso)
- GC = SV x FC / 1000            (gittata cardiaca, L/min)
- CaO2 = 1,34 x Hb x SaO2/100 + 0,003 x PaO2
- DO2 = GC x CaO2 x 10           (mL/min)
- VCO2 = RQ x VO2 + componente anaerobica se DO2 < DO2crit (= VO2 / OERmax)
"""

from dataclasses import dataclass, replace

OER_MAX_DEFAULT = 0.60   # massimo rapporto di estrazione di O2 (VO2/DO2 critico)
K_ANA_DEFAULT = 0.5      # coefficiente della componente anaerobica di VCO2
PPV_THRESHOLD = 12.0     # soglia di fluid responsiveness (%)


@dataclass
class Determinants:
    """Determinanti fisiologici dello stato emodinamico-metabolico."""
    ees: float   # elastanza telesistolica VS (mmHg/mL) — contrattilita'
    ea: float    # elastanza arteriosa efficace (mmHg/mL) — postcarico
    sv: float    # gittata sistolica (mL)
    hr: float    # frequenza cardiaca (bpm)
    hb: float    # emoglobina (g/dL)
    sao2: float  # saturazione arteriosa (%)
    pao2: float  # pressione parziale O2 arteriosa (mmHg)
    vo2: float   # consumo di O2 (mL/min)
    rq: float    # quoziente respiratorio (VCO2/VO2)


def compute_state(det: Determinants, oer_max: float = OER_MAX_DEFAULT,
                  k_ana: float = K_ANA_DEFAULT) -> dict:
    """Calcola VAC, DO2, VCO2 e il rapporto VCO2/DO2 dai determinanti."""
    vac = det.ea / det.ees
    pas = det.ea * det.sv / 0.9                      # PAS implicita (per display)
    co = det.sv * det.hr / 1000.0                    # L/min
    cao2 = 1.34 * det.hb * det.sao2 / 100.0 + 0.003 * det.pao2
    do2 = co * cao2 * 10.0                           # mL/min
    do2crit = det.vo2 / oer_max
    vco2_aer = det.rq * det.vo2
    vco2_ana = k_ana * max(0.0, do2crit - do2)
    vco2 = vco2_aer + vco2_ana
    ratio = vco2 / do2 if do2 > 0 else float("nan")
    return dict(ea=det.ea, ees=det.ees, vac=vac, pas=pas, sv=det.sv, hr=det.hr,
                co=co, cao2=cao2, do2=do2, do2crit=do2crit, vo2=det.vo2,
                vco2_aer=vco2_aer, vco2_ana=vco2_ana, vco2=vco2, ratio=ratio,
                anaerobic=do2 < do2crit)


def apply_therapies(det: Determinants, ppv: float, fluids_ml: float = 0.0,
                    ne_dose: float = 0.0, dobu_dose: float = 0.0,
                    cNE_Ea: float = 1.0, cNE_Ees: float = 0.25,
                    cD_Ees: float = 0.12, cD_Ea: float = 0.015):
    """Applica fluidi, noradrenalina e dobutamina modificando i determinanti.

    Restituisce (nuovi_determinanti, responder). Coefficienti ipotetici.
    """
    ea, ees, sv, hr = det.ea, det.ees, det.sv, det.hr
    responder = ppv >= PPV_THRESHOLD

    # Fluidi: effetto sulla gittata solo nei responder (PPV >= 12%);
    # nei responder Ea si riduce lievemente (rilascio del tono simpatico riflesso).
    if fluids_ml > 0:
        if responder:
            sv *= 1 + min(0.30, 0.08 * fluids_ml / 250.0)
            ea *= 1 - 0.05 * fluids_ml / 500.0
        else:
            sv *= 1 + min(0.05, 0.01 * fluids_ml / 250.0)

    # Noradrenalina: Ea aumenta (alfa-1) piu' di Ees (beta-1);
    # nei responder recluta anche precarico (costrizione venosa).
    if ne_dose > 0:
        ea *= 1 + cNE_Ea * ne_dose
        ees *= 1 + cNE_Ees * ne_dose
        if responder:
            sv *= 1 + min(0.15, 0.5 * ne_dose)

    # Dobutamina: Ees aumenta marcatamente (beta-1), Ea si riduce lievemente
    # (beta-2 vascolare); aumentano gittata e frequenza.
    if dobu_dose > 0:
        ees *= 1 + cD_Ees * dobu_dose
        ea *= max(0.05, 1 - cD_Ea * dobu_dose)
        sv *= 1 + min(0.50, 0.04 * dobu_dose)
        hr *= 1 + min(0.30, 0.015 * dobu_dose)

    return replace(det, ea=ea, ees=ees, sv=sv, hr=hr), responder


def u_curve(vac_values, anchor_vac: float, anchor_ratio: float, amp: float = 1.0):
    """Curva a U ipotizzata y = y_min x (1 + amp x (VAC-1)^2).

    La curva e' ancorata allo stato basale del paziente: passa esattamente
    per il punto (anchor_vac, anchor_ratio). Restituisce (y, y_min).
    """
    y_min = anchor_ratio / (1.0 + amp * (anchor_vac - 1.0) ** 2)
    return y_min * (1.0 + amp * (vac_values - 1.0) ** 2), y_min


def free_mode_shift(vac: float, ratio: float, ppv: float, fluids_ml: float,
                    ne_dose: float, dobu_dose: float):
    """Modalita' libera: spostamenti predefiniti (dichiarati) del punto.

    - Fluidi (se responder): VAC si avvicina a 1 di 0,15; rapporto -10%.
    - Noradrenalina oltre 0,5 ug/kg/min: VAC +0,1 per ogni step di 0,3;
      rapporto +5% per step.
    - Dobutamina (solo se VAC > 1,2): VAC -0,2 per 10 ug/kg/min (fino a 1);
      rapporto -8% per 10 ug/kg/min.
    """
    vac1, r1 = vac, ratio
    responder = ppv >= PPV_THRESHOLD
    if fluids_ml > 0 and responder:
        vac1 += min(0.15, abs(1 - vac1)) * (1 if vac1 < 1 else -1)
        r1 *= 0.90
    if ne_dose > 0.5:
        steps = (ne_dose - 0.5) / 0.3
        vac1 += 0.1 * steps
        r1 *= 1 + 0.05 * steps
    if dobu_dose > 0 and vac1 > 1.2:
        vac1 = max(1.0, vac1 - 0.2 * dobu_dose / 10.0)
        r1 *= 1 - 0.08 * dobu_dose / 10.0
    return vac1, r1, responder
