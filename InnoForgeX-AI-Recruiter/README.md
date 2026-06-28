# Redrob Candidate Ranker

## Setup Instructions

1. Ensure you have Python 3.11+ installed.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Ranker

To generate the `submission.csv` from the candidate pool, run:
```bash
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
```
This script runs entirely locally on CPU, respects the 16GB RAM limit, and does not make any external API calls. It will process 100,000 candidates in under 5 minutes.

## Methodology

We built a highly optimized, rule-based and TF-IDF hybrid ranking engine. 
1. **Honeypot Filtering**: Automatically filters out profiles with logically impossible attributes (e.g., "expert" skills with 0 months of use, or years of experience exceeding mathematical limits).
2. **JD Disqualifiers**: Excludes profiles matching the exact disqualifiers listed in the JD:
   - Pure consulting firm experience without product experience.
   - Title chasers (frequent jumping without tenure).
   - "LangChain only" without foundational ML background (inferred via heuristic rules).
3. **Scoring Model**: Uses TF-IDF similarity between the candidate's career history/summary and the Job Description, heavily boosted by specific technical concepts (e.g., `Pinecone`, `Sentence-Transformers`, `Weaviate`, `NDCG`, `Hybrid Search`).
4. **Behavioral Modifier**: Scores are multiplied by a behavioral factor derived from `redrob_signals` to favor candidates who are active, responsive, and available.

## Output
The script produces exactly 100 top candidates with monotonically non-increasing scores and deterministic, auto-generated reasoning referencing their exact profile attributes.
