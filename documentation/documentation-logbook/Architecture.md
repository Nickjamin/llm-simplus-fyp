# Architecture & Domain Translation Spec: SimplusGT LLM Pipeline

This document outlines the critical translation rules between the Pydantic/LLM schema generation and the native SimplusGT `UserData.json` format. **Do not alter these without cross-referencing SimplusGT's MATLAB source.**

## 1. Grid Topology & Physics Rules

*   **Slack Bus Constraint:** Bus 1 (and *only* Bus 1) must be defined as the Slack Bus (`BusType: 1`). SimplusGT requires this rigidly.
*   **Sequential Numbering:** `BusNo` must be strictly sequential starting from 1. 
*   **Electrical Connectivity:** The grid must form a single, fully connected electrical island. `schema.py` enforces this via a Breadth-First Search (BFS) traversal of `NetworkLine` to catch disconnected sub-grids before passing them to the MATLAB engine solver. Multi-circuit parallel lines are permitted.

## 2. Component Mapping & Parameter Asymmetry

The LLM outputs a highly structured schema (`SimplusGTModelLLM`) that `compiler.py` flattens into the format `UserMain.m` expects.

*   **Implicit Floating Buses (Type 100):** To save LLM token output, the LLM is instructed to omit passive/empty AC buses from the `Apparatus` list. `compiler.py` automatically detects missing buses and populates them as AC Floating Buses (`Type: 100`). PV regulation nodes (like SVCs) are modeled as `Type: 100` buses with `PGi = 0`.
*   **Parameter Structure Asymmetry:** 
    *   Standard active apparatuses (Types 0, 10, 20, 30, 40, 50) expect a parameter dictionary. `compiler.py` maps the user overrides against `AC_DEFAULT_PARA` and injects the `w0` (angular frequency) key based on `Fbase`.
    *   Infinite Buses (`Type: 90`) and Floating Buses (`Type: 100`) strictly require an empty array (`[]`) for their `Para` field, not an empty dictionary (`{}`). `compiler.py` handles this formatting override.

## 3. Shunt Representation

SimplusGT represents shunt capacitors, inductors, and loads natively within the `NetworkLine` array rather than as standalone apparatuses.
*   **Self-Branching:** Shunts are defined as transmission lines where `FromBus == ToBus`.
*   **NaN Overrides:** For self-branches, the series resistance (`R`) and series inductive reactance (`wL`) must explicitly be set to the string `"NaN"`.
*   **Open-Circuit Prevention:** A self-branch must possess a non-zero `wC` (susceptance) or `G` (conductance) value; otherwise, it is electrically meaningless and will be rejected by the Pydantic validator.

## 4. Execution Bridge (`matlab_bridge.py`)

*   **Headless Execution:** The pipeline runs `UserMain.m` without the MATLAB desktop UI (`-nodesktop -nosplash`). 
*   **Persistent Engine:** To eliminate the 10-15 second cold-start penalty during batch testing, the MATLAB engine is instantiated once at the start of a batch run. State bleed between iterations is prevented by passing `clear all; close all;` to the workspace before executing `UserMain.m`.
*   **Stability Detection:** A completely successful run evaluates both syntax execution and small-signal stability. The bridge intercepts the native eigenvalue check and categorizes the run as `SOLVED` (stable) or `UNSTABLE` based on pole location.