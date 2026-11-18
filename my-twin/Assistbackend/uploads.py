"""File and image uploads (section 12 of README1).

Bytes live on local disk (Assistbackend/uploads/<uid>/, git-ignored) because
Firestore documents are capped at 1 MiB; Firestore `uploads` holds metadata.
The frontend sends `upload_ids` with the next message and the blocks go before
the user's text. Extracted text is also indexed into memory (`chunks`) so later
chats can find it without resending the file.
"""
import base64
import io
import os
import threading
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from auth_utils import require_auth
from ratelimit import rate_limited
from services import db

uploads_bp = Blueprint("uploads", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
MAX_BYTES = 20 * 1024 * 1024
MAX_IMAGE_BYTES = 3_750_000          # stays under the API's 5 MB base64 image limit
MAX_PDF_PAGES_AS_DOCUMENT = 100      # bigger PDFs are sent as extracted text
MAX_TEXT_CHARS = 400_000

IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".webp": "image/webp", ".gif": "image/gif"}
TEXT_EXTS = {".txt", ".md", ".csv", ".json", ".py", ".js", ".jsx", ".ts", ".tsx", ".html",
             ".css", ".java", ".c", ".cpp", ".sql", ".yaml", ".yml", ".xml", ".log"}
ALLOWED = set(IMAGE_TYPES) | TEXT_EXTS | {".pdf", ".docx"}


def _b64(data):
    return base64.standard_b64encode(data).decode("ascii")


def _shrink_image(data):
    """Downscale large images so they fit the API image limit."""
    from PIL import Image
    img = Image.open(io.BytesIO(data))
    img.thumbnail((2000, 2000))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue(), "image/jpeg"


def _pdf_text(data):
    import pdfplumber
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = len(pdf.pages)
        text = "\n\n".join((p.extract_text() or "") for p in pdf.pages)
    return pages, text


def _docx_text(data):
    import docx
    doc = docx.Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(c.text for c in row.cells))
    return "\n".join(parts)


def _user_dir(user_id):
    path = os.path.join(UPLOAD_DIR, "".join(ch for ch in user_id if ch.isalnum() or ch in "-_"))
    os.makedirs(path, exist_ok=True)
    return path


def _text_block(name, text):
    note = ""
    if len(text) > MAX_TEXT_CHARS:
        note = f"\n[Only the first {MAX_TEXT_CHARS} characters of {len(text)} are included.]"
        text = text[:MAX_TEXT_CHARS]
    safe_name = name.replace('"', "'")
    return {"type": "text", "text": f'<file name="{safe_name}">\n{text}{note}\n</file>'}


@uploads_bp.route("/api/upload", methods=["POST"])
@require_auth
@rate_limited("upload")
def upload():
    user_id = request.user["uid"]
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "No file provided"}), 400
    name = os.path.basename(f.filename)
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED:
        return jsonify({"error": f"Unsupported file type {ext or '(none)'}"}), 400
    data = f.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        return jsonify({"error": "File is larger than 20 MB"}), 413
    if not data:
        return jsonify({"error": "File is empty"}), 400

    upload_id = uuid.uuid4().hex
    folder = _user_dir(user_id)
    meta = {"user_id": user_id, "name": name, "ext": ext, "size": len(data),
            "created_at": datetime.now(timezone.utc).isoformat()}
    text = None
    try:
        if ext in IMAGE_TYPES:
            media_type = IMAGE_TYPES[ext]
            if len(data) > MAX_IMAGE_BYTES:
                data, media_type = _shrink_image(data)
            meta.update(kind="image", media_type=media_type)
        elif ext == ".pdf":
            pages, text = _pdf_text(data)
            meta.update(kind="pdf" if pages <= MAX_PDF_PAGES_AS_DOCUMENT else "text",
                        media_type="application/pdf", pages=pages)
        elif ext == ".docx":
            text = _docx_text(data)
            meta.update(kind="text")
        else:
            text = data.decode("utf-8", errors="ignore")
            meta.update(kind="text")
    except Exception as e:
        return jsonify({"error": f"Could not read {name}: {e}"}), 400

    with open(os.path.join(folder, upload_id + ".bin"), "wb") as out:
        out.write(data)
    if text is not None:
        with open(os.path.join(folder, upload_id + ".txt"), "w", encoding="utf-8") as out:
            out.write(text)
    db().collection("uploads").document(upload_id).set(meta)

    if text and text.strip():
        conv_id = request.form.get("conversation_id") or f"user_{user_id}"
        threading.Thread(target=_index_upload, args=(user_id, conv_id, name, text), daemon=True).start()

    return jsonify({"upload_id": upload_id, "name": name, "kind": meta["kind"], "size": meta["size"]})


def _index_upload(user_id, conv_id, name, text):
    try:
        import memory
        memory.index_chunk(user_id, conv_id, text[:200_000], kind="upload", title=name)
    except Exception as e:
        print(f"Upload indexing failed: {e}")


def load_upload_blocks(user_id, upload_ids):
    """Content blocks for the given uploads (only the caller's own files)."""
    blocks, names = [], []
    for upload_id in (upload_ids or [])[:10]:
        if not isinstance(upload_id, str) or not upload_id.isalnum():
            continue
        try:
            snap = db().collection("uploads").document(upload_id).get()
        except Exception as e:
            print(f"Upload lookup failed: {e}")
            continue
        meta = snap.to_dict() if snap.exists else None
        if not meta or meta.get("user_id") != user_id:
            continue
        folder = _user_dir(user_id)
        try:
            if meta["kind"] in ("image", "pdf"):
                with open(os.path.join(folder, upload_id + ".bin"), "rb") as fh:
                    data = fh.read()
                block_type = "image" if meta["kind"] == "image" else "document"
                blocks.append({"type": block_type, "source": {
                    "type": "base64", "media_type": meta["media_type"], "data": _b64(data)}})
            else:
                with open(os.path.join(folder, upload_id + ".txt"), encoding="utf-8") as fh:
                    blocks.append(_text_block(meta["name"], fh.read()))
            names.append(meta["name"])
        except FileNotFoundError:
            print(f"Upload {upload_id} missing on disk")
    return blocks, names


def load_upload_text(user_id, upload_id):
    """Plain text of an upload (for grading pipelines)."""
    blocks, _ = load_upload_blocks(user_id, [upload_id])
    if not blocks:
        return None
    if blocks[0]["type"] == "text":
        return blocks[0]["text"]
    folder = _user_dir(user_id)
    path = os.path.join(folder, upload_id + ".txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    return None
