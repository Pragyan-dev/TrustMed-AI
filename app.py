"""
TrustMed AI - Streamlit Dashboard
A clean, functional clinical decision support interface.
"""

import streamlit as st
import asyncio
import os
import sys

# Add project root to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.trustmed_brain import ask_trustmed
from src.graph_visualizer import get_graph
from streamlit_agraph import agraph, Node, Edge, Config


# Page config
st.set_page_config(
    page_title="TrustMed AI",
    page_icon="🩺",
    layout="wide"
)

# Minimal CSS for dark theme compatibility
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
    }
    .main-header h1 {
        color: #00d4ff;
        font-size: 2.5rem;
        margin-bottom: 0.25rem;
    }
    .main-header p {
        color: #888;
        font-size: 1rem;
    }
    .feature-box {
        background: rgba(0, 212, 255, 0.1);
        border: 1px solid rgba(0, 212, 255, 0.3);
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        margin-bottom: 1rem;
    }
    .feature-box h4 {
        color: #00d4ff;
        margin: 0 0 0.5rem 0;
    }
    .feature-box p {
        color: #aaa;
        margin: 0;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("🔧 System Status")
    st.success("✅ Knowledge Graph Active")
    st.success("✅ MIMIC-IV Data Loaded")
    st.success("✅ Vector Store Ready")
    
    st.divider()
    
    st.header("📷 Medical Imaging")
    uploaded_file = st.file_uploader("Upload Medical Scan", type=["jpg", "png", "jpeg"])
    
    # Track if image should be used in next query
    if "use_image_in_query" not in st.session_state:
        st.session_state.use_image_in_query = False
    
    if uploaded_file is not None:
        # Save the file to disk so backend can access it
        image_path = os.path.abspath("temp_scan.jpg")
        with open(image_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Verify and display
        if os.path.exists(image_path):
            st.image(uploaded_file, caption="Uploaded Scan", use_container_width=True)

            # Auto-detect compound figures
            try:
                from src.subfigure_detector import detect_compound_figure, get_analysis_summary
                analysis = detect_compound_figure(image_path)
                if analysis.is_compound and analysis.confidence >= 0.5:
                    rows, cols = analysis.grid_structure
                    st.info(
                        f"📊 **Compound figure detected:** {analysis.num_panels} panels "
                        f"({rows}×{cols} grid, panels: {', '.join(analysis.detected_labels)}). "
                        f"Each panel will be analyzed independently."
                    )
                    st.session_state.is_compound_figure = True
                else:
                    st.success("✅ Image ready for analysis")
                    st.session_state.is_compound_figure = False
            except Exception:
                st.success("✅ Image ready for analysis")
                st.session_state.is_compound_figure = False

            print(f"[app.py] Image saved to: {image_path}")

            # Checkbox to include image in next query
            st.session_state.use_image_in_query = st.checkbox(
                "👁️ Include image in next message",
                value=st.session_state.use_image_in_query,
                help="Check this to analyze the image with your next question"
            )
        else:
            st.error("❌ Failed to save image")
    else:
        st.session_state.use_image_in_query = False
    
    st.divider()
    
    st.header("🏥 Sample Patient IDs")
    st.code("10002428\n10025463\n10027602\n10009049")
    
    st.divider()
    
    st.header("⚡ Quick Actions")
    if st.button("🩺 Assess Patient 10002428", use_container_width=True):
        st.session_state.pending_query = "Assess patient 10002428. Check vitals and medication risks."
    if st.button("💊 Drug Interactions", use_container_width=True):
        st.session_state.pending_query = "What are common drug interactions with lisinopril?"
    if st.button("🫁 Pneumonia Info", use_container_width=True):
        st.session_state.pending_query = "What are the symptoms of pneumonia?"
        
    st.divider()
    
    st.header("📝 Clinical Tools")
    if st.button("📄 Generate Clinical Note (SOAP)", use_container_width=True):
        # We need context to generate the note
        if not st.session_state.messages:
            st.warning("Start a conversation first!")
        else:
            with st.spinner("✍️ Drafting SOAP Note..."):
                from src.trustmed_brain import generate_soap_note, get_patient_context
                
                # Try to extract patient ID from history if possible, or just pass generic context
                # For simplicity, we'll re-fetch context if we can find an ID in the last user query
                last_user_msg = next((m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"), "")
                pat_context = get_patient_context(last_user_msg)
                
                soap_note = generate_soap_note(
                    history=st.session_state.messages, 
                    patient_context=pat_context if pat_context else "No specific patient context linked."
                )
                
                # Store in session state to persist display? 
                # Or just display immediately. A sidebar expander is nice.
                st.session_state.show_soap = soap_note

    # Display SOAP note if generated
    if "show_soap" in st.session_state and st.session_state.show_soap:
        with st.expander("📄 Clinical SOAP Note", expanded=True):
            import json as _json
            soap_data = st.session_state.show_soap
            soap_text = _json.dumps(soap_data, indent=2) if isinstance(soap_data, dict) else str(soap_data)
            st.text_area("Copy-Paste Ready", value=soap_text, height=300)
            if st.button("Close Note"):
                del st.session_state.show_soap
                st.rerun()

# Main content
st.markdown("""
<div class="main-header">
    <h1>🩺 TrustMed AI</h1>
    <p>Clinical Decision Support System • Powered by Neuro-Symbolic AI</p>
</div>
""", unsafe_allow_html=True)

# Feature cards
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("""
    <div class="feature-box">
        <h4>📊 Knowledge Graph</h4>
        <p>Verified medical relationships</p>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown("""
    <div class="feature-box">
        <h4>🏥 Patient Records</h4>
        <p>Real-time MIMIC-IV data</p>
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown("""
    <div class="feature-box">
        <h4>📚 Medical Literature</h4>
        <p>Semantic vector search</p>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# Tabs Layout
# =============================================================================

tab_chat, tab_graph = st.tabs(["💬 Chat", "🕸️ Knowledge Graph"])

# =============================================================================
# Tab 1: Chat Interface
# =============================================================================

with tab_chat:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Chat header with clear button
    col_chat, col_clear = st.columns([6, 1])
    with col_chat:
        st.subheader("💬 Clinical Assistant")
    with col_clear:
        if st.button("🗑️ Clear", key="clear_chat", help="Clear chat history"):
            st.session_state.messages = []
            st.rerun()

    # Create a container for messages
    chat_container = st.container()

    # Display chat history
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Handle pending query from sidebar buttons
    if "pending_query" in st.session_state and st.session_state.pending_query:
        # We need to effectively "submit" this.
        # Streamlit generic way: just treat as input.
        val = st.session_state.pending_query
        st.session_state.pending_query = None
        # We'll use a session state variable to trigger the run in the loop below
        st.session_state.auto_submit = val

# =============================================================================
# Tab 2: Knowledge Graph Visualization
# =============================================================================

with tab_graph:
    st.subheader("🕸️ Interactive Knowledge Graph")
    
    col_search, col_pat = st.columns([2, 1])
    with col_search:
        # Default term from last user query if available
        default_term = "Pneumonia"
        if st.session_state.messages:
            last_msg = st.session_state.messages[-1]["content"]
            # Simple heuristic: find longer words or just use default
            if "pneumonia" in last_msg.lower(): default_term = "Pneumonia"
            elif "diabetes" in last_msg.lower(): default_term = "Diabetes"
            
        graph_search = st.text_input("Visualize Condition / Disease", value=default_term)
        
    with col_pat:
        # Try to find a patient ID from sidebar or session
        def_pat = ""
        # We could use simple regex on chat history, but for now let user input
        graph_pat_id = st.text_input("Patient Context (Optional ID)", value=def_pat, 
                                     placeholder="e.g. 10002428")

    # Persist graph state
    if "graph_active" not in st.session_state:
        st.session_state.graph_active = False

    if st.button("🚀 Render Graph"):
        st.session_state.graph_active = True
    
    if st.session_state.graph_active:
        with st.spinner("Fetching subgraph from Neo4j..."):
            try:
                nodes, edges, config = get_graph(graph_search, graph_pat_id)
                if nodes:
                    # Key argument is not supported, rely on data
                    agraph(nodes=nodes, edges=edges, config=config)
                else:
                    st.warning(f"No graph data found for query '{graph_search}'. Try exact disease name.")
            except Exception as e:
                st.error(f"Graph Error: {e}")
                
        if st.button("🔄 Reset View"):
            st.session_state.graph_active = False
            st.rerun()
    else:
        st.info("Enter a disease name and click 'Render Graph' to explore.")


# =============================================================================
# Chat Input & Processing (Bottom Global)
# =============================================================================

# Check if we have an auto-submit pending
auto_input = st.session_state.get("auto_submit", None)
if auto_input:
    st.session_state.auto_submit = None  # Consume

user_input = st.chat_input("💬 Ask about a patient (e.g., 'Assess patient 10002428')...")

# Use either manual or auto input
final_input = user_input if user_input else auto_input

if final_input:
    # 1. Append User Message
    st.session_state.messages.append({"role": "user", "content": final_input})
    
    # We need to redraw the chat tab to show the user message immediately?
    # Since chat_input triggers rerun, the `with tab_chat` block above will run and show it.
    # But we need to ensure the spinner occurs INSIDE the chat tab.
    
    with tab_chat:
         # Need to re-render the user message if it wasn't captured in the top loop? 
         # No, st.session_state.messages is updated, so top loop renders it.
         # But the loop already ran at top of script.
         # So we need to manually display just this new message or force rerun?
         # Standard pattern: Display immediate message, then spin.
         
         with st.chat_message("user"):
             st.markdown(final_input)
             
         # Prepare image attachment
         query = final_input
         if st.session_state.get('use_image_in_query', False) and uploaded_file:
             query += " [ATTACHMENT: temp_scan.jpg]"
             st.session_state.use_image_in_query = False
             
         # 2. Generate Assistant Response
         with st.chat_message("assistant"):
             with st.spinner("🧠 Analyzing patient data, graph, and literature..."):
                 try:
                     history = st.session_state.messages[:-1]
                     response = asyncio.run(ask_trustmed(query, chat_history=history))
                     st.markdown(response)
                     st.session_state.messages.append({"role": "assistant", "content": response})
                 except Exception as e:
                     st.error(f"Error: {e}")

