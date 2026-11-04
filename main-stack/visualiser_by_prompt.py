"""
================================================================================
SimplusGT Evaluation Results Visualizer - Grouped by Prompt
================================================================================
"""

import argparse
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.transforms import blended_transform_factory
import numpy as np
import textwrap
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Visualize evaluation results grouped by Prompt.")
    parser.add_argument("-i", "--input", type=str, default="eval_results/results.csv", help="Path to results CSV")
    parser.add_argument("-o", "--output", type=str, default="eval_results", help="Output directory")
    parser.add_argument("-n", "--max-iterations", type=int, default=None, help="Maximum number of iterations to display (auto-detected from CSV if omitted)")
    args = parser.parse_args()

    csv_path = Path(args.input)
    results_dir = Path(args.output)

    if not csv_path.exists():
        print(f"[ERROR] No data found at {csv_path}.")
        return

    results_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(csv_path)
    if df.empty:
        print("[ERROR] CSV is empty.")
        return
    if args.max_iterations is not None:
        max_iters = args.max_iterations
    else:
        it_cols = [c for c in df.columns if c.startswith('it') and '_matlab_status' in c]
        max_iters = max([int(c.split('_')[0].replace('it', '')) for c in it_cols], default=3)

    # Sort and group the dataframe by prompt first
    df = df.sort_values(by=['prompt_name', 'model_name'])
    grouped = df.groupby('prompt_name', sort=False)

    color_map = {
        'SUCCESS (STABLE)': '#2ca02c', 'UNSTABLE': '#bcbd22',
        'MATLAB': '#d62728', 'PYDANTIC': '#ff7f0e', 'JSON_DECODE': '#ffbb78',
        'TOKEN_LIMIT': '#9467bd', 'API': '#8c564b', 'UNKNOWN_FAILURE': '#7f7f7f'
    }

    fig, ax = plt.subplots(figsize=(16, 8))
    
    current_x = 0
    x_ticks = []
    x_ticklabels = []
    group_labels = []
    present_outcomes = set()

    for prompt, group in grouped:
        start_x = current_x
        for _, row in group.iterrows():
            model = row.get('model_name', 'Unknown_Model')
            x_ticks.append(current_x)
            x_ticklabels.append(model)
            
            for i in range(1, max_iters + 1):
                matlab_status = str(row.get(f'it{i}_matlab_status', ''))
                fail_stage = str(row.get(f'it{i}_failure_stage', 'NONE'))
                
                outcome = 'SKIPPED'
                if matlab_status == 'SOLVED': outcome = 'SUCCESS (STABLE)'
                elif matlab_status == 'UNSTABLE': outcome = 'UNSTABLE'
                elif fail_stage not in ['NONE', 'nan', '']: outcome = fail_stage
                elif pd.notna(row.get(f'it{i}_json_syntax_valid')) and str(row.get(f'it{i}_json_syntax_valid')).strip() != '':
                    outcome = 'UNKNOWN_FAILURE'
                    
                if outcome != 'SKIPPED':
                    present_outcomes.add(outcome)
                    color = color_map.get(outcome, '#7f7f7f')
                    hatch = '///' if outcome == 'UNSTABLE' else None
                    
                    ax.bar(current_x, 1, bottom=i-1, color=color, edgecolor='white', 
                           linewidth=1.5, width=0.8, hatch=hatch)
            
            current_x += 1
        
        # Record the center of this group for the parent label
        center_x = (start_x + current_x - 1) / 2
        group_labels.append((center_x, prompt))
        current_x += 1.5  # Add a visual gap between prompt groups

    # Configure X-axis limits and primary ticks (Models)
    ax.set_xlim(-1, current_x - 0.5)
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(x_ticklabels, rotation=45, ha='right', fontsize=9)
    
    # Add secondary grouping labels (Prompts) using blended transforms
    trans = blended_transform_factory(ax.transData, ax.transAxes)
    for cx, prompt_name in group_labels:
        wrapped_prompt = textwrap.fill(prompt_name, width=14)
        ax.text(cx, -0.35, wrapped_prompt, transform=trans, ha='center', va='top', 
                fontsize=12, fontweight='bold')

    ax.set_yticks([i - 0.5 for i in range(1, max_iters + 1)])
    ax.set_yticklabels([f'Iteration {i}' for i in range(1, max_iters + 1)], fontsize=11)
    ax.set_ylim(0, max_iters)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.set_title('Evaluation Pipeline: Grouped by Prompt', pad=20, fontsize=14, fontweight='bold')

    # Dynamic Legend
    handles = []
    for out in present_outcomes:
        hatch = '///' if out == 'UNSTABLE' else None
        handles.append(mpatches.Patch(facecolor=color_map.get(out, '#7f7f7f'), 
                                      edgecolor='black' if hatch else 'white',
                                      hatch=hatch, label=out))
    ax.legend(handles=handles, bbox_to_anchor=(1.02, 1), loc='upper left', title="Stage Outcome", frameon=False)
    
    plt.tight_layout()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = results_dir / f"iteration_grouped_by_prompt_{timestamp}.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved prompt-grouped plot to {output_path}")

if __name__ == "__main__":
    main()