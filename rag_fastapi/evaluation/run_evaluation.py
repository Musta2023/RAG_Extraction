import requests
import json
import time
from typing import List, Dict, Any, Optional
import os

# Base URL of your FastAPI application
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_QUESTIONS_FILE = os.path.join(BASE_DIR, "test_questions.json")
OUTPUT_REPORT_FILE = os.path.join(BASE_DIR, "evaluation_report.json")

def _wait_for_api_healthy(max_retries: int = 20, delay_seconds: int = 3) -> bool:
    """Waits for the API to become healthy with retries."""
    print(f"Waiting for API to become healthy (max {max_retries} retries, {delay_seconds}s delay)...")
    for i in range(max_retries):
        try:
            response = requests.get(f"{BASE_URL}/health")
            response.raise_for_status()
            print(f"Health check successful after {i+1} attempts: {response.json()}")
            return True
        except requests.exceptions.RequestException:
            print(f"Attempt {i+1}/{max_retries}: API not yet healthy. Retrying in {delay_seconds}s...")
            time.sleep(delay_seconds)
    print(f"API did not become healthy after {max_retries} attempts. Exiting.")
    return False

def run_health_check():
    """Checks if the API is healthy."""
    # This function is now redundant, as _wait_for_api_healthy handles it
    pass

def start_ingestion(ingest_payload: Dict[str, Any]) -> Optional[str]:
    """Starts an ingestion job and returns the job ID."""
    print(f"\nStarting ingestion job with seed URLs: {ingest_payload['seed_urls']}")
    try:
        response = requests.post(f"{BASE_URL}/ingest", json=ingest_payload)
        response.raise_for_status()
        job_id = response.json()["job_id"]
        print(f"Ingestion job started. Job ID: {job_id}")
        return job_id
    except requests.exceptions.RequestException as e:
        print(f"Failed to start ingestion job: {e}")
        return None

def wait_for_job_completion(job_id: str, timeout_minutes: int = 10):
    """Waits for an ingestion job to complete."""
    print(f"Waiting for job {job_id} to complete...")
    start_time = time.time()
    while time.time() - start_time < timeout_minutes * 60:
        try:
            response = requests.get(f"{BASE_URL}/status/{job_id}")
            response.raise_for_status()
            status_data = response.json()
            if status_data["status"] == "pending":
                print(f"Job {job_id} is pending... waiting for worker to pick it up.")
            else:
                # Added a check for 'pages_fetched' and 'pages_indexed' in case they are missing during early stages
                pages_fetched = status_data.get('pages_fetched', 0)
                pages_indexed = status_data.get('pages_indexed', 0)
                print(f"Job {job_id} status: {status_data['status']} (Fetched: {pages_fetched}, Indexed: {pages_indexed})")
            
            if status_data["status"] == "completed":
                print(f"Job {job_id} completed successfully.")
                return True
            elif status_data["status"] == "failed":
                print(f"Job {job_id} failed. Errors: {status_data.get('errors', 'No error details.')}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"Error checking job status: {e}")
        time.sleep(5) # Wait 5 seconds before checking again
    print(f"Job {job_id} did not complete within {timeout_minutes} minutes timeout.")
    return False

def ask_question(job_id: str, question: str) -> Optional[Dict[str, Any]]:
    """Sends a question to the /ask endpoint and returns the response."""
    print(f"\nAsking question (Job ID: {job_id}): {question}")
    try:
        response = requests.post(f"{BASE_URL}/ask", json={"job_id": job_id, "question": question})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Failed to ask question: {e}")
        return None

def evaluate_response(question: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates the RAG response against expected keywords and citation quality."""
    eval_results = {
        "question": question["question"],
        "expected_answer_keywords": question.get("expected_answer_keywords", []),
        "response_answer": response.get("answer", ""),
        "confidence": response.get("confidence", "unknown"),
        "citations_count": len(response.get("citations", [])),
        "citation_urls": [c["url"] for c in response.get("citations", [])],
        "grounding_notes": response.get("grounding_notes", ""),
        "evaluation_notes": []
    }

    # Check for keyword presence (simple check)
    answer_lower = eval_results["response_answer"].lower()
    found_keywords = []
    missing_keywords = []
    for kw in eval_results["expected_answer_keywords"]:
        if kw.lower() in answer_lower:
            found_keywords.append(kw)
        else:
            missing_keywords.append(kw)

    if missing_keywords:
        eval_results["evaluation_notes"].append(f"Missing expected keywords: {', '.join(missing_keywords)}")
    if found_keywords:
        eval_results["evaluation_notes"].append(f"Found expected keywords: {', '.join(found_keywords)}")
    
    # Check if citations are present for non-abstaining answers
    if eval_results["response_answer"] != "I cannot answer this question based on the provided information." and eval_results["citations_count"] == 0:
         eval_results["evaluation_notes"].append("Warning: Answer provided but no citations found.")
    
    # Placeholder for more advanced citation quality check (e.g., does quote actually match source?)

    return eval_results

def main():
    if not _wait_for_api_healthy(): # Use the new retry mechanism
        print("API did not become healthy. Exiting evaluation.")
        return

    # Load test questions
    try:
        with open(TEST_QUESTIONS_FILE, 'r', encoding='utf-8') as f:
            test_questions = json.load(f)
    except FileNotFoundError:
        print(f"Error: {TEST_QUESTIONS_FILE} not found. Please create it.")
        return
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {TEST_QUESTIONS_FILE}.")
        return

    # Example Ingestion Payload (adjust as needed for your test data)
    # This should ideally point to a known set of documents that can answer your test questions
    ingestion_payload = {
        "seed_urls": ["https://www.paulgraham.com/avg.html"], # Example URL
        "domain_allowlist": ["paulgraham.com"],
        "max_pages": 5,
        "max_depth": 1,
        "user_notes": "Evaluation ingestion"
    }

    # Start and wait for ingestion job
    job_id = start_ingestion(ingestion_payload)
    if not job_id:
        print("Could not start ingestion job. Exiting evaluation.")
        return
    
    if not wait_for_job_completion(job_id):
        print("Ingestion job failed or timed out. Cannot proceed with Q&A evaluation.")
        return

    all_evaluation_results = []
    for q_data in test_questions:
        response = ask_question(job_id, q_data["question"])
        if response:
            eval_results = evaluate_response(q_data, response)
            all_evaluation_results.append(eval_results)
            print(f"  --> Confidence: {eval_results['confidence']}, Citations: {eval_results['citations_count']}")
            print(f"  --> Eval Notes: {'; '.join(eval_results['evaluation_notes'])}")
        else:
            all_evaluation_results.append({
                "question": q_data["question"],
                "response_answer": "API_ERROR",
                "confidence": "unknown",
                "citations_count": 0,
                "evaluation_notes": ["Failed to get response from API."]
            })

    # Save evaluation report
    with open(OUTPUT_REPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_evaluation_results, f, indent=4, ensure_ascii=False)
    print(f"\nEvaluation complete. Report saved to {OUTPUT_REPORT_FILE}")

if __name__ == "__main__":
    main()