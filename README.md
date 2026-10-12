# 🤖 AI Chatbot with PDF Q&A (Neural Network Implementor)

An intelligent AI-powered chatbot built using **Flask, NLP (BERT), and Retrieval-Augmented Generation (RAG)** that can answer questions from a predefined dataset as well as uploaded PDF documents.

---

## 🚀 Live Demo

🔗 Add your deployed link here (Render):

```
https://your-app-name.onrender.com
```

---

## 📌 Features

* 💬 ChatGPT-like chatbot interface
* 🧠 Semantic search using BERT embeddings
* 📄 PDF upload & question answering (RAG-based)
* 🔍 Smart matching (Exact + Keyword + Semantic)
* 🗂 Chat history storage (SQLite)
* 🔐 User authentication (Login/Register)
* ⚡ Fast and lightweight backend using Flask

---

## 🧠 How It Works

1. **User Input Processing**

   * Text normalization
   * Short form expansion

2. **Answer Retrieval Pipeline**

   * ✅ Keyword matching (CNN, RNN, ML, DL)
   * ✅ Exact match from dataset
   * ✅ Semantic similarity using BERT
   * ✅ PDF search + summarization

3. **Response Generation**

   * Returns the most relevant answer
   * Displays confidence score

---

## 🏗 Tech Stack

* **Backend:** Flask (Python)
* **NLP Model:** BERT / Sentence Transformers
* **Database:** SQLite
* **Frontend:** HTML, CSS, JavaScript
* **PDF Processing:** PyPDF2
* **Vector Search:** FAISS / Custom similarity search

---

## 📂 Project Structure

```
Neural_Network_Implementor/
│
├── app.py
├── database.py
├── requirements.txt
├── data/
│   └── data.json
│
├── model/
│   └── embedding.py
│
├── utils/
│   ├── helper.py
│   ├── preprocess.py
│   ├── pdf_handler.py
│   ├── summarizer.py
│   └── vector_store.py
│
├── templates/
│   ├── login.html
│   └── chat.html
│
├── static/
│   ├── style.css
│   └── chat.js
```

---

## ⚙️ Installation & Setup

### 1️⃣ Clone Repository

```
git clone 
cd your-repo
```

---

### 2️⃣ Install Dependencies

```
pip install -r requirements.txt
```

---

### 3️⃣ Run the Application

```
python app.py
```

---

### 4️⃣ Open in Browser

```
http://127.0.0.1:5000/
```

---

## 🧪 Usage

* Register a new user
* Login to access chatbot
* Ask questions like:

  * `what is cnn`
  * `what is rnn`
* Upload a PDF and ask:

  * `skills in pdf`
  * `summarize document`

---

## 📊 Example Queries

| Input         | Output                         |
| ------------- | ------------------------------ |
| what is cnn   | CNN explanation                |
| what is rnn   | RNN explanation                |
| skills in pdf | Extracted answer from document |

---

## 🔥 Key Highlights

* Built a **hybrid AI system** combining rule-based + semantic + document retrieval
* Implemented **RAG architecture**
* Designed **real-world chatbot pipeline**
* Deployed as a **live web application**

---

## 🚀 Deployment

Deployed using **Render**

Steps:

1. Push code to GitHub
2. Connect repo to Render
3. Set build & start commands
4. Deploy and get live URL

---

## 📌 Future Improvements

* 🌐 Integration with real LLM APIs (OpenAI / Gemini)
* 🎤 Voice-based chatbot
* 📊 Advanced analytics dashboard
* 📁 Multi-PDF support

---

## 👨‍💻 Author

**Piyush Pratap Singh**

* 🔗 LinkedIn: https://www.linkedin.com/in/your-profile
* 💻 GitHub: https://github.com/1616piyu

---

## ⭐ Acknowledgements

* BERT / Sentence Transformers
* Flask Documentation
* Open-source AI community

---

## 📜 License

This project is open-source and available under the MIT License.
