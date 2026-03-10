"""
Medical Image Ingestion Script

Ingests medical images into ChromaDB using BiomedCLIP embeddings
for multimodal semantic search capabilities.
"""

import os
import io
import sys
import tempfile
import torch
import requests
import chromadb
from PIL import Image
from dotenv import load_dotenv

# Add project root to path for subfigure detector
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.subfigure_detector import detect_compound_figure, split_compound_figure
    COMPOUND_DETECTION_AVAILABLE = True
except ImportError:
    COMPOUND_DETECTION_AVAILABLE = False
    print("⚠️ subfigure_detector not available. Compound figure detection disabled.")

load_dotenv()

# =============================================================================
# Configuration
# =============================================================================

CHROMA_DB_DIR = "./data/chroma_db"
COLLECTION_NAME = "medical_images"

# BiomedCLIP model via open_clip
MODEL_NAME = "hf-hub:microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224"

# Get HuggingFace token
HF_TOKEN = os.getenv("HF_TOKEN")

# Sample test images
TEST_IMAGES = []

# =============================================================================
# Hardware Detection
# =============================================================================

def get_device():
    """Detect the best available hardware acceleration."""
    if torch.backends.mps.is_available():
        print("🖥️ Using Apple MPS (Metal Performance Shaders)")
        return torch.device("mps")
    elif torch.cuda.is_available():
        print("🖥️ Using NVIDIA CUDA")
        return torch.device("cuda")
    else:
        print("🖥️ Using CPU")
        return torch.device("cpu")


# =============================================================================
# Model Initialization
# =============================================================================

_model = None
_preprocess = None
_tokenizer = None
_device = None


def load_model():
    """Lazily load the BiomedCLIP model via open_clip."""
    global _model, _preprocess, _tokenizer, _device
    
    if _model is None:
        print(f"📦 Loading model: {MODEL_NAME}")
        _device = get_device()
        
        import open_clip
        
        # Set HF token for authentication
        if HF_TOKEN:
            os.environ["HF_TOKEN"] = HF_TOKEN
        
        _model, _preprocess = open_clip.create_model_from_pretrained(MODEL_NAME)
        _tokenizer = open_clip.get_tokenizer(MODEL_NAME)
        
        _model.to(_device)
        _model.eval()
        
        print("✅ Model loaded successfully!")
    
    return _model, _preprocess, _tokenizer, _device


# =============================================================================
# Embedding Function
# =============================================================================

def embed_image(image_path: str) -> list:
    """
    Generate embedding for a medical image using BiomedCLIP.
    
    Args:
        image_path: Path to the image file or URL
        
    Returns:
        Embedding as a flat Python list
    """
    model, preprocess, tokenizer, device = load_model()
    
    # Load image
    if image_path.startswith("http"):
        response = requests.get(image_path, timeout=30)
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
    else:
        image = Image.open(image_path).convert("RGB")
    
    # Preprocess image using open_clip's preprocess function
    image_tensor = preprocess(image).unsqueeze(0).to(device)
    
    # Generate embedding
    with torch.no_grad():
        image_features = model.encode_image(image_tensor)
        # Normalize features
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
    
    # Convert to list
    embedding = image_features.squeeze().cpu().numpy().tolist()
    
    return embedding


def embed_text(text: str) -> list:
    """
    Generate embedding for text using BiomedCLIP.
    Useful for text-to-image search.
    
    Args:
        text: Text query
        
    Returns:
        Embedding as a flat Python list
    """
    model, preprocess, tokenizer, device = load_model()
    
    # Tokenize text
    text_tokens = tokenizer([text]).to(device)
    
    # Generate embedding
    with torch.no_grad():
        text_features = model.encode_text(text_tokens)
        # Normalize features
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
    
    # Convert to list
    embedding = text_features.squeeze().cpu().numpy().tolist()
    
    return embedding


# =============================================================================
# ChromaDB Setup
# =============================================================================

def get_collection():
    """Get or create the medical images collection."""
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}  # Use cosine similarity
    )
    
    return collection


# =============================================================================
# Ingestion Functions
# =============================================================================

def ingest_image(image_path: str, modality: str = "X-ray", metadata: dict = None,
                  detect_compound: bool = True):
    """
    Ingest a single image into the ChromaDB collection.

    If compound figure detection is enabled and the image contains multiple
    panels (e.g., A/B/C/D), each panel is also stored individually for
    better retrieval quality.

    Args:
        image_path: Path to the image file or URL
        modality: Image modality (X-ray, MRI, CT, etc.)
        metadata: Additional metadata to store
        detect_compound: Whether to check for compound figures (default: True)
    """
    collection = get_collection()

    # Prepare base metadata
    filename = os.path.basename(image_path) if not image_path.startswith("http") else image_path.split("/")[-1]
    doc_id = filename.replace(".", "_").replace("/", "_")

    meta = {
        "modality": modality,
        "source": "BiomedCLIP",
        "filename": filename,
        "path": image_path,
        "is_compound": False,
        "is_subfigure": False,
    }
    if metadata:
        meta.update(metadata)

    # Check for compound figures
    if (detect_compound and COMPOUND_DETECTION_AVAILABLE
            and not image_path.startswith("http")):
        try:
            analysis = detect_compound_figure(image_path)

            if analysis.is_compound and analysis.confidence >= 0.5:
                print(f"📊 Compound figure: {analysis.num_panels} panels detected in {filename}")

                # Update parent metadata
                meta["is_compound"] = True
                meta["num_panels"] = analysis.num_panels
                meta["grid_layout"] = f"{analysis.grid_structure[0]}x{analysis.grid_structure[1]}"
                meta["panel_labels"] = ",".join(analysis.detected_labels)

                # Ingest the parent (full image)
                print(f"🔄 Processing parent: {image_path}")
                embedding = embed_image(image_path)
                collection.upsert(
                    ids=[doc_id],
                    embeddings=[embedding],
                    metadatas=[meta]
                )
                print(f"✅ Ingested parent [{filename}]")

                # Ingest each subfigure
                subfigures = split_compound_figure(image_path)
                for sf in subfigures:
                    subfig_id = f"{doc_id}_panel_{sf.panel_id}"
                    temp_path = os.path.join(
                        tempfile.gettempdir(),
                        f"trustmed_ingest_{sf.panel_id}.jpg"
                    )

                    try:
                        sf.image.save(temp_path, "JPEG", quality=95)
                        subfig_embedding = embed_image(temp_path)

                        subfig_meta = {
                            "modality": modality,
                            "source": "BiomedCLIP",
                            "filename": f"{filename}_panel_{sf.panel_id}",
                            "path": image_path,
                            "is_compound": False,
                            "is_subfigure": True,
                            "parent_id": doc_id,
                            "panel_label": sf.panel_id,
                            "grid_position": f"{sf.grid_position[0]},{sf.grid_position[1]}",
                        }
                        if metadata:
                            # Inherit non-compound metadata from parent
                            for k, v in metadata.items():
                                if k not in subfig_meta:
                                    subfig_meta[k] = v

                        collection.upsert(
                            ids=[subfig_id],
                            embeddings=[subfig_embedding],
                            metadatas=[subfig_meta]
                        )
                        print(f"  ✅ Panel {sf.panel_id} ingested")

                    finally:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)

                return  # Done — parent + subfigures all ingested

        except Exception as e:
            print(f"⚠️ Compound detection failed for {filename}: {e}. Ingesting as single image.")

    # Standard single-image ingestion
    print(f"🔄 Processing: {image_path}")
    embedding = embed_image(image_path)

    collection.upsert(
        ids=[doc_id],
        embeddings=[embedding],
        metadatas=[meta]
    )

    print(f"✅ Ingested [{filename}] into {COLLECTION_NAME} collection")


def ingest_directory(directory: str, modality: str = "X-ray"):
    """
    Ingest all images from a directory.
    
    Args:
        directory: Path to the directory containing images
        modality: Default modality for all images
    """
    valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
    
    for filename in os.listdir(directory):
        ext = os.path.splitext(filename)[1].lower()
        if ext in valid_extensions:
            image_path = os.path.join(directory, filename)
            ingest_image(image_path, modality=modality)


def search_similar_images(query_image_path: str, n_results: int = 5):
    """
    Find similar images in the collection.
    
    Args:
        query_image_path: Path to query image
        n_results: Number of results to return
        
    Returns:
        List of similar images with metadata
    """
    collection = get_collection()
    
    # Generate query embedding
    query_embedding = embed_image(query_image_path)
    
    # Search
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )
    
    return results


def search_by_text(query: str, n_results: int = 5):
    """
    Find images matching a text description.
    
    Args:
        query: Text description (e.g., "chest X-ray with pneumonia")
        n_results: Number of results to return
        
    Returns:
        List of matching images with metadata
    """
    collection = get_collection()
    
    # Generate text embedding
    query_embedding = embed_text(query)
    
    # Search
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )
    
    return results


# =============================================================================
# Main Execution
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🏥 Medical Image Ingestion - BiomedCLIP")
    print("=" * 60)
    
    # Default directory with downloaded images
    images_dir = "data/medical_images"
    
    # Check if directory exists and has images
    if os.path.exists(images_dir):
        valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
        image_files = [f for f in os.listdir(images_dir) 
                       if os.path.splitext(f)[1].lower() in valid_extensions]
        
        if image_files:
            print(f"\n📂 Found {len(image_files)} images in {images_dir}")
            print("🔄 Starting ingestion...\n")
            
            for filename in image_files:
                image_path = os.path.join(images_dir, filename)
                
                # Try to get modality from caption file
                caption_path = image_path.rsplit(".", 1)[0] + ".txt"
                if os.path.exists(caption_path):
                    with open(caption_path, "r") as f:
                        caption = f.read().strip()
                    # Detect modality from caption
                    caption_lower = caption.lower()
                    if "mri" in caption_lower or "magnetic resonance" in caption_lower:
                        modality = "MRI"
                    elif "ct" in caption_lower or "computed tomography" in caption_lower:
                        modality = "CT"
                    elif "x-ray" in caption_lower or "xray" in caption_lower or "radiograph" in caption_lower:
                        modality = "X-ray"
                    elif "ultrasound" in caption_lower or "sonograph" in caption_lower:
                        modality = "Ultrasound"
                    else:
                        modality = "Medical"
                else:
                    modality = "Medical"
                    caption = ""
                
                try:
                    ingest_image(image_path, modality=modality, metadata={"caption": caption})
                except Exception as e:
                    print(f"❌ Failed to process {filename}: {e}")
            
            # Show collection stats
            collection = get_collection()
            print(f"\n📊 Collection '{COLLECTION_NAME}' now has {collection.count()} images")
        else:
            print(f"\n⚠️ No image files found in {images_dir}")
            print("Run the download script first:")
            print("  python ingestion/download_data.py")
    else:
        print(f"\n⚠️ Directory not found: {images_dir}")
        print("Run the download script first:")
        print("  python ingestion/download_data.py")
    
    print("=" * 60)
