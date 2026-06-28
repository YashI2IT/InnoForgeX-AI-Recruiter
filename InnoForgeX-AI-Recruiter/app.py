import gradio as gr
import subprocess
import pandas as pd
import sys
import os

def run_ranker():
    try:
        # Define paths
        candidates_path = "data/candidates.jsonl"
        output_path = "output/submission.csv"
        
        # Check if input exists
        if not os.path.exists(candidates_path):
            return "Error: data/candidates.jsonl not found. Make sure you uploaded the dataset!", None, None

        # Ensure output dir exists
        os.makedirs("output", exist_ok=True)
        
        # Run the ranker script
        result = subprocess.run(
            [sys.executable, "backend/rank.py", "--candidates", candidates_path, "--out", output_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return f"Error running rank.py:\n{result.stderr}", None, None
            
        # Read the output CSV to display top 10
        if os.path.exists(output_path):
            df = pd.read_csv(output_path)
            top_10 = df.head(10)
            
            # Generate XLSX version
            xlsx_path = "output/submission.xlsx"
            df.to_excel(xlsx_path, index=False)
            
            return "✅ Ranking completed successfully! View the top 10 below and download the output files.", top_10, [output_path, xlsx_path]
        else:
            return "Error: Ranker completed but submission.csv was not found.", None, None
            
    except Exception as e:
        return f"An error occurred: {str(e)}", None, None

# Gradio Interface
with gr.Blocks(title="AI-Recruiter Ranker", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🚀 AI-Recruiter: Intelligent Candidate Ranker")
    gr.Markdown("Click the button below to process the `100,000` candidates from the dataset using our TF-IDF & Heuristic Engine. The process takes less than 60 seconds on standard CPUs.")
    
    with gr.Row():
        run_btn = gr.Button("Run Ranker Engine", variant="primary")
        
    status_text = gr.Textbox(label="Status Log", interactive=False)
    
    gr.Markdown("### 🏆 Top 10 Ranked Candidates")
    preview_table = gr.Dataframe(interactive=False)
    
    gr.Markdown("### 📥 Download Output")
    download_btn = gr.File(label="Full Submission Files (CSV and XLSX)", file_count="multiple")
    
    run_btn.click(
        fn=run_ranker,
        inputs=[],
        outputs=[status_text, preview_table, download_btn]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
