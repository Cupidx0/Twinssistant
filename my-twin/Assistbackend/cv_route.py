from flask import Blueprint, request, jsonify
import os, re, json, anthropic, pdfplumber
from werkzeug.utils import secure_filename
from docx import Document

cv_bp = Blueprint('cv', __name__)

CV_DIR = "cv_docs"
os.makedirs(CV_DIR, exist_ok=True)

def clean_text(text):
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()

def extract_pdf(path):
    with pdfplumber.open(path) as pdf:
        return clean_text("\n".join(
            p.extract_text() for p in pdf.pages if p.extract_text()
        ))

def extract_docx(path):
    doc = Document(path)
    return clean_text("\n".join(
        p.text for p in doc.paragraphs if p.text.strip()
    ))

def get_cv():
    files = sorted(f for f in os.listdir(CV_DIR) if f.endswith(".txt"))
    if not files:
        return ""
    with open(os.path.join(CV_DIR, files[-1]), "r") as f:
        return f.read().strip()

@cv_bp.route('/cv/upload', methods=['POST'])
def upload():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file"}), 400

    filename = secure_filename(file.filename)
    temp = os.path.join(CV_DIR, filename)
    file.save(temp)

    if filename.endswith(".pdf"):
        text = extract_pdf(temp)
    elif filename.endswith((".docx", ".doc")):
        text = extract_docx(temp)
    else:
        os.remove(temp)
        return jsonify({"error": "PDF or DOCX only"}), 400

    os.remove(temp)
    saved = os.path.join(CV_DIR, filename.rsplit('.', 1)[0] + ".txt")
    with open(saved, "w") as f:
        f.write(text)

    return jsonify({"message": "CV uploaded", "preview": text[:300]})


@cv_bp.route('/cv/review', methods=['POST'])
def review():
    cv_text = get_cv()
    if not cv_text:
        return jsonify({"error": "No CV found"}), 400

    target = request.json.get("target_role", "tech/developer roles")
    client = anthropic.Anthropic()

    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": f"""
                   Review this CV for {target}. Return JSON only:
                   {{
                        "score": 1-10,
                        "strengths": ["max 3"],
                        "weaknesses": ["max 3"],
                        "missing": ["missing sections"],
                        "summary": "2 sentence verdict"
                    }}

                    CV:
                    {cv_text[:3000]}"""}]
                        )

    return jsonify(json.loads(msg.content[0].text))


@cv_bp.route('/cv/rewrite', methods=['POST'])
def rewrite():
    cv_text = get_cv()
    if not cv_text:
        return jsonify({"error": "No CV found"}), 400

    target = request.json.get("target_role", "tech/developer roles")
    client = anthropic.Anthropic()

    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": f"""
                   Rewrite this CV for {target}.
                    - Keep all real experience
                    - Achievement-focused bullet points
                    - Strong action verbs
                    - Remove filler
                    Return plain text only, ready to copy.

                    CV:
                    {cv_text[:3000]}"""}]
                        )
    return jsonify({"rewritten_cv": msg.content[0].text})