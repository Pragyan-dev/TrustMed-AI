"""
LangChain Tool for querying Neo4j Medical Knowledge Graph.

This module provides a GraphRetriever tool that allows an agent to query
the Neo4j database using natural language, which gets converted to Cypher.
"""

import os
from dotenv import load_dotenv
from langchain_community.graphs import Neo4jGraph
from langchain.chains import GraphCypherQAChain
from langchain_openai import ChatOpenAI
from langchain.tools import Tool
from langchain_core.prompts import PromptTemplate
from src.ssl_bootstrap import configure_ssl_certificates

load_dotenv()
configure_ssl_certificates()

# Environment variables
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL") or DEFAULT_OPENROUTER_MODEL

# Lazy-loaded globals
_graph = None
_chain = None

# Custom Cypher generation prompt with fuzzy matching instructions
CYPHER_GENERATION_TEMPLATE = """Task: Generate a Cypher statement to query a graph database.

Instructions:
- Use only the provided relationship types and properties in the schema.
- Do NOT use exact string matching (e.g., n.name = "string").
- ALWAYS use case-insensitive fuzzy matching: toLower(n.name) CONTAINS toLower("search_term")
- When looking for symptoms, first find the disease node using fuzzy matching, then traverse to symptoms.
- Return only the Cypher statement, no explanations.

Schema:
{schema}

Question: {question}

Cypher Query:"""

CYPHER_GENERATION_PROMPT = PromptTemplate(
    input_variables=["schema", "question"],
    template=CYPHER_GENERATION_TEMPLATE
)


def get_graph() -> Neo4jGraph:
    """Lazily initialize and return the Neo4jGraph instance."""
    global _graph
    if _graph is None:
        _graph = Neo4jGraph(
            url=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD
        )
    return _graph


def get_chain() -> GraphCypherQAChain:
    """Lazily initialize and return the GraphCypherQAChain instance."""
    global _chain
    if _chain is None:
        graph = get_graph()
        
        llm = ChatOpenAI(
            model=OPENROUTER_MODEL,
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0  # Deterministic for Cypher generation
        )
        
        _chain = GraphCypherQAChain.from_llm(
            llm=llm,
            graph=graph,
            cypher_prompt=CYPHER_GENERATION_PROMPT,
            validate_cypher=True,
            top_k=5,
            verbose=True,
            allow_dangerous_requests=True  # Required acknowledgment for Cypher execution
        )
    return _chain


def query_graph(question: str) -> str:
    """
    Query the Neo4j knowledge graph with a natural language question.
    
    Args:
        question: A natural language question about medical data.
        
    Returns:
        The answer from the graph, or 'No structured data found' on failure.
    """
    try:
        chain = get_chain()
        result = chain.invoke({"query": question})
        
        # Extract the result string
        answer = result.get("result", "")
        if not answer or answer.strip() == "":
            return "No structured data found"
        return answer
        
    except Exception as e:
        print(f"[GraphRetriever] Error querying graph: {e}")
        err_msg = str(e).lower()
        if any(token in err_msg for token in ("routing", "connect", "certificate", "ssl")):
            return "Knowledge graph unavailable"
        return "No structured data found"


# Create the LangChain Tool
GraphRetriever = Tool(
    name="GraphRetriever",
    func=query_graph,
    description=(
        "Useful for retrieving structured medical facts, strict relationships "
        "(like Drug-Treats-Disease), and looking up verified symptoms. "
        "Input should be a specific medical question."
    )
)


if __name__ == "__main__":
    # Quick test
    print("Testing GraphRetriever...")
    test_query = "What symptoms are associated with diabetes?"
    print(f"Query: {test_query}")
    result = GraphRetriever.invoke(test_query)
    print(f"Result: {result}")
