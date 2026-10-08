# Databricks notebook source
# MAGIC %run "./Retention Data Collector"

# COMMAND ----------

import json

collector = DataCollector(spark)
patients = collector.get_agent_context(limit=3)

model = "databricks-meta-llama-3-3-70b-instruct"

for patient in patients:
    prompt = f"""
    You are an AI patient retention assistant for a chiropractic clinic.

    Patient data:
    {json.dumps(patient, indent=2)}

    Analyze this patient and provide:
    1. Why they might stop returning.
    2. ONE specific action clinic staff should take.
    3. Why you recommend that action.

    Only use the provided data.
    Do not invent patient circumstances or provide medical advice.
    The risk score is an outreach priority, not a proven churn probability.
    """

    result = spark.createDataFrame([(prompt,)], ["prompt"])

    response = result.selectExpr(
        f"ai_query('{model}', prompt) AS recommendation"
    ).first()["recommendation"]

    print(f"\nPatient: {patient['patient_id']}")
    print(response)
    print("-" * 50)

# COMMAND ----------

# This cell saves the reccommendations our agent made:

import json

model = "databricks-meta-llama-3-3-70b-instruct"

recommendations = []

for patient in patients:
    prompt = f"""
    You are a patient retention assistant for a chiropractic clinic.

    Patient data:
    {json.dumps(patient, indent=2)}

    Recommend ONE appropriate follow-up action for clinic staff.
    Explain why based on the patient's data.

    Do not invent facts or give medical advice.
    The risk score is an outreach priority, not a proven probability.
    """

    df = spark.createDataFrame([(prompt,)], ["prompt"])

    response = df.selectExpr(
        f"ai_query('{model}', prompt) AS recommendation"
    ).first()["recommendation"]

    recommendations.append((
        patient["patient_id"],
        response,
        "Pending Review"
    ))

    print("Completed:", patient["patient_id"])

# Save recommendations to Databricks
results = spark.createDataFrame(
    recommendations,
    ["patient_id", "ai_recommendation", "task_status"]
)

results.write.mode("overwrite").saveAsTable(
    "workspace.chiro_hackathon.ai_recommendations"
)

print("AI recommendations saved successfully!")