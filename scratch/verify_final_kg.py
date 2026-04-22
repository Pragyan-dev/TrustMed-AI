from src.trustmed_brain import get_graph_chain


try:
    chain = get_graph_chain()
    dis_count = chain.graph.query("MATCH (d:Disease) RETURN count(d) as count")[0]["count"]
    sym_count = chain.graph.query("MATCH (s:Symptom) RETURN count(s) as count")[0]["count"]
    sample = chain.graph.query(
        "MATCH (d:Disease) WHERE d.cui IS NOT NULL RETURN d.name, d.cui LIMIT 5"
    )

    print(f"DISEASE_COUNT: {dis_count}")
    print(f"SYMPTOM_COUNT: {sym_count}")
    print(f"SAMPLES: {sample}")

    atelect_check = chain.graph.query(
        "MATCH (d:Disease {name: 'Atelectasis'}) RETURN d.name, d.cui"
    )
    print(f"ATELECTASIS: {atelect_check}")
except Exception as exc:
    print(f"ERROR: {exc}")
