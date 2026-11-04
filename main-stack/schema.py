import math
from typing import Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, model_validator
from defaults import AC_DEFAULT_PARA, get_base_type_key
from collections import deque

class BasicSettings(BaseModel):
    Fs: int = Field(default=25000, description="Sampling frequency in Hz")
    Fbase: float = Field(default=50.0, description="Base grid frequency in Hz")
    Sbase: float = Field(default=1.0, description="Base apparent power in VA")
    Vbase: float = Field(default=1.0, description="Base voltage in V")

class AdvanceSettings(BaseModel):
    DiscretizationMethod: Literal[1, 2, 3] = Field(default=2, description="1: Forward Euler, 2: Backward Euler, 3: Tustin")
    LinearizationTimes: int = Field(default=1, ge=1)
    DiscretizationDampingFlag: Literal[0, 1] = 1
    DirectFeedthrough: Literal[0, 1] = 0
    PowerFlowAlgorithm: Literal[1, 2] = Field(default=1, description="1: Gauss-Seidel, 2: Newton-Raphson")
    EnableCreateSimulinkModel: Literal[0, 1] = 0
    EnablePlotPole: Literal[0, 1] = 0
    EnablePlotAdmittance: Literal[0, 1] = 0
    EnablePrintOutput: Literal[0, 1] = 1

class BusItem(BaseModel):
    BusNo: int = Field(ge=1, description="Sequential bus number starting at 1")
    BusType: Literal[1, 2, 3] = Field(description="1: Slack (Bus 1 ONLY), 2: PV, 3: PQ")
    Voltage: float = Field(default=1.0, gt=0)
    Theta: float = Field(default=0.0)
    PGi: float = Field(default=0.0, description="Active power generation in p.u.")
    QGi: float = Field(default=0.0, description="Reactive power generation in p.u.")
    PLi: float = Field(default=0.0, description="Active power load in p.u.")
    QLi: float = Field(default=0.0, description="Reactive power load in p.u.")
    Qmin: float = Field(default=-999.0)
    Qmax: float = Field(default=999.0)
    AreaNo: Literal[1] = 1
    AcDc: Literal[1] = 1

class NetworkLineItem(BaseModel):
    FromBus: int = Field(ge=1, description="Sending bus. Equal to ToBus for shunt loads.")
    ToBus: int = Field(ge=1, description="Receiving bus.")
    R: Union[float, Literal["NaN"]] = Field(default=0.01, description="Series R in p.u. Must be 'NaN' if FromBus == ToBus.")
    wL: Union[float, Literal["NaN"]] = Field(default=0.3, description="Series wL in p.u. Must be 'NaN' if FromBus == ToBus.")
    wC: float = Field(default=0.0, ge=0.0, description="Shunt wC in p.u.")
    G: float = Field(default=0.0, ge=0.0, description="Shunt G in p.u.")
    TurnsRatio: float = Field(default=1.0, gt=0.0)

    @model_validator(mode="after")
    def validate_branch_physics(self) -> "NetworkLineItem":
        if self.FromBus == self.ToBus:
            if self.R not in ("NaN", 0):
                raise ValueError(f"Self-branch on Bus {self.FromBus} must have R='NaN' or 0.")
            if self.wL not in ("NaN", 0):
                raise ValueError(f"Self-branch on Bus {self.FromBus} must have wL='NaN' or 0.")
            if self.wC == 0 and self.G == 0:
                raise ValueError(f"Self-branch on Bus {self.FromBus} is open-circuit (wC=0 and G=0).")
        else:
            if self.R == "NaN" or self.wL == "NaN":
                raise ValueError(f"Line {self.FromBus}-{self.ToBus} cannot have 'NaN' series R or wL.")
            if self.R < 0 or self.wL < 0:
                raise ValueError("Line R and wL must be non-negative.")
            
            # New: Minimum Impedance Magnitude Check for Y-Bus Stability
            z_mag = math.hypot(float(self.R), float(self.wL))
            if z_mag < 1e-4:
                raise ValueError(
                    f"Line {self.FromBus}-{self.ToBus} series impedance is too low (R={self.R}, wL={self.wL}). "
                    f"Magnitude {z_mag:.1e} will cause a singular Y-bus matrix. Increase R or wL."
                )
        return self

AllowedAcApparatusTypes = Literal[
    0, 1, 10, 11, 12, 20, 30, 40, 41, 50, 51, 60, 61, 62, 63, 64, 65, 90, 100
]

class LLMApparatusItem(BaseModel):
    BusNo: int = Field(ge=1)
    Type: AllowedAcApparatusTypes = Field(
        description="0:SyncGen, 10:GFL, 20:GFM, 30:BESS, 40:PV-GFM, 41:PV-GFL, 50:Wind-GFM, 51:Wind-GFL, 60-65:FullSyncGen, 90:InfBus, 100:FloatingBus"
    )
    ParaOverrides: Optional[Dict[str, float]] = Field(
        default=None,
        description="Optional parameter overrides (e.g., {'J': 5.0}). Leave null for standard defaults."
    )

    @model_validator(mode="after")
    def validate_override_keys(self) -> "LLMApparatusItem":
        if self.ParaOverrides:
            base_key = get_base_type_key(self.Type)
            valid_keys = set(AC_DEFAULT_PARA[base_key].keys())
            invalid = set(self.ParaOverrides.keys()) - valid_keys
            if invalid:
                raise ValueError(
                    f"Invalid parameter override(s) {invalid} for Type {self.Type}. Allowed: {sorted(valid_keys)}"
                )
        return self

class SimplusGTModelLLM(BaseModel):
    Basic: BasicSettings = Field(default_factory=BasicSettings)
    Advance: AdvanceSettings = Field(default_factory=AdvanceSettings)
    Bus: List[BusItem]
    NetworkLine: List[NetworkLineItem]
    Apparatus: List[LLMApparatusItem]

    @model_validator(mode="after")
    def validate_system_topology(self) -> "SimplusGTModelLLM":
        bus_nos = sorted([b.BusNo for b in self.Bus])
        expected_nos = list(range(1, len(self.Bus) + 1))
        if bus_nos != expected_nos:
            raise ValueError(f"BusNo must be sequential starting from 1. Got {bus_nos}.")

        slack_buses = [b.BusNo for b in self.Bus if b.BusType == 1]
        if slack_buses != [1]:
            raise ValueError(f"Bus 1 (and only Bus 1) must be Slack (BusType=1). Found: {slack_buses}")

        app_bus_nos = [a.BusNo for a in self.Apparatus]
        if len(app_bus_nos) != len(set(app_bus_nos)):
            raise ValueError("Multiple apparatuses assigned to the same BusNo.")
        
        for b_no in app_bus_nos:
            if b_no not in expected_nos:
                raise ValueError(f"Apparatus connected to non-existent BusNo {b_no}.")

        return self

    @model_validator(mode="after")
    def validate_network_connectivity(self) -> "SimplusGTModelLLM":
        bus_nos = {b.BusNo for b in self.Bus}
        
        # 1. Dangling Lines Check: Ensure all lines connect to actual buses
        for idx, line in enumerate(self.NetworkLine):
            if line.FromBus not in bus_nos:
                raise ValueError(f"NetworkLine branch references non-existent FromBus {line.FromBus}.")
            if line.ToBus not in bus_nos:
                raise ValueError(f"NetworkLine branch references non-existent ToBus {line.ToBus}.")

        # 2. Electrical Island Check: Ensure the grid is a single connected component
        if not bus_nos:
            return self
            
        adj = {b: set() for b in bus_nos}
        for line in self.NetworkLine:
            if line.FromBus != line.ToBus:  # Ignore shunt self-branches
                adj[line.FromBus].add(line.ToBus)
                adj[line.ToBus].add(line.FromBus)
        
        visited = set()
        queue = deque([next(iter(bus_nos))])
        
        while queue:
            curr = queue.popleft()
            if curr not in visited:
                visited.add(curr)
                queue.extend(adj[curr] - visited)
                
        unvisited = bus_nos - visited
        if unvisited:
            raise ValueError(
                f"Grid topology is disconnected. Isolated buses found: {sorted(unvisited)}. "
                "SimplusGT power flow requires a single connected electrical island."
            )
                             
        return self

    @model_validator(mode="after")
    def validate_dynamic_elements(self) -> "SimplusGTModelLLM":
        # Types 90 (Infinite Bus) and 100 (Floating Bus) do not provide dynamic states
        dynamic_types = {0, 10, 11, 12, 20, 30, 40, 41, 50, 51, 60, 61, 62, 63, 64, 65}
        
        has_dynamic = any(app.Type in dynamic_types for app in self.Apparatus)
        if not has_dynamic:
            raise ValueError(
                "The grid contains no dynamic components. You must include at least one "
                "generator or inverter (e.g., Type 0, 10, 20) to construct the state-space model."
            )
        return self