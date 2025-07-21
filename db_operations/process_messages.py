import string
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import nltk
# Для эмбеддинга:
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List

 

# Убедитесь, что эти ресурсы NLTK загружены
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('wordnet')

async def process_single_message(text: str) -> str:
    """Обрабатывает текст сообщения: нижний регистр, удаление пунктуации, стоп-слов и лемматизация"""
    # Инициализация инструментов обработки текста
    lemmatizer = WordNetLemmatizer()
    stop_words = set(stopwords.words('russian'))
    translator = str.maketrans('', '', string.punctuation)
    
    # Обработка текста
    text = text.lower().strip()
    
    # Удаление пунктуации
    text = text.translate(translator)
    
    # Токенизация
    words = nltk.word_tokenize(text)
    
    # Удаление стоп-слов и лемматизация
    processed_words = [
        lemmatizer.lemmatize(word) 
        for word in words 
        if word not in stop_words and word.isalpha()
    ]
    
    return ' '.join(processed_words)



# Загружаем модель один раз при импорте
model = SentenceTransformer('DeepPavlov/rubert-base-cased-sentence')


async def embedding_single_message(text: str) -> List[float]:
    """Векторизует текст в 768-мерное пространство"""
    if not text:
        return None
    
    # Получаем эмбеддинг
    embedding = model.encode(text, convert_to_tensor=False)
    
    # Конвертируем numpy array в список float
    return embedding.tolist()