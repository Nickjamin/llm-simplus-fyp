### Level 1: Trivial Baseline (Basic Validation)

**Goal:** Verify the LLM can generate the absolute minimum required JSON without syntax errors or hallucinating unnecessary fields.

- **Prompt A (Radial Pair):** "Create a simple 2-bus radial AC network. Connect Bus 1 to Bus 2 with a single network line. Place a synchronous generator on Bus 1 and a shunt load on Bus 2."
    
- **What it tests:**
    
    - Sequential bus numbering (1, 2).
        
    - Correct assignment of Bus 1 as the Slack Bus (BusType: 1).
        
    - Correct formulation of a shunt load as a self-branch (FromBus=2, ToBus=2) with `R="NaN"`.
        

### Level 2: Intermediate (Mixed Apparatuses & Topology)

**Goal:** Evaluate the LLM's ability to map standard industry terminology to the correct SimplusGT internal apparatus integers (e.g., Type 10, 20, 30).

- **Prompt B (Microgrid):** "Design a 5-bus AC grid. Bus 1 is the slack bus with an infinite bus connection. Buses 2, 3, and 4 form a ring network. Bus 5 is connected radially to Bus 4. Place a Grid-Forming (GFM) inverter on Bus 2, a Grid-Following (GFL) inverter on Bus 4, and battery energy storage (BESS) on Bus 5. Add shunt loads on buses 3 and 5."
    
- **What it tests:**
    
    - Mapping "infinite bus" to Type 90, "GFM" to 20, "GFL" to 10, and "BESS" to 30.
        
    - Generating a mix of standard lines and self-branch loads across a hybrid ring/radial topology.
        

### Level 3: Advanced (Parameter Overrides & Physics)

**Goal:** Test the LLM's capacity to modify the `ParaOverrides` dictionary using the exact keys required by the `AC_DEFAULT_PARA` dictionary without hallucinating variable names.

- **Prompt C (Tuned Inverters):** "Generate a 3-bus AC system connected sequentially. Bus 1 has a standard synchronous generator. Bus 2 has a PV-GFM inverter, but override its nominal DC link capacitor (C_dc) to 1.5 and its filter resistance (Rf) to 0.02. Bus 3 is just a shunt load. Make the line between Bus 1 and 2 very long by setting its series R to 0.05 and wL to 0.8."
    
- **What it tests:**
    
    - Populating `ParaOverrides` with `{"C_dc": 1.5, "Rf": 0.02}` for a Type 40 apparatus.
        
    - Modifying specific `NetworkLineItem` attributes (`R` and `wL`) instead of relying on default line values.
        

### Level 4: Adversarial (Guardrails & Scope Enforcement)

**Goal:** Stress-test the prompt boundaries. The LLM must navigate out-of-order instructions, missing data, and out-of-scope requests without breaking the Pydantic structural validation.

- **Prompt D (Ambiguous/Out-of-Scope):** "I need a 4-bus power system. Put a load on Bus 4 and a GFL inverter on Bus 2. Make sure the main grid connection is on Bus 1. Also, connect 1 to 2, 2 to 3, and 3 to 4. Leave Bus 3 empty. Finally, add a DC microgrid attached to Bus 4."
    
- **What it tests:**
    
    - **Scope rejection:** The project explicitly excludes DC grids. The LLM should ignore the DC microgrid request entirely rather than hallucinating an invalid apparatus type.
        
    - **Implicit defaults:** The LLM must recognize that Bus 3 is "empty" and let your `compiler.py` auto-fill it as a Type 100 Floating Bus.
        
    - **Scattered logic:** The bus definitions are provided out of order, forcing the LLM to sort them sequentially starting from 1.