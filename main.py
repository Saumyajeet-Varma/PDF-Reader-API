import os
from flask import Flask, jsonify, request, session
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import pdfplumber

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
        return jsonify({"success": False, "message": "No data to store", "text": pdf_text}), 400
    
    # TODO: Logic to store data in DB


    
    
    delete_files()

    session.pop('pdf_text', None)
    session.pop('filename', None)
    
    return jsonify({"success": True, "message": "Stored", "text": pdf_text}), 200

if __name__ == "__main__":
    app.run(debug=True)