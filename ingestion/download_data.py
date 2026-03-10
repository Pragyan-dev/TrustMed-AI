"""
ROCO Medical Image Dataset Downloader

Downloads medical images from the ROCO dataset using HuggingFace parquet files.
Dataset: https://huggingface.co/datasets/MedIR/roco
"""

import os
import io
import pandas as pd
from PIL import Image

# =============================================================================
# Configuration
# =============================================================================

OUTPUT_DIR = "data/medical_images"
NUM_IMAGES = 50  # Set to None to download all images

# HuggingFace dataset path
DATASET_URL = "hf://datasets/MedIR/roco/data/test-00000-of-00001-1ca3285a8d47f6c4.parquet"

# =============================================================================
# Main Download Function
# =============================================================================

def download_roco_dataset(output_dir: str = OUTPUT_DIR, num_images: int = NUM_IMAGES):
    """
    Download ROCO medical images from HuggingFace parquet file.
    
    Args:
        output_dir: Directory to save images
        num_images: Number of images to download (None for all)
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    print("=" * 60)
    print("🏥 ROCO Medical Image Dataset Downloader")
    print("=" * 60)
    print(f"\n⬇️  Loading ROCO dataset from parquet...")
    print(f"📁 Output directory: {os.path.abspath(output_dir)}")
    
    if num_images:
        print(f"🔢 Downloading {num_images} images")
    else:
        print("🔢 Downloading ALL images")
    
    print()
    
    # Load dataset from parquet
    try:
        print("📦 Reading parquet file (this may take a moment)...")
        df = pd.read_parquet(DATASET_URL)
        print(f"✅ Loaded {len(df)} records from dataset")
        
        # Limit if specified
        if num_images and num_images < len(df):
            df = df.head(num_images)
            print(f"📋 Processing first {num_images} images")
        
    except Exception as e:
        print(f"❌ Failed to load dataset: {e}")
        print("\nMake sure you have pyarrow installed:")
        print("  pip install pyarrow")
        print("\nIf authentication is needed, run:")
        print("  huggingface-cli login")
        return
    
    # Save images to disk
    count = 0
    errors = 0
    
    print()
    for idx, row in df.iterrows():
        try:
            # Get image data and caption
            image_data = row.get('image', None)
            caption = row.get('caption', '')
            
            if image_data is None:
                print(f"⚠️ No image data for row {idx}")
                continue
            
            # Handle different image formats
            if isinstance(image_data, dict) and 'bytes' in image_data:
                # Image stored as bytes in dict
                image_bytes = image_data['bytes']
                image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            elif isinstance(image_data, bytes):
                # Direct bytes
                image = Image.open(io.BytesIO(image_data)).convert("RGB")
            elif isinstance(image_data, Image.Image):
                # Already a PIL Image
                image = image_data.convert("RGB")
            else:
                print(f"⚠️ Unknown image format for row {idx}: {type(image_data)}")
                continue
            
            # Create filename
            filename = f"roco_{idx:04d}.jpg"
            filepath = os.path.join(output_dir, filename)
            
            # Save image
            image.save(filepath, "JPEG", quality=95)
            
            # Save caption as metadata
            if caption:
                caption_path = filepath.replace(".jpg", ".txt")
                with open(caption_path, "w") as f:
                    f.write(str(caption))
            
            # Truncate caption for display
            caption_preview = str(caption)[:50] + "..." if len(str(caption)) > 50 else str(caption)
            print(f"✅ Saved {filename}: {caption_preview}")
            count += 1
            
        except Exception as e:
            print(f"❌ Error processing row {idx}: {e}")
            errors += 1
    
    # Summary
    print()
    print("=" * 60)
    print(f"🎉 Download Complete!")
    print(f"   ✅ {count} images saved to '{output_dir}/'")
    if errors:
        print(f"   ❌ {errors} errors encountered")
    print("=" * 60)
    
    # Next steps
    print("\n📋 Next Steps:")
    print("   1. Review downloaded images in the folder")
    print("   2. Run ingestion to embed into ChromaDB:")
    print(f"      python ingestion/ingest_images.py")
    print()
    
    return count


# =============================================================================
# Main Execution
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Download ROCO medical images")
    parser.add_argument(
        "--num", "-n", 
        type=int, 
        default=NUM_IMAGES,
        help="Number of images to download (default: 50, use 0 for all)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=OUTPUT_DIR,
        help="Output directory (default: data/medical_images)"
    )
    parser.add_argument(
        "--test-split", "-t",
        type=float,
        default=0.0,
        help="Percentage of images to put in test set (e.g., 0.1 for 10%%)"
    )
    parser.add_argument(
        "--test-output",
        type=str,
        default="data/medical_images_test",
        help="Output directory for test images"
    )
    
    args = parser.parse_args()
    
    # Handle 0 as "all"
    num = args.num if args.num > 0 else None
    
    if args.test_split > 0:
        # Download with train/test split
        import random
        
        total_images = num if num else 8176  # Full dataset size
        test_count = int(total_images * args.test_split)
        train_count = total_images - test_count
        
        print(f"📊 Splitting: {train_count} train / {test_count} test images")
        
        # Download training set
        print(f"\n📥 Downloading TRAINING set ({train_count} images)...")
        train_downloaded = download_roco_dataset(
            output_dir=args.output, 
            num_images=train_count
        )
        
        # Download test set (skip the training images)
        print(f"\n📥 Downloading TEST set ({test_count} images)...")
        # For test set, we need to skip the first train_count images
        # Reload dataset and skip
        os.makedirs(args.test_output, exist_ok=True)
        
        try:
            df = pd.read_parquet(DATASET_URL)
            # Skip training images, take test images
            test_df = df.iloc[train_count:train_count + test_count]
            
            test_count_actual = 0
            for idx, row in test_df.iterrows():
                try:
                    image_data = row.get('image', None)
                    caption = row.get('caption', '')
                    
                    if image_data is None:
                        continue
                    
                    if isinstance(image_data, dict) and 'bytes' in image_data:
                        image_bytes = image_data['bytes']
                        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                    elif isinstance(image_data, bytes):
                        image = Image.open(io.BytesIO(image_data)).convert("RGB")
                    elif isinstance(image_data, Image.Image):
                        image = image_data.convert("RGB")
                    else:
                        continue
                    
                    filename = f"test_{idx:04d}.jpg"
                    filepath = os.path.join(args.test_output, filename)
                    image.save(filepath, "JPEG", quality=95)
                    
                    if caption:
                        caption_path = filepath.replace(".jpg", ".txt")
                        with open(caption_path, "w") as f:
                            f.write(str(caption))
                    
                    print(f"✅ Saved {filename}")
                    test_count_actual += 1
                    
                except Exception as e:
                    print(f"❌ Error: {e}")
            
            print(f"\n🎉 Test set complete: {test_count_actual} images in '{args.test_output}/'")
            
        except Exception as e:
            print(f"❌ Failed to create test set: {e}")
    else:
        download_roco_dataset(output_dir=args.output, num_images=num)
