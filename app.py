from utils.generator import generate_answer
from utils.pdf_handler import extract_text_from_pdf
from utils.vector_store import store_documents, search
from utils.summarizer import summarize_text
from utils.preprocess import expand_text
from database import create_tables, connect_db
from flask import Flask, render_template, request, jsonify
import json
from utils.helper import find_best_match

app = Flask(__name__)

# ---------------- INIT ----------------
create_tables()

with open('data/data.json', 'r') as f:
    data = json.load(f)

questions = [item["question"] for item in data]


# ---------------- ROUTES ----------------
@app.route('/')
def home():
    return render_template('login.html')


@app.route('/login-page')
def login_page():
    return render_template('login.html')


@app.route('/chat-page')
def chat_page():
    return render_template('chat.html')


# ---------------- CHAT API ----------------
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data_req = request.json

        if not data_req or "message" not in data_req:
            return jsonify({"response": "Invalid request", "confidence": 0.0})

        user_input = data_req.get('message', '').lower()
        user_input = expand_text(user_input)

        username = data_req.get('username', 'guest')

        print("USER:", user_input)

        response = None
        score = 0.0

        clean_input = user_input.replace("?", "").strip()

        # ✅ PRIORITY KEYWORDS
        if "cnn" in clean_input:
            response = "CNN (Convolutional Neural Network) is used for image processing tasks like classification and object detection."
            score = 1.0

        elif "rnn" in clean_input:
            response = "RNN (Recurrent Neural Network) is used for sequential data such as text, speech, and time series."
            score = 1.0

        elif "machine learning" in clean_input or clean_input == "ml":
            response = "Machine learning is a field of AI where systems learn patterns from data."
            score = 1.0

        elif "deep learning" in clean_input or clean_input == "dl":
            response = "Deep learning is a subset of machine learning that uses neural networks with multiple layers."
            score = 1.0

        # ✅ EXACT MATCH
        if response is None:
            for item in data:
                if clean_input == item["question"]:
                    response = item["answer"]
                    score = 1.0
                    break

        # ✅ BERT MATCH
        if response is None:
            try:
                index, score = find_best_match(user_input, questions)

                if score > 0.7:
                    response = data[index]["answer"]
            except Exception as e:
                print("BERT ERROR:", e)

        # ✅ PDF SEARCH
        if response is None:
            try:
                pdf_text = search(user_input)

                if pdf_text and len(pdf_text.strip()) > 20:
                    response = summarize_text(pdf_text)
                else:
                    response = "No relevant information found in PDF."
            except Exception as e:
                print("PDF ERROR:", e)
                response = "PDF system not ready. Please upload a PDF."

        # ✅ FINAL SAFETY
        if response is None:
            response = "I couldn't understand your question."

        # ---------------- SAVE CHAT ----------------
        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO chats (username, message, response) VALUES (?, ?, ?)",
            (username, user_input, response)
        )

        conn.commit()
        conn.close()

        # ✅ ChatGPT-style response
        final_response = generate_answer(user_input, response)

        return jsonify({
            "response": final_response,
            "confidence": float(score)
        })

    except Exception as e:
        print("ERROR:", e)
        return jsonify({
            "response": "Server error occurred. Please try again.",
            "confidence": 0.0
        })


# ---------------- REGISTER ----------------
@app.route('/register', methods=['POST'])
def register():
    try:
        data_req = request.json
        username = data_req.get("username")
        password = data_req.get("password")

        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, password)
        )

        conn.commit()
        conn.close()

        return jsonify({"message": "User registered successfully"})

    except Exception as e:
        print("REGISTER ERROR:", e)
        return jsonify({"message": "Registration failed"})


# ---------------- LOGIN ----------------
@app.route('/login', methods=['POST'])
def login():
    try:
        data_req = request.json
        username = data_req.get("username")
        password = data_req.get("password")

        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        )

        user = cursor.fetchone()
        conn.close()

        if user:
            return jsonify({"message": "Login successful"})
        else:
            return jsonify({"message": "Invalid credentials"})

    except Exception as e:
        print("LOGIN ERROR:", e)
        return jsonify({"message": "Login failed"})


# ---------------- HISTORY ----------------
@app.route('/history/<username>', methods=['GET'])
def get_history(username):
    try:
        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT message, response FROM chats WHERE username=?",
            (username,)
        )

        chats = cursor.fetchall()
        conn.close()

        history = [{"message": m, "response": r} for m, r in chats]

        return jsonify(history)

    except Exception as e:
        print("HISTORY ERROR:", e)
        return jsonify([])


# ---------------- PDF UPLOAD ----------------
@app.route('/upload', methods=['POST'])
def upload_pdf():
    try:
        if 'file' not in request.files:
            return jsonify({"message": "No file uploaded"})

        file = request.files['file']
        text = extract_text_from_pdf(file)

        if not text.strip():
            return jsonify({"message": "Empty PDF or unable to extract text"})

        store_documents(text)

        return jsonify({"message": "PDF uploaded and processed successfully"})

    except Exception as e:
        print("UPLOAD ERROR:", e)
        return jsonify({"message": "PDF upload failed"})


# ---------------- TEST ----------------
@app.route('/test')
def test():
    try:
        from model.embedding import get_embedding
        get_embedding("hello world")
        return "✅ BERT is working!"
    except Exception as e:
        return f"❌ Error: {str(e)}"


# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)