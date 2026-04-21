import os
import subprocess
import sys
import time

def run_query(query, session_file):
    print(f"\n--- Running query: '{query}' ---")
    # Point to the actual knowledge base in data/chroma_db
    env = os.environ.copy()
    root = "/Users/chandanapulikanti/Downloads/TrustMed-AI"
    env["CHROMA_DB_DIR"] = os.path.join(root, "data/chroma_db")
    env["CHROMA_COLLECTIONS"] = "diseases,symptoms,medicines"
    env["X0"] = "0.30"
    env["Y0"] = "0.15"
    env["RERANKER_MODEL_NAME"] = "" # Disable reranker for speed/reliability
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    anti_test_path = os.path.join(tests_dir, "anti_test.py")
    cmd = [sys.executable, "-u", anti_test_path, "--query", query, "--session_file", session_file]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        print("Error running command:")
        print(result.stdout)
        print(result.stderr)
        return "", ""
    
    # Extract the rewritten query if present
    rewritten = ""
    answer_preview = ""
    lines = result.stdout.splitlines()
    for i, line in enumerate(lines):
        if "[Context] Rewrote query:" in line:
            rewritten = line.split("->")[1].strip().strip("'")
            print(f"  -> Rewritten as: '{rewritten}'")
        if "== ANSWER ==" in line and i+2 < len(lines):
            answer_preview = lines[i+2].strip()[:150] + "..."
            print(f"  AI Response: {answer_preview}")
    
    return result.stdout, rewritten

def main():
    session_file = "context_test_history.json"
    if os.path.exists(session_file):
        os.remove(session_file)

    queries = [
        "What are the signs of diabetes?",
        "How to prevent it?",
        "What medications are used for it?",
        "What causes heart disease?",
        "What are the symptoms?"
    ]

    # Expected context keywords for verification (heuristic)
    expected_contexts = [
        "diabetes",
        "diabetes",
        "diabetes",
        "heart disease",
        "heart disease"
    ]

    for i, query in enumerate(queries):
        stdout, rewritten = run_query(query, session_file)
        
        # Check if the output contains relevant keywords (if the RAG works)
        # or at least if the query rewriting happened correctly.
        
        # For Q2, Q3, Q5, we expect rewriting
        if i in [1, 2, 4]:
            if not rewritten:
                print(f"WARNING: Query '{query}' was NOT rewritten.")
            else:
                expected = expected_contexts[i]
                if expected in rewritten.lower():
                    print(f"SUCCESS: Query rewritten correctly to include '{expected}'.")
                else:
                    print(f"FAILURE: Query rewritten but missing '{expected}'. Got: '{rewritten}'")
        
        # For Q4, we expect it NOT to be rewritten to include diabetes, or just stay as is
        if i == 3:
             if "diabetes" in rewritten.lower():
                 print("FAILURE: Context switch failed! Q4 rewritten to include 'diabetes'.")
             else:
                 print("SUCCESS: Context switch initiated (Q4 not polluted by previous context).")

    print("\nTest sequence completed.")

if __name__ == "__main__":
    main()
