# Comment-Filter

An AI-based web application that classifies comments as toxic or non-toxic using basic machine learning techniques.

## 📌 Overview

This project aims to simplify comment moderation by automatically identifying harmful comments. It uses Natural Language Processing (NLP) and a machine learning model to analyze text input and provide structured results.

## ⚙️ Features

- Classifies comments as Toxic or Non-Toxic  
- Uses text preprocessing (cleaning, normalization)  
- Applies TF-IDF vectorization  
- Uses Logistic Regression / SVM for classification  
- Simple web interface using Flask  
- Easy to test and run locally  

## 🛠️ Tech Stack

- Python  
- Scikit-learn  
- Flask  
- HTML/CSS  
- Pandas  

## 🚀 How to Run

1. Clone the repository:
```bash
git clone https://github.com/shubhangi-111/Comment-Filter.git
cd Comment-Filter

2. Install dependencies:

pip install -r requirements.txt

3. Run the model training (if needed):

python model/train.py

4. Run the web app:

python app.py

5. Open in browser:

http://127.0.0.1:5000