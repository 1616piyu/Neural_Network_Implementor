def expand_text(text):
    text = text.lower()

    replacements = {
        "ml": "machine learning",
        "ai": "artificial intelligence",
        "dl": "deep learning",
        "cnn": "convolutional neural network",
        "rnn": "recurrent neural network"
    }

    words = text.split()

    expanded_words = []
    for word in words:
        if word in replacements:
            expanded_words.append(replacements[word])
        else:
            expanded_words.append(word)

    return " ".join(expanded_words)