import json
import math
from pathlib import Path
from defaults import AC_DEFAULT_PARA, get_base_type_key
from schema import SimplusGTModelLLM

def compile_to_simplus_dict(model: SimplusGTModelLLM) -> dict:
    """Expands a validated SimplusGTModelLLM instance into the full SimplusGT dictionary."""
    w0 = 2.0 * math.pi * model.Basic.Fbase
    sorted_buses = sorted(model.Bus, key=lambda x: x.BusNo)
    app_by_bus = {a.BusNo: a for a in model.Apparatus}

    compiled_apparatus = []
    for bus in sorted_buses:
        b_no = bus.BusNo
        if b_no in app_by_bus:
            app = app_by_bus[b_no]
            app_type = app.Type
            overrides = app.ParaOverrides or {}
        else:
            # Auto-fill omitted buses as Type 100 (AC Floating Bus)
            app_type = 100
            overrides = {}

        base_key = get_base_type_key(app_type)
        para_dict = dict(AC_DEFAULT_PARA[base_key])
        para_dict.update(overrides)

        if base_key in (0, 10, 20, 30, 40, 41, 50, 51):
            para_dict["w0"] = w0

        final_para = [] if base_key in (90, 100) else para_dict

        compiled_apparatus.append({
            "BusNo": b_no,
            "Type": app_type,
            "Para": final_para
        })

    return {
        "Basic": model.Basic.model_dump(),
        "Advance": model.Advance.model_dump(),
        "Bus": [b.model_dump() for b in sorted_buses],
        "NetworkLine": [line.model_dump() for line in model.NetworkLine],
        "NetworkLineIEEE": [],
        "Apparatus": compiled_apparatus
    }

def save_simplus_json(model: SimplusGTModelLLM, filepath: str | Path = "UserData.json") -> str:
    """Compiles the model and writes it to disk for MATLAB consumption."""
    data = compile_to_simplus_dict(model)
    json_str = json.dumps(data, indent=2)
    Path(filepath).write_text(json_str, encoding="utf-8")
    return json_str