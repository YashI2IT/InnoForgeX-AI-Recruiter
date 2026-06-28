import argparse
import json
import csv
import re
from datetime import datetime
import math
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

def parse_args():
    parser = argparse.ArgumentParser(description="Redrob Candidate Ranker")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    parser.add_argument("--out", required=True, help="Path to output submission.csv")
    return parser.parse_args()

def is_honeypot(candidate):
    # Check 1: Expert skill with 0 duration
    for skill in candidate.get('skills', []):
        if skill.get('proficiency') == 'expert' and skill.get('duration_months', 0) == 0:
            return True
    
    # Check 2: Career history duration impossible
    # Current date for hackathon timeline is around mid 2026.
    now = datetime(2026, 6, 1)
    
    for job in candidate.get('career_history', []):
        start_str = job.get('start_date')
        end_str = job.get('end_date')
        claimed_duration = job.get('duration_months', 0)
        
        if not start_str:
            continue
            
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d")
            if end_str:
                end_date = datetime.strptime(end_str, "%Y-%m-%d")
            else:
                end_date = now
                
            actual_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
            if claimed_duration > actual_months + 12: # Add 1 year buffer for date parsing edge cases
                return True
                
            if start_date > now:
                return True # Started in future?
        except Exception:
            pass
            
    # Check 3: YOE much larger than max possible age (e.g. 50+ YOE)
    if candidate.get('profile', {}).get('years_of_experience', 0) > 40:
        return True
        
    return False

def check_disqualifiers(candidate):
    # Returns True if disqualified
    career = candidate.get('career_history', [])
    if not career:
        return False
        
    # Disqualifier 1: Pure consulting
    consulting_firms = {'tcs', 'infosys', 'wipro', 'accenture', 'cognizant', 'capgemini'}
    all_consulting = True
    for job in career:
        comp = job.get('company', '').lower()
        is_consulting = any(c in comp for c in consulting_firms)
        if not is_consulting:
            all_consulting = False
            break
    if all_consulting and len(career) > 0:
        return True
        
    # Disqualifier 2: Title chasers
    # "switching companies every 1.5 years" -> average duration < 18 months over >= 4 jobs
    if len(career) >= 4:
        total_duration = sum(job.get('duration_months', 0) for job in career)
        if (total_duration / len(career)) < 18:
            return True
            
    # Disqualifier 3: Pure research (Academic labs)
    all_research = True
    for job in career:
        comp = job.get('company', '').lower()
        ind = job.get('industry', '').lower()
        is_research = 'university' in comp or 'lab' in comp or 'research' in ind
        if not is_research:
            all_research = False
            break
    if all_research and len(career) > 0:
        return True
        
    return False

def compute_base_score(candidate, vectorizer, ideal_vec):
    prof = candidate.get('profile', {})
    summary = prof.get('summary', '')
    
    career_texts = []
    for job in candidate.get('career_history', []):
        career_texts.append(f"{job.get('title', '')} at {job.get('company', '')}: {job.get('description', '')}")
        
    skill_texts = [f"{s.get('name', '')}" for s in candidate.get('skills', [])]
    
    doc = summary + " " + " ".join(career_texts) + " " + " ".join(skill_texts)
    
    doc_vec = vectorizer.transform([doc])
    sim = cosine_similarity(ideal_vec, doc_vec)[0][0]
    return sim

def generate_reasoning(candidate, final_score, score_components):
    prof = candidate.get('profile', {})
    yoe = prof.get('years_of_experience', 0)
    title = prof.get('current_title', 'Engineer')
    
    signals = candidate.get('redrob_signals', {})
    resp_rate = signals.get('recruiter_response_rate', 0.0)
    
    skills = [s.get('name') for s in candidate.get('skills', [])]
    ai_skills = [s for s in skills if s.lower() in ['python', 'machine learning', 'nlp', 'deep learning', 'pytorch', 'tensorflow', 'embeddings', 'pinecone', 'llm', 'rag']]
    
    skill_str = f"{len(ai_skills)} AI core skills" if ai_skills else "matching skills"
    
    # Justification text
    if score_components['is_perfect_fit']:
        reason = f"Excellent fit: {title} with {yoe} yrs; strong ML/retrieval background ({skill_str}). Highly responsive ({resp_rate*100:.0f}% response rate) and active."
    else:
        reason = f"Solid fit: {title} with {yoe} yrs; possesses {skill_str}. Recruiter response rate is {resp_rate*100:.0f}%."
        
    # Cap length just in case
    return reason[:200]

def main():
    args = parse_args()
    
    print(f"Loading candidates from {args.candidates}...")
    candidates = []
    import gzip
    open_func = gzip.open if args.candidates.endswith('.gz') else open
    with open_func(args.candidates, 'rt', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                candidates.append(json.loads(line))
                
    print(f"Loaded {len(candidates)} candidates.")
    
    # Ideal JD Text for TF-IDF
    ideal_text = """
    machine learning AI engineer backend production embeddings retrieval sentence-transformers openai bge e5 
    vector database hybrid search pinecone weaviate qdrant milvus opensearch elasticsearch faiss python 
    evaluation frameworks ndcg mrr map offline-to-online a/b test llm fine-tuning lora qlora peft 
    xgboost learning-to-rank ranking search recommendation system hr-tech marketplace distributed systems inference.
    """ * 3 # Repeat to increase weight of these words compared to generic stopwords
    
    vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
    
    # To build vocabulary quickly, we can fit on a sample of candidates + the ideal text
    print("Fitting TF-IDF...")
    sample_docs = [ideal_text]
    for c in candidates[:5000]: # fit on first 5000 to save time
        doc = c.get('profile', {}).get('summary', '')
        for job in c.get('career_history', []):
            doc += " " + job.get('description', '')
        sample_docs.append(doc)
        
    vectorizer.fit(sample_docs)
    ideal_vec = vectorizer.transform([ideal_text])
    
    print("Scoring candidates...")
    scored_candidates = []
    
    now = datetime(2026, 6, 1)
    
    for c in candidates:
        if is_honeypot(c):
            continue
            
        if check_disqualifiers(c):
            continue
            
        base_score = compute_base_score(c, vectorizer, ideal_vec)
        
        # Adjust score based on YOE
        yoe = c.get('profile', {}).get('years_of_experience', 0)
        yoe_multiplier = 1.0
        if 5 <= yoe <= 9:
            yoe_multiplier = 1.2
        elif yoe < 5:
            yoe_multiplier = 0.5 + (0.1 * yoe) # Penalty for < 5
        elif yoe > 9:
            yoe_multiplier = 1.0 - (0.02 * (yoe - 9)) # Slight penalty for > 9
            
        # Adjust score based on Behavioral Signals
        signals = c.get('redrob_signals', {})
        resp_rate = signals.get('recruiter_response_rate', 0.0)
        
        last_active = signals.get('last_active_date')
        recency_penalty = 1.0
        if last_active:
            try:
                la_date = datetime.strptime(last_active, "%Y-%m-%d")
                days_since = (now - la_date).days
                if days_since > 180:
                    recency_penalty = 0.5 # heavily penalize if inactive for 6 months
                elif days_since > 90:
                    recency_penalty = 0.8
            except:
                pass
                
        open_to_work = signals.get('open_to_work_flag', False)
        otw_multiplier = 1.1 if open_to_work else 1.0
        
        # Combine
        final_score = base_score * yoe_multiplier * (0.5 + 0.5 * resp_rate) * recency_penalty * otw_multiplier
        
        # Add a tiny random jitter deterministic on candidate_id to avoid large tie blocks
        import hashlib
        h = int(hashlib.md5(c['candidate_id'].encode()).hexdigest(), 16)
        jitter = (h % 1000) / 1000000.0
        final_score += jitter
        
        is_perfect = (yoe_multiplier >= 1.0 and resp_rate > 0.6 and recency_penalty == 1.0 and base_score > 0.1)
        
        scored_candidates.append({
            'candidate_id': c['candidate_id'],
            'score': final_score,
            'candidate': c,
            'is_perfect_fit': is_perfect
        })
        
    print("Sorting candidates...")
    scored_candidates.sort(key=lambda x: x['score'], reverse=True)
    
    top_100 = scored_candidates[:100]
    
    print(f"Writing to {args.out}...")
    with open(args.out, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['candidate_id', 'rank', 'score', 'reasoning'])
        
        for i, item in enumerate(top_100):
            rank = i + 1
            reasoning = generate_reasoning(item['candidate'], item['score'], {'is_perfect_fit': item['is_perfect_fit']})
            # Ensure score format is exactly 4 decimal places string
            score_str = f"{item['score']:.4f}"
            writer.writerow([item['candidate_id'], rank, score_str, reasoning])
            
    print("Done!")

if __name__ == "__main__":
    main()
