import re
import importlib.util
import time  # For timing evaluation

# Dynamically load query_rag.py as a module
spec = importlib.util.spec_from_file_location("rag2", "rag2.py")
qr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qr)

# ---------- Test Cases ----------
TEST_CASES = [
    {
        "query": "Which units have access to the swimming pool?",
        "expected_collections": ["Amenities"],
        "expected_keywords": ["U-101", "U-102", "U-201", "U-202", "U-301", "U-302", "U-401", "U-402", "U-501", "U-502"]
    },
    {
        "query": "What is the monthly rent and deposit for unit U-101?",
        "expected_collections": ["Contracts"],
        "expected_keywords": ["25000", "50000"]
    },
    {
        "query": "Has the electricity bill for U-101 been paid?",
        "expected_collections": ["ElecBill"],
        "expected_keywords": ["12000", "paid"]
    },
    {
        "query": "How much was spent on elevator repair in August 2025?",
        "expected_collections": ["Expenses"],
        "expected_keywords": ["50000", "elevator repair"]
    },
    {
        "query": "What is the status of the maintenance request for U-101?",
        "expected_collections": ["Maintenance"],
        "expected_keywords": ["pending"]
    },
    {
        "query": "Has the rent for September 2025 for U-101 been paid?",
        "expected_collections": ["Rent"],
        "expected_keywords": ["25000", "paid"]
    },
    {
        "query": "Who is the plumber assigned to maintenance requests?",
        "expected_collections": ["Staff"],
        "expected_keywords": ["Pedro Cruz"]
    },
    {
        "query": "Who is the tenant of unit U-101?",
        "expected_collections": ["Tenants"],
        "expected_keywords": ["Maria Santos"]
    },
    {
        "query": "What floor is unit U-101 on and what is its status?",
        "expected_collections": ["Units"],
        "expected_keywords": ["1", "occupied"]
    },
    {
        "query": "Has the water bill for U-101 been paid?",
        "expected_collections": ["WaterBill"],
        "expected_keywords": ["3500", "paid"]
    },
]

# ---------- Helper to flatten Chroma results ----------
def flatten_chroma_results(results):
    """
    Convert Chroma query output to a flat list of dicts:
    [{'document': ..., 'metadata': {...}}, ...]
    """
    flat = []
    if isinstance(results, dict):
        docs_list = results.get("documents", [])
        metas_list = results.get("metadatas", [])
        for docs, metas in zip(docs_list, metas_list):
            for d, m in zip(docs, metas):
                flat.append({"document": d, "metadata": m})
    elif isinstance(results, list):
        for r in results:
            if isinstance(r, dict):
                flat.extend(flatten_chroma_results(r))
            elif isinstance(r, list):
                flat.extend(flatten_chroma_results({"documents": [r], "metadatas": [[{}]*len(r)]}))
            else:
                flat.append({"document": str(r), "metadata": {}})
    else:
        flat.append({"document": str(results), "metadata": {}})
    return flat

# ---------- Run Evaluation ----------
retrieval_score = 0
answer_score = 0
total_start_time = time.time()  # Start total evaluation timer

for case in TEST_CASES:
    print("\n=== Test Case ===")
    print(f"Query: {case['query']}")

    start_time = time.time()  # Start timer per query
    try:
        # Call generate_answer with return_results=True to get chunks
        context_str, response, results = qr.generate_answer(
            case["query"], return_results=True
        )

        # Flatten results safely
        parsed_chunks = flatten_chroma_results(results)

        # Extract collection names
        retrieved_collections = [c.get("metadata", {}).get("collection", "Unknown") for c in parsed_chunks]

        # Print retrieved chunks
        print("\n[RETRIEVED CHUNKS]")
        for i, c in enumerate(parsed_chunks, 1):
            coll_name = c.get("metadata", {}).get("collection", "Unknown")
            preview = str(c["document"])[:200].replace("\n", " ")
            print(f"--- Chunk {i} (from {coll_name}) ---")
            print(preview + ("..." if len(str(c["document"])) > 200 else ""))
            print()

        print("[DETECTED COLLECTIONS]", retrieved_collections)

        # Check retrieval accuracy
        expected_colls = set(case["expected_collections"])
        if expected_colls & set(retrieved_collections):
            print("Retrieval OK ✅")
            retrieval_score += 1
        else:
            print("Retrieval FAIL ❌")

        # Check answer correctness
        answer_ok = any(re.search(kw, response, re.IGNORECASE) for kw in case["expected_keywords"])
        if answer_ok:
            print("Answer OK ✅")
            answer_score += 1
        else:
            print("Answer FAIL ❌")

        print("Answer:", response)

    except Exception as e:
        print(f"Error running query: {e}")

    end_time = time.time()
    elapsed_ms = (end_time - start_time) * 1000
    print(f"[DEBUG] Query processed in {elapsed_ms:.2f} ms")

total_end_time = time.time()
total_elapsed = total_end_time - total_start_time
print("\n=== Summary ===")
print(f"Retrieval Accuracy: {retrieval_score}/{len(TEST_CASES)} ({retrieval_score/len(TEST_CASES)*100:.1f}%)")
print(f"Answer Accuracy:   {answer_score}/{len(TEST_CASES)} ({answer_score/len(TEST_CASES)*100:.1f}%)")
print(f"Total Evaluation Time: {total_elapsed:.2f} s")
print(f"Average per-query time: {total_elapsed/len(TEST_CASES)*1000:.2f} ms")
