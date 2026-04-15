from transformers import pipeline

# Load summarization model
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

def summarize_text(text):
    # Simple lightweight summarization
    sentences = text.split('.')

    # Return first 2 meaningful sentences
    return '. '.join(sentences[:2])