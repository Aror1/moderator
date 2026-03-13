**OpenWeatherMap API** — [openweathermap.org](https://openweathermap.org)





Бесплатный погодный API, предоставляющий данные о текущей погоде, прогнозах и геокодировании. В проекте используются два эндпоинта:






| Эндпоинт | Назначение |
|---|---|
| `data/2.5/weather` | Получение текущей погоды по координатам (температура, ветер, влажность, давление, облачность) |
| `geo/1.0/reverse` | Reverse geocoding — определение названия города по координатам GPS |

Пользователь отправляет боту геолокацию, бот определяет город и возвращает актуальные погодные данные.





---

## Базовая модель ИИ

**BERT** (Bidirectional Encoder Representations from Transformers)

Предобученная языковая модель от Google. Является основой для большинства современных моделей классификации текста на русском языке.

---





## Модель трансформера

**[cointegrated/rubert-tiny-toxicity](https://huggingface.co/cointegrated/rubert-tiny-toxicity)**

Дообученная компактная версия ruBERT для классификации токсичности русскоязычных текстов.

| Параметр | Значение |
|---|---|
| Базовая архитектура | ruBERT-tiny (BERT) |
| Задача | Бинарная классификация текста |
| Входные данные | Текст на русском языке (до 512 токенов) |
| Выходные данные | Вероятность токсичности (0.0 — 1.0) |
| Библиотека | `transformers` (HuggingFace) + `torch` |


Каждое сообщение в группе проходит через модель. Если вероятность токсичности превышает порог (`TOXICITY_THRESHOLD = 0.5`), сообщение удаляется, а пользователь получает предупреждение. После трёх предупреждений — мут.

```python
def is_toxic(text: str, threshold: float = 0.5) -> tuple[bool, float]:
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        logits = model(**inputs).logits
    prob_safe = torch.sigmoid(logits)[0][0].item()
    toxic_score = 1.0 - prob_safe
    return toxic_score > threshold, toxic_score
```

---



**GitHub**.

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/Aror1/moderator.git
git push -u origin main
```

Репозиторий: `[https://github.com/Aror0/moderator.git](https://github.com/Aror1/moderator.git`

---
