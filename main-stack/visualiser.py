"""
================================================================================
SimplusGT Evaluation Results Visualizer (visualiser.py)
================================================================================

Description:
    Parses wide-format benchmark evaluation CSV files (such as `results.csv`
    produced by logger.py) and generates stacked-bar iteration diagnostic charts.
    
    Each horizontal position represents an evaluation test run (model and prompt).
    The vertical axis stacks unit blocks corresponding to each iteration attempt
    (Iterations 1 to 3). Block colors distinguish:
      - SUCCESS (STABLE): Power flow converged & small-signal stable.
      - UNSTABLE: Solved/linearized by MATLAB, but eigenvalues indicate instability.
      - Failures by stage: MATLAB, PYDANTIC, JSON_DECODE, TOKEN_LIMIT, API.

Command-line Arguments:
    -i, --input   Path to the results CSV file (default: eval_results/results.csv).
    -o, --output  Directory to save output plots (default: eval_results).
    -m, --model   Filter to a specific model key (default: all models).

Usage Examples:
    # 1. Run using defaults:
    $ python visualiser.py

    # 2. Filter visualization to a single model:
    $ python visualiser.py -m gemini-3.5-flash-lite

    # 3. Specify custom paths and model filter:
    $ python visualiser.py -i runs_backup/results.csv -o output_charts -m gpt-oss-120b
================================================================================
"""

import argparse
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        description="Visualize SimplusGT Evaluation Results with stability and stage diagnostics."
    )
    parser.add_argument(
        "-i", "--input", 
        type=str, 
        default="eval_results/results.csv", 
        help="Path to the results CSV file (default: eval_results/results.csv)"
    )
    parser.add_argument(
        "-o", "--output", 
        type=str, 
        default="eval_results", 
        help="Directory to save the generated plots (default: eval_results)"
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default=None,
        help="Filter results to a specific model_name"
    )
    parser.add_argument(
        "-n", "--max-iterations",
        type=int,
        default=None,
        help="Maximum iterations to plot (auto-detected from CSV if omitted)"
    )
    args = parser.parse_args()

    csv_path = Path(args.input)
    results_dir = Path(args.output)

    if not csv_path.exists():
        print(f"[ERROR] No data found at {csv_path}. Please check the path or run an evaluation first.")
        return

    results_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    if df.empty:
        print("[ERROR] CSV is empty.")
        return

    # Auto-detect max iterations if not explicitly passed via -n
    if args.max_iterations is not None:
        max_iters = args.max_iterations
    else:
        it_cols = [c for c in df.columns if c.startswith('it') and '_matlab_status' in c]
        max_iters = max([int(c.split('_')[0].replace('it', '')) for c in it_cols], default=3)

    if args.model:
        df = df[df["model_name"] == args.model]
        if df.empty:
            print(f"[ERROR] No records found for model: '{args.model}'")
            return

    plot_data = []
    
    for idx, row in df.iterrows():
        model = row.get('model_name', 'Unknown_Model')
        prompt = row.get('prompt_name', 'Unknown_Prompt')
        label = prompt if args.model else f"{model}\n{prompt}"
        
        for i in range(1, max_iters + 1):
            matlab_status = str(row.get(f'it{i}_matlab_status', ''))
            fail_stage = str(row.get(f'it{i}_failure_stage', 'NONE'))
            
            outcome = 'SKIPPED'
            if matlab_status == 'SOLVED':
                outcome = 'SUCCESS (STABLE)'
            elif matlab_status == 'UNSTABLE':
                outcome = 'UNSTABLE'
            elif fail_stage not in ['NONE', 'nan', '']:
                outcome = fail_stage
            elif pd.notna(row.get(f'it{i}_json_syntax_valid')) and str(row.get(f'it{i}_json_syntax_valid')).strip() != '':
                outcome = 'UNKNOWN_FAILURE'
                
            if outcome != 'SKIPPED':
                plot_data.append({
                    'label': label,
                    'iteration': i,
                    'outcome': outcome
                })

    df_plot = pd.DataFrame(plot_data)
    if df_plot.empty:
        print("[ERROR] No iteration data to plot.")
        return

    color_map = {
        'SUCCESS (STABLE)': '#2ca02c',
        'UNSTABLE':         '#bcbd22',
        'MATLAB':           '#d62728',
        'PYDANTIC':         '#ff7f0e',
        'JSON_DECODE':      '#ffbb78',
        'TOKEN_LIMIT':      '#9467bd',
        'API':              '#8c564b',
        'UNKNOWN_FAILURE':  '#7f7f7f'
    }

    fig, ax = plt.subplots(figsize=(14, max(6, max_iters * 1.6)))
    
    unique_labels = df_plot['label'].unique()
    x_positions = np.arange(len(unique_labels))
    label_to_x = {label: x for x, label in zip(x_positions, unique_labels)}

    for _, row in df_plot.iterrows():
        x = label_to_x[row['label']]
        y_bottom = row['iteration'] - 1 
        outcome = row['outcome']
        color = color_map.get(outcome, '#7f7f7f')
        hatch = '///' if outcome == 'UNSTABLE' else None
        
        ax.bar(
            x, 1, 
            bottom=y_bottom, 
            color=color, 
            edgecolor='white', 
            linewidth=2, 
            width=0.8,
            hatch=hatch
        )

    ax.set_xticks(x_positions)
    ax.set_xticklabels(unique_labels, rotation=45, ha='right', fontsize=10)
    
    ax.set_yticks([i - 0.5 for i in range(1, max_iters + 1)])
    ax.set_yticklabels([f'Iteration {i}' for i in range(1, max_iters + 1)], fontsize=11)
    ax.set_ylim(0, max_iters)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    
    title_suffix = f" ({args.model})" if args.model else ""
    ax.set_title(f'Evaluation Pipeline: Iteration Progression by Stage{title_suffix}', pad=20, fontsize=14, fontweight='bold')

    present_outcomes = df_plot['outcome'].unique()
    handles = []
    for out in present_outcomes:
        hatch = '///' if out == 'UNSTABLE' else None
        handles.append(mpatches.Patch(
            facecolor=color_map.get(out, '#7f7f7f'), 
            edgecolor='black' if hatch else 'white',
            hatch=hatch, 
            label=out
        ))
        
    ax.legend(handles=handles, bbox_to_anchor=(1.02, 1), loc='upper left', title="Stage Outcome", frameon=False)
    plt.tight_layout()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_model = args.model.replace("/", "_").replace(":", "_") if args.model else "all"
    filename = f"iteration_stack_{clean_model}_{timestamp}.png"
    
    output_path = results_dir / filename
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved stacked iteration plot to {output_path}")

if __name__ == "__main__":
    main()