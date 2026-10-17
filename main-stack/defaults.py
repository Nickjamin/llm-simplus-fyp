from typing import Dict

# Ported directly from SimplusGT RearrangeListApparatus.m (AC apparatuses only)
AC_DEFAULT_PARA: Dict[int, Dict[str, float]] = {
    0: {"J": 3.5, "D": 1.0, "wL": 0.05, "R": 0.01},
    10: {"V_dc": 2.5, "C_dc": 1.25, "f_v_dc": 5.0, "wLf": 0.03, "R": 0.01, "f_pll": 5.0, "f_tau_pll": 300.0, "f_i_dq": 600.0},
    20: {"wLf": 0.05, "Rf": 0.01, "wCf": 0.02, "wLc": 0.01, "Rc": 0.002, "Xov": 0.01, "Dw": 0.05, "fdroop": 5.0, "fvdq": 300.0, "fidq": 600.0},
    30: {"wLf": 0.05, "Rf": 0.01, "wCf": 0.02, "wLc": 0.01, "Rc": 0.002, "Xov": 0.01, "Dw": 0.05, "fdroop": 5.0, "fvdq": 300.0, "fidq": 600.0, "L_dc": 0.000125, "C_dc": 0.224, "v_ocv": 0.625, "R_bat": 0.0625, "v_dc_ref": 1.0, "fvdc": 50.0, "fibat": 500.0},
    40: {"wLf": 0.05, "Rf": 0.01, "wCf": 0.02, "wLc": 0.01, "Rc": 0.002, "Xov": 0.01, "N": 1.0, "R": 0.05, "fvdq": 300.0, "fidq": 600.0, "Sair": 1000.0, "Tair": 25.0, "C_dc": 1.0, "v_pv_ref": 0.8, "v_dc_ref": 1.0, "fvdc": 100.0, "fidc": 500.0},
    41: {"wLf": 0.05, "Rf": 0.01, "wCf": 0.02, "wLc": 0.01, "Rc": 0.002, "Xov": 0.01, "fvdc": 250.0, "fpll": 15.0, "fidq": 600.0, "C_dc": 1.0, "Sair": 1000.0, "Tair": 25.0, "v_pv_ref": 0.8, "v_dc_ref": 1.0, "fvpv": 100.0, "fidc": 500.0},
    50: {"wLf": 0.05, "Rf": 0.01, "wCf": 0.02, "wLc": 0.01, "Rc": 0.002, "Xov": 0.0, "Dw": 0.05, "f_droop": 5.0, "f_v_dq": 300.0, "f_i_dq": 600.0, "v_dc_r": 2.5, "C_dc": 0.01, "v_wpu": 1.0, "n_r": 20.0, "f_v_dc": 20.0, "f_i_sdq": 500.0, "f_w_m": 2.0},
    51: {"v_dc_r": 2.5, "C_dc": 0.01, "wLf": 0.05, "Rf": 0.0, "f_v_dc": 10.0, "f_pll": 10.0, "f_tau_pll": 300.0, "f_i_dq": 250.0, "v_wpu": 0.85, "n_r": 20.0, "f_i_sdq": 500.0, "f_w_m": 5.0},
    60: {
        "X": 0.15, "R": 0.0043, "Xd": 1.67, "Xd1": 0.265, "Xd2": 0.205, "Td1": 0.587, "Td2": 0.025,
        "Xq": 1.6, "Xq1": 0.46, "Xq2": 0.205, "Tq1": 0.135, "Tq2": 0.027, "H": 2.656, "D": 1.0,
        "TR": 1.0, "KA": 50.0, "TA": 0.06, "VRmax": 1.0, "VRmin": -1.0, "KE": -0.047, "TE": 0.52,
        "E1": 3.24, "SE1": 0.072, "E2": 4.32, "SE2": 0.282, "KF": 0.083, "TF": 1.0, "KP": 0.083,
        "KI": 1.0, "KD": 0.083, "TD": 1.0, "KPSS": 0.0, "TW": 10.0, "T11": 5.0, "T12": 0.6,
        "T21": 3.0, "T22": 0.5, "T31": 3.0, "T32": 0.5, "VSSmax": 0.2, "VSSmin": -0.2,
        "Rgov": 0.011, "T1gov": 0.1, "T2gov": 0.1, "T3gov": 0.3, "Dtgov": 0.25
    },
    90: {},
    100: {}
}

def get_base_type_key(app_type: int) -> int:
    """Maps subtype integers (e.g., 61-65) to their base parameter dictionary key."""
    if app_type in (0, 1):
        return 0
    if app_type in (10, 11, 12):
        return 10
    if 60 <= app_type <= 65:
        return 60
    return app_type