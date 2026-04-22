import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, classification_report
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
import joblib
import os

# Load dataset
df = pd.read_csv("data/student_data.csv")

# Features and target
X = df[["attendance", "quiz_avg", "assignment_avg", "midterm", "late_submissions", "prev_gpa"]]
y = df["risk_label"]

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.3, random_state=42, stratify=y
)

# Preprocessing
preprocess = ColumnTransformer([
    ("num", StandardScaler(), X.columns)
])

# -------- Random Forest --------
rf_model = Pipeline([
    ("preprocess", preprocess),
    ("model", RandomForestClassifier(
        n_estimators=400,
        random_state=42,
        class_weight="balanced"
    ))
])

rf_model.fit(X_train, y_train)
rf_pred = rf_model.predict(X_test)

print("=== RANDOM FOREST ===")
print("Accuracy:", round(accuracy_score(y_test, rf_pred), 4))
print(classification_report(y_test, rf_pred))

# -------- Logistic Regression --------
lr_model = Pipeline([
    ("preprocess", preprocess),
    ("model", LogisticRegression(
        max_iter=1000,
        class_weight="balanced"
    ))
])

lr_model.fit(X_train, y_train)
lr_pred = lr_model.predict(X_test)

print("=== LOGISTIC REGRESSION ===")
print("Accuracy:", round(accuracy_score(y_test, lr_pred), 4))
print(classification_report(y_test, lr_pred))

# Save both models
os.makedirs("models", exist_ok=True)
joblib.dump(rf_model, "models/random_forest_model.pkl")
joblib.dump(lr_model, "models/logistic_regression_model.pkl")

print("✅ Both models trained and saved.")