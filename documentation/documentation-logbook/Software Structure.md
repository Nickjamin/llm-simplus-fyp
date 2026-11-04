
**full-stack** /
├── config.py       # LLM providers, model IDs, and system prompt builder
├── defaults.py     # AC_DEFAULT_PARA dictionary (ported from MATLAB)
├── schema.py       # Pure Pydantic models and topology/physics validators
├── compiler.py     # Post-processor: expands LLM output into SimplusGT
├── logger.py     # updates eval_results folder including a results.csv
├── matlab-bridge.py     # headless matlab execution of UserMain.m from simplusGT
└── main.py         # CLI entry point, OpenAI client execution, and error logging

