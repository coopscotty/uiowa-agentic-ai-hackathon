# Databricks notebook source
"""Simple patient retention data collector for the UIowa hackathon.
Run this in Databricks after creating the synthetic data tables.
Scores are outreach priorities, not actual probabilities of churn.
"""

from pyspark.sql import SparkSession, Window, functions as F

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "chiro_hackathon")

TABLE_PATH = f"{dbutils.widgets.get('catalog')}.{dbutils.widgets.get('schema')}"


def build_retention_profiles(spark):
    today = F.current_date()
    last_90 = F.date_sub(today, 90)
    last_180 = F.date_sub(today, 180)

    patients = spark.table(f"{TABLE_PATH}.patients").select(
        "patient_id", "home_location_id", "age_band", "acquisition_source"
    )
    locations = spark.table(f"{TABLE_PATH}.locations").select(
        F.col("location_id").alias("home_location_id"), "location_name"
    )
    visits = spark.table(f"{TABLE_PATH}.visits").filter(F.col("visit_date") <= today)
    appointments = spark.table(f"{TABLE_PATH}.appointments").filter(
        F.col("appointment_date") <= today
    )

    # Count visits and appointments separately, so joining them doesn't double-count.
    visit_summary = visits.groupBy("patient_id").agg(
        F.countDistinct("visit_date").alias("visit_days"),
        F.count("*").alias("total_completed_visits"),
        F.max("visit_date").alias("last_completed_visit_date"),
        F.sum(F.when(F.col("visit_date") >= last_90, 1).otherwise(0)).alias("visits_last_90d"),
        F.sum(F.when(
            (F.col("visit_date") >= last_180) & (F.col("visit_date") < last_90), 1
        ).otherwise(0)).alias("visits_previous_90d"),
    )

    appointment_summary = appointments.groupBy("patient_id").agg(
        F.max(F.when(
            (F.col("status") == "No-Show") & (F.col("appointment_date") >= last_90),
            F.col("appointment_date")
        )).alias("last_no_show_date"),
        F.max(F.when(
            (F.col("status") == "Cancelled") & (F.col("appointment_date") >= last_90),
            F.col("appointment_date")
        )).alias("last_cancellation_date"),
    )

    # Work out the usual days between completed visits for each patient.
    dates = visits.select("patient_id", "visit_date").distinct()
    patient_window = Window.partitionBy("patient_id").orderBy("visit_date")
    gaps = (dates
        .withColumn("previous_visit", F.lag("visit_date").over(patient_window))
        .withColumn("gap_days", F.datediff("visit_date", "previous_visit"))
        .filter(F.col("gap_days") > 0))

    usual_gaps = gaps.groupBy("patient_id").agg(
        F.count("*").alias("gap_count"),
        F.expr("percentile_approx(gap_days, 0.5)").alias("usual_gap_days"),
    )

    # With only 2 visit days, use the clinic's typical interval as an estimate.
    clinic_gaps = (usual_gaps
        .filter(F.col("gap_count") >= 2)
        .join(patients.select("patient_id", "home_location_id"), "patient_id")
        .groupBy("home_location_id")
        .agg(F.expr("percentile_approx(usual_gap_days, 0.5)").alias("clinic_gap_days")))

    profiles = (patients
        .join(locations, "home_location_id", "left")
        .join(visit_summary, "patient_id", "left")
        .join(appointment_summary, "patient_id", "left")
        .join(usual_gaps, "patient_id", "left")
        .join(clinic_gaps, "home_location_id", "left")
        .fillna({
            "visit_days": 0,
            "total_completed_visits": 0,
            "visits_last_90d": 0,
            "visits_previous_90d": 0,
            "location_name": "Unknown",
        })
        .withColumn("days_since_last_visit", F.datediff(today, "last_completed_visit_date"))
        .withColumn("expected_gap_days", F.when(
            F.col("visit_days") >= 3, F.col("usual_gap_days")
        ).when(F.col("visit_days") == 2, F.col("clinic_gap_days")))
        .withColumn("overdue_ratio", F.col("days_since_last_visit") / F.col("expected_gap_days")))

    # Only count a recent no-show/cancellation if the patient hasn't returned since.
    no_show = F.col("last_no_show_date") > F.col("last_completed_visit_date")
    cancelled = F.col("last_cancellation_date") > F.col("last_completed_visit_date")
    visits_dropped = (
        (F.col("visits_previous_90d") >= 2) &
        (F.col("visits_last_90d") == 0) &
        (F.col("overdue_ratio") >= 1.2)
    )

    # How overdue are they compared with their normal visit schedule?
    overdue_points = (F.when(F.col("overdue_ratio") >= 2, 3)
        .when(F.col("overdue_ratio") >= 1.5, 2)
        .when(F.col("overdue_ratio") >= 1.2, 1)
        .otherwise(0))

    score = (overdue_points + F.when(no_show, 2).otherwise(0)
        + F.when(cancelled, 1).otherwise(0)
        + F.when(visits_dropped, 1).otherwise(0))

    profiles = profiles.withColumn("retention_priority_score",
        F.when(F.col("visit_days") < 2, 0)
        .when(F.col("visit_days") == 2, F.least(score, F.lit(4)))
        .otherwise(score))

    # Fewer than 2 DIFFERENT visit dates means we can't estimate a normal interval.
    profiles = profiles.withColumn("risk_category",
        F.when(F.col("visit_days") < 2, "Insufficient data")
        .when(F.col("retention_priority_score") >= 5, "High")
        .when(F.col("retention_priority_score") >= 3, "Medium")
        .otherwise("Low"))

    return profiles


def get_agent_context(profiles, limit=10):
    # Return simple dictionaries the AI agent can use later.
    rows = (profiles
        .filter(F.col("risk_category") == "High")
        .orderBy(F.col("retention_priority_score").desc(),
                 F.col("overdue_ratio").desc(), "patient_id")
        .select("patient_id", "home_location_id", "location_name", "age_band",
                "acquisition_source", "total_completed_visits",
                "last_completed_visit_date", "days_since_last_visit",
                "expected_gap_days", "retention_priority_score", "risk_category")
        .limit(limit).collect())

    result = []
    for row in rows:
        patient = row.asDict()
        if patient["last_completed_visit_date"] is not None:
            patient["last_completed_visit_date"] = str(patient["last_completed_visit_date"])
        result.append(patient)
    return result


# Keep the same basic interface as the older collector for your AI agent.
class DataCollector:
    def __init__(self, spark):
        self.spark = spark

    def build_retention_profiles(self):
        return build_retention_profiles(self.spark)

    def get_agent_context(self, limit=10, profiles=None):
        if profiles is None:
            profiles = self.build_retention_profiles()
        return get_agent_context(profiles, limit)


# Run the collector and print simple, readable results.
if __name__ == "__main__":
    spark = SparkSession.builder.getOrCreate()
    collector = DataCollector(spark)
    profiles = collector.build_retention_profiles()

    print("Sample high-priority patients:")
    for patient in get_agent_context(profiles, limit=10):
        print(f"\npatient_id: {patient['patient_id']}")
        for field, value in patient.items():
            if field != "patient_id":
                print(f"    {field}: {value}")

    counts = {row["risk_category"]: row["count"]
              for row in profiles.groupBy("risk_category").count().collect()}

    print("\nPatient Risks")
    print(f"High: {counts.get('High', 0)}")
    print(f"Medium: {counts.get('Medium', 0)}")
    print(f"Low: {counts.get('Low', 0)}")
    print(f"Patients with not enough data to classify: {counts.get('Insufficient data', 0)}")
    print("Scores indicate follow-up priority, not a proven chance of leaving.")

# COMMAND ----------

profiles = build_retention_profiles(spark)

profiles.write.mode("overwrite").option(
    "overwriteSchema", "true"
).saveAsTable(f"{TABLE_PATH}.retention_profiles")

print("Dashboard data saved successfully!")