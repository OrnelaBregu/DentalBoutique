"""Document ingestion for text + images into Chroma collections."""
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import chromadb
import numpy as np
from PIL import Image
from llama_index.core import Document, SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.core.settings import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from sentence_transformers import SentenceTransformer

from config import (
    DOCUMENTS_PATH,
    EXTRACTED_IMAGES_DIR,
    IMAGE_EMBEDDING_MODEL,
    LOCAL_EMBEDDING_MODEL,
    MODEL_CACHE_DIR,
    VECTOR_STORE_PATH,
)

TEXT_COLLECTION_NAME = "dental_boutique_text"
IMAGE_COLLECTION_NAME = "dental_boutique_images"
COMPANY_DOCS_GLOBS = ("company_*.md", "company_*.docx")
IMAGE_TOPIC_LABELS = [
    "dental implant",
    "root canal",
    "teeth whitening",
    "invisalign",
    "dental crown",
    "dental bridge",
    "dental veneers",
    "tooth extraction",
    "dentures",
    "teeth cleaning",
    "dental filling",
]


def _company_doc_paths() -> list[Path]:
    """Paths to company docs under DOCUMENTS_PATH."""
    root = Path(DOCUMENTS_PATH)
    if not root.is_dir():
        return []
    paths: list[Path] = []
    for pattern in COMPANY_DOCS_GLOBS:
        for p in root.glob(pattern):
            if p.is_file():
                paths.append(p.resolve())
    return sorted(set(paths))


def _extract_text_from_docx(docx_path: Path) -> str:
    """Extract plain text from a .docx using XML paragraphs."""
    with zipfile.ZipFile(docx_path, "r") as docx_zip:
        xml_bytes = docx_zip.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for p in root.findall(".//w:p", namespace):
        text_parts = [t.text for t in p.findall(".//w:t", namespace) if t.text]
        if text_parts:
            paragraphs.append("".join(text_parts))
    return "\n".join(paragraphs).strip()


def _extract_images_from_docx(docx_path: Path, image_output_dir: Path) -> list[dict[str, Any]]:
    """Extract images from a docx into static/indexed_images and return metadata."""
    image_output_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[dict[str, Any]] = []
    with zipfile.ZipFile(docx_path, "r") as docx_zip:
        media_files = sorted(
            [name for name in docx_zip.namelist() if name.startswith("word/media/")]
        )
        for idx, media_name in enumerate(media_files, start=1):
            ext = Path(media_name).suffix.lower() or ".png"
            filename = f"{docx_path.stem}_image_{idx}{ext}"
            output_path = image_output_dir / filename
            with docx_zip.open(media_name) as src, open(output_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted.append(
                {
                    "file_path": str(output_path.resolve()),
                    "url": f"/static/indexed_images/{filename}",
                    "source_doc": docx_path.name,
                    "image_name": filename,
                }
            )
    return extracted


def _clear_extracted_images_dir(image_output_dir: Path) -> None:
    """Remove old extracted images so each ingestion run reflects latest docs."""
    image_output_dir.mkdir(parents=True, exist_ok=True)
    for p in image_output_dir.glob("*"):
        if p.is_file():
            p.unlink()


def _load_documents(doc_paths: list[Path], image_output_dir: Path) -> tuple[list[Document], list[dict[str, Any]]]:
    """Load text documents and extract document images."""
    md_paths = [str(p) for p in doc_paths if p.suffix.lower() == ".md"]
    docx_paths = [p for p in doc_paths if p.suffix.lower() == ".docx"]

    documents: list[Document] = []
    if md_paths:
        reader = SimpleDirectoryReader(input_files=md_paths)
        documents.extend(reader.load_data())

    image_assets: list[dict[str, Any]] = []
    for docx_path in docx_paths:
        text = _extract_text_from_docx(docx_path)
        if text:
            documents.append(
                Document(
                    text=text,
                    metadata={
                        "file_name": docx_path.name,
                        "source": str(docx_path),
                        "doc_type": "docx",
                    },
                )
            )
        image_assets.extend(_extract_images_from_docx(docx_path, image_output_dir))
    return documents, image_assets


def _recreate_collection(client: chromadb.PersistentClient, name: str, metadata: dict[str, Any]) -> Any:
    """Drop existing collection (if any), then create a fresh one."""
    try:
        client.delete_collection(name=name)
    except Exception:
        pass
    return client.get_or_create_collection(name=name, metadata=metadata)


def run_ingestion() -> None:
    """Rebuild text and image embeddings from latest company documents."""
    print(f"Using text embedding model: {LOCAL_EMBEDDING_MODEL}")
    print(f"Using image embedding model: {IMAGE_EMBEDDING_MODEL}")

    doc_paths = _company_doc_paths()
    if not doc_paths:
        patterns = ", ".join(COMPANY_DOCS_GLOBS)
        raise FileNotFoundError(f"No files matching [{patterns}] found in {DOCUMENTS_PATH}")

    image_output_dir = Path(EXTRACTED_IMAGES_DIR)
    _clear_extracted_images_dir(image_output_dir)
    documents, image_assets = _load_documents(doc_paths, image_output_dir)
    image_assets = []  # image indexing temporarily disabled
    if not documents and not image_assets:
        raise ValueError("No text or image content loaded. Check document files.")

    os.makedirs(VECTOR_STORE_PATH, exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)

    text_collection = _recreate_collection(
        client=chroma_client,
        name=TEXT_COLLECTION_NAME,
        metadata={"description": "DentalBoutique text knowledge base"},
    )
    image_collection = _recreate_collection(
        client=chroma_client,
        name=IMAGE_COLLECTION_NAME,
        metadata={
            "description": "DentalBoutique extracted document images",
            "hnsw:space": "cosine",
        },
    )

    if documents:
        vector_store = ChromaVectorStore(chroma_collection=text_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        Settings.embed_model = HuggingFaceEmbedding(
            model_name=LOCAL_EMBEDDING_MODEL,
            cache_folder=MODEL_CACHE_DIR,
        )
        node_parser = MarkdownNodeParser()
        nodes = node_parser.get_nodes_from_documents(documents)
        print(f"Parsed {len(nodes)} text chunks from {len(documents)} documents.")
        VectorStoreIndex(nodes=nodes, storage_context=storage_context, show_progress=True)
    else:
        print("No text content found in documents; skipping text indexing.")

    if image_assets:
        image_model = SentenceTransformer(
            IMAGE_EMBEDDING_MODEL,
            cache_folder=MODEL_CACHE_DIR,
        )
        topic_embeddings = image_model.encode(
            IMAGE_TOPIC_LABELS,
            normalize_embeddings=True,
        )
        image_ids: list[str] = []
        embeddings: list[list[float]] = []
        metadatas: list[dict[str, Any]] = []
        documents_payload: list[str] = []

        for idx, asset in enumerate(image_assets, start=1):
            image = Image.open(asset["file_path"]).convert("RGB")
            embedding = image_model.encode(image, normalize_embeddings=True).tolist()
            embedding_np = np.asarray(embedding)
            topic_scores = topic_embeddings @ embedding_np
            best_topic_idx = int(np.argmax(topic_scores))
            best_topic = IMAGE_TOPIC_LABELS[best_topic_idx]
            best_topic_score = float(topic_scores[best_topic_idx])
            image_ids.append(f"img-{idx}")
            embeddings.append(embedding)
            metadatas.append(
                {
                    "url": asset["url"],
                    "source_doc": asset["source_doc"],
                    "image_name": asset["image_name"],
                    "topic_label": best_topic,
                    "topic_confidence": best_topic_score,
                }
            )
            documents_payload.append(
                f"Image extracted from {asset['source_doc']} ({asset['image_name']}); "
                f"predicted topic: {best_topic}"
            )

        image_collection.add(
            ids=image_ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents_payload,
        )
        print(f"Indexed {len(image_assets)} extracted images.")
    else:
        print("No images found in docs; skipping image indexing.")

    print(f"Ingestion complete. Vector store updated at {VECTOR_STORE_PATH}")


if __name__ == "__main__":
    run_ingestion()
