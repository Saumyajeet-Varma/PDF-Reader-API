import os
from flask import Flask, jsonify, request, session
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import pdfplumber
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss

load_dotenv()

app = Flask(__name__)

CORS(app, origins=[os.getenv("CORS_ORIGIN")])

app.secret_key = os.getenv("SECRET_KEY")
app.config['UPLOAD_FOLDER'] = 'static/uploads'

ALLOWED_EXTENSIONS = {'pdf'}

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

    if pdf_text == "":
        delete_files()
        return jsonify({"success": False, "message": "No data to store", "text": pdf_text}), 400
    
    # Step 1: Chunk the text
    chunks = chunk_text(pdf_text)

    # Step 2: Load embedding model
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Step 3: Embed chunks
    embeddings = embed_chunks(chunks, model)
    embeddings_np = np.array(embeddings).astype("float32")

    # Step 4: Create FAISS index
    index = build_faiss_index(embeddings_np)

    # Step 5: Save index to disk
    faiss.write_index(index, "faiss_index.index")
    
    delete_files()

    session.pop('pdf_text', None)
    session.pop('filename', None)
    
    return jsonify({"success": True, "message": "Stored", "text": pdf_text}), 200

if __name__ == "__main__":
    app.run(debug=True)