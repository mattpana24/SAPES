import numpy as np
import pandas as pd

np.random.seed(42)

n = 200

attendance = np.random.randint(30, 101, n)
quiz_avg = np.random.randint(10, 101, n)
assignment_avg = np.random.randint(10, 101, n)
midterm = np.random.randint(0, 101, n)
late_submissions = np.random.randint(0, 9, n)
prev_gpa = np.round(np.random.uniform(0.0, 4.0, n), 2)

noise = np.random.normal(0, 8, n)

final_mark = (
    0.25 * attendance +
    0.20 * quiz_avg +
    0.25 * assignment_avg +
    0.25 * midterm -
    2.5 * late_submissions +
    5 * prev_gpa +
    noise
)

final_mark = np.clip(final_mark, 0, 100).round(0).astype(int)

def label(mark):
    if mark < 40:
        return "High"
    elif mark <= 55:
        return "Medium"
    else:
        return "Low"

risk_label = [label(m) for m in final_mark]

df = pd.DataFrame({
    "student_id": [f"RU{1000+i}" for i in range(n)],
    "attendance": attendance,
    "quiz_avg": quiz_avg,
    "assignment_avg": assignment_avg,
    "midterm": midterm,
    "late_submissions": late_submissions,
    "prev_gpa": prev_gpa,
    "final_mark": final_mark,
    "risk_label": risk_label
})

df.to_csv("data/student_data.csv", index=False)

print("✅ Dataset created successfully!")