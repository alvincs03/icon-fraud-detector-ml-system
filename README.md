# 🛡️ **ICON Fraud Detection System**

A full-stack, machine-learning–powered fraud detection platform that analyzes financial transactions in real time, assigns risk scores, and provides explainable reasoning through a secure web interface.

---

## **Problem Statement**
Financial fraud detection requires balancing accuracy, speed, and interpretability. Traditional rule-based systems are brittle and difficult to scale, while pure black-box machine learning models often lack transparency. This project aims to detect suspicious transaction patterns probabilistically, provide explainable reasoning for every prediction, and maintain reproducibility via synthetic training data.

---

## **Approach**

### **Key Idea**
- Train a supervised classification model on synthetic transaction data to estimate fraud risk.
- Engineer behavioral features (velocity, distance, price deviation) to capture complex fraud patterns.
- Serve predictions through a REST API and provide explanations using deterministic feature contribution logic.

---

## **Data**

### **Dataset**
Synthetic transaction data is generated using `settlement-ml/data/generate_data.py`. Each record contains transaction metadata, behavioral features, and a binary fraud label.

### **Schema**
```text
id, timestamp, amount, merchant, location, channel, category,
hour, weekday, velocity_5m, velocity_1h, merchant_freq,
distance_km, price_z, fraud

---

## **Feature Engineering**
Raw data is converted into **behavioral features** that highlight risk:
- **Velocity (5m/1h)**: Detects "card testing" or rapid-fire transactions.
- **Price Z-Score**: Measures how much an amount deviates from the category average.
- **Distance KM**: Calculated distance between current transaction and user home base.
- **Merchant Frequency**: Identifies if the user has shopped at this merchant before.

---

## **Models**
The system evaluates transactions using a Scikit-learn pipeline:
- **Logistic Regression (Production)**: Chosen for its speed and ability to output well-calibrated probabilities.
- **Random Forest (Experimental)**: Used for feature importance analysis and offline benchmarking.
- **Feature Attribution**: A custom logic layer that maps model weights to human-readable "Reasons."

---

## **ML Architecture**

The system follows a modern distributed flow:
1. **Frontend (Next.js)**: Requests a score via a secure API route.
2. **ML API (FastAPI)**: Receives raw data, performs runtime feature engineering, and queries the model.
3. **Inference**: The model returns a probability (0.0 to 1.0).
4. **Response**: The API converts the probability into a 0-10 score and attaches risk "reasons."

---

## **Project Structure**
```text
icon-fraud-detector-ml-system/
├── settlement-console/        # Next.js frontend
│   ├── src/
│   ├── package.json
├── settlement-ml/             # Machine learning service
│   ├── app.py                 # FastAPI server
│   ├── train.py               # Production training pipeline
│   ├── data/
│   │   ├── generate_data.py
│   ├── artifacts/
│   │   ├── model.joblib
│   └── requirements.txt
└── README.md

---

## **How to Run**

1. **Generate Synthetic Data**:
   Navigate to the ML directory and run the generator script:
   ```bash
   cd settlement-ml
   python data/generate_data.py

2. **Train the Model**:
   Execute the training pipeline to create the model artifacts and save the trained model:
   ```bash
   python train.py

3. **Start the ML API**:
   Launch the FastAPI server to handle real-time scoring requests:
   ```bash
   uvicorn app:app --reload

4. **Launch the Web Console**:
   In a new terminal, start the Next.js development server:
   ```bash
   cd settlement-console
   npm install
   npm run dev

---

## **Limitations**
- **Synthetic Data**: Predictions are based on generated distributions and may not reflect specific real-world banking edge cases or professional money laundering techniques.
- **Identity Modeling**: Currently lacks persistent historical profiling (e.g., multi-year spending trends or cross-account relationship analysis).
- **Geographic Logic**: Distance calculations assume straight-line travel and simplified movement patterns rather than actual transit routes or flight paths.
- **Deterministic Explanations**: Risk reasons are currently mapped from feature weights rather than using dynamic game-theory models like SHAP or LIME.
- **Inference Speed**: While optimized for web scale, extremely high-frequency transaction bursts would require a message queue (e.g., Kafka) for production stability.

---

## **Future Improvements**
- **Temporal Modeling**: Implement LSTM or Transformer architectures to analyze the sequence of transactions over time for a single user.
- **Advanced Attribution**: Integrate SHAP for more granular, feature-level explanations on why a specific transaction was flagged.
- **Drift Detection**: Add monitoring to detect when incoming live data patterns diverge significantly from the training set.
- **Real-time Integration**: Connect to actual financial data aggregators like Plaid to test the model against live (anonymized) data streams.
- **Mobile UI**: Optimize the Settlement Console for mobile devices to allow investigators to review flags on the go.

---

## **Security Notes**
- **OAuth Integration**: Secure login flow using Google OAuth 2.0 via NextAuth to ensure only authorized personnel access the console.
- **Environment Management**: All secrets, API keys, and endpoint URLs are managed via `.env` files and never hardcoded in the source.
- **Encrypted Communication**: HTTPS enforcement is required for all production-level API traffic between the frontend and the ML service.
- **Stateless ML Service**: The FastAPI backend is stateless and does not store sensitive financial data, reducing the attack surface.

---

## **Disclaimer**
This project is for educational and analytical purposes only. The fraud detection scores are probabilistic and generated from synthetic data. They are not guaranteed for accuracy and should not be used for real-world financial decision-making, production banking systems, or legal compliance.

---

## **Author**
**Alvin Chen** Brown University — Applied Mathematics & Computer Science