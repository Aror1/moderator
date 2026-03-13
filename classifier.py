from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

MODEL_NAME = "cointegrated/rubert-tiny-toxicity"

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)

device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
model.to(device)

def is_toxic(text: str, threshold: float = 0.5):
    
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512).to(device)
    with torch.no_grad():
        logits = model(**inputs).logits
    prob = torch.sigmoid(logits)[0][0].item() 
    
    prob_safe = torch.sigmoid(logits)[0][0].item()
    toxic_score = 1.0 - prob_safe
    return toxic_score > threshold, toxic_score


if __name__ == "__main__":
    texts = [
        "Ты полный лох",
        "Привет!"
    ]
    
    for text in texts:
        toxic, score = is_toxic(text)
        print(f"[{'OK' if toxic else 'TOXIC'}] {score:.2%} | {text}")
        
        
        

#BOT_TOKEN = "8296264601:AAFLcG2Hi8xV1P1TQlfv9qwuE2nJJh2S1l4"
#WEATHER_API_KEY = "0ff35a61f1a94ffb82c0999ffb44273f"  # openweathermap.org