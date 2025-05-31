import os
from flask import Flask, jsonify, request, session
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import pdfplumber
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

load_dotenv()

app = Flask(__name__)

CORS(app, origins=[os.getenv("CORS_ORIGIN")])

app.secret_key = os.getenv("SECRET_KEY")
app.config['UPLOAD_FOLDER'] = 'static/uploads'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///documents.db'
db = SQLAlchemy(app)

model = SentenceTransformer(os.getenv("MODEL"))

ALLOWED_EXTENSIONS = {'pdf'}

# ---------- Models ----------
class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(120), unique=True, nullable=False)
    index_path = db.Column(db.String(120), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class TextChunk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    chunk = db.Column(db.Text, nullable=False)

with app.app_context():
    db.create_all()

# ---------- Utils ----------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def delete_files():
    folder = app.config['UPLOAD_FOLDER']
    for filename in os.listdir(folder):
        if filename == '.gitkeep':
            continue
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")

def chunk_text(text, chunk_size=500, overlap=100):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks

def embed_chunks(chunks, model):
    return model.encode(chunks, show_progress_bar=True)

def build_faiss_index(embeddings):
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    return index

# ---------- Routes ----------
@app.route('/')
def index():
    return "Hello World"

@app.route('/api/v1/extract-text', methods=['POST'])
def extract_text():

    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file part"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"success": False, "message": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"success": False, "message": "Only PDF files allowed"}), 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    extracted_text = ""

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                extracted_text += text

    session['pdf_text'] = extracted_text
    session['filename'] = filename

    return jsonify({"success": True, "message": "Text extracted successfully", "text": extracted_text, "filename": filename}), 200

@app.route('/api/v1/get-text', methods=['GET'])
def get_text():

    pdf_text = session.get('pdf_text', '')

    if pdf_text == "":
        return jsonify({"success": False, "message": "No data to store", "text": pdf_text}), 400

    return jsonify({"success": True, "message": "Text fetched successfully", "text": pdf_text}), 200

@app.route('/api/v1/store-text', methods=['POST'])
def store_text():

    pdf_text = session.get('pdf_text', '')
    filename = session.get('filename', '')

    base_filename = filename.split('.')[0]

    print(filename)

    if pdf_text == "":
        delete_files()
        return jsonify({"success": False, "message": "No data to store", "text": pdf_text}), 400
    
    chunks = chunk_text(pdf_text)
    embeddings = embed_chunks(chunks, model)
    embeddings_np = np.array(embeddings).astype("float32")

    index = build_faiss_index(embeddings_np)
    index_path = f"{base_filename}_faiss.index"
    faiss.write_index(index, index_path)

    document = Document(filename=filename, index_path=index_path)
    db.session.add(document)
    db.session.commit()

    for chunk in chunks:
        db.session.add(TextChunk(document_id=document.id, chunk=chunk))
    db.session.commit()
    
    delete_files()

    session.pop('pdf_text', None)
    session.pop('filename', None)
    
    return jsonify({"success": True, "message": "Stored in DB and indexed", "text": pdf_text}), 200

@app.route('/api/v1/search', methods=['POST'])
def search():

    data = request.get_json()
    query = data.get('query', '')
    filename = data.get('filename', '')

    if not query or not filename:
        return jsonify({"success": False, "message": "Query and filename required"}), 400
    
    document = Document.query.filter_by(filename=filename).first()

    if not document:
        return jsonify({"success": False, "message": "Document not found"}), 404
    
    # TODO: Logic For searching
    results = None

    return jsonify({"success": True, "message": "Search complete", "results": results}), 200

if __name__ == "__main__":
    app.run(debug=True)