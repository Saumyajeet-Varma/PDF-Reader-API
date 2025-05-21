import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import pdfplumber

load_dotenv()

app = Flask(__name__)

# CORS(app, resources={r"/api/*": {"origins": "http://localhost:5500"}}, supports_credentials=True)
# CORS(app, origins="http://localhost:5500", methods=["GET", "POST"], allow_headers=["Content-Type"])
CORS(app, origins=["http://localhost:5500"])
# CORS(app, origins=[os.getenv("CORS_ORIGIN")])

pdf_text = ""

app.config['UPLOAD_FOLDER'] = 'static/uploads'

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return "Hello World"

@app.route('/api/v1/extract-text', methods=['POST'])
def extract_text():

    global pdf_text

    print(request.files)
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

    pdf_text = ""

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            pdf_text += page.extract_text()

    return jsonify({"success": True, "message": "Text extracted successfully", "text": pdf_text}), 200

@app.route('/api/v1/get-text', methods=['GET'])
def get_text():

    global pdf_text

    if pdf_text == "":
        return jsonify({"success": False, "message": "No data to store", "text": pdf_text}), 400

    return jsonify({"success": True, "message": "Text fetched successfully", "text": pdf_text}), 200

@app.route('/api/v1/store-text', methods=['POST'])
def store_text():

    if pdf_text == "":
        return jsonify({"success": False, "message": "No data to store", "text": pdf_text}), 400
    
    return jsonify({"success": True, "message": "Stored", "text": pdf_text}), 200

if __name__ == "__main__":
    app.run(debug=True)