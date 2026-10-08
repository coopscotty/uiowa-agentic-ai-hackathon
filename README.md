# UIowa × Xorbix Hackathon

## Patient Retention AI Agent

For this hackathon, we built a patient retention system using Databricks, Python, and AI. The goal is to help chiropractic clinics identify patients who might stop coming back and recommend ways to retain them.

## How It Works

Our project has three main parts:

### 1. Data Collection & Risk Scoring
The Python script collects patient data from several tables, including:
- Patient information
- Appointment and visit history
- Cancellations and no-shows

Using this data, the script calculates a retention priority score based on things like how recently a patient visited, how often they visit, and whether they've missed appointments.

Patients are then categorized as **High, Medium, Low, or Insufficient Data**.

### 2. AI Retention Agent
The highest-priority patients (i.e. ones with the highest scores) are passed to our AI agent, which uses Meta Llama 3.3 through Databricks.

The agent looks at the patient's information and recommends a specific action the clinic could take to help retain them.

Instead of just saying a patient is at risk, the goal is to explain **why they might be at risk and what the clinic could do about it.**

### 3. Dashboard
We also created a Databricks dashboard to visualize patient retention data, risk categories, and other information that we saw would be relevant.

## Project Workflow

```text
Patient Data
     |
     v
Python Data Collector
     |
     |-- Analyzes patient activity
     |-- Calculates risk scores
     |-- Assigns risk categories
     |
     v
AI Retention Agent
     |
     |-- Analyzes high-priority patients
     |-- Generates follow-up recommendations
     |
     v
Databricks Tables & Dashboard
```

## Technologies Used

- Databricks
- Python / PySpark
- SQL
- Meta Llama 3.3 70B
- Databricks Asset Bundles (DAB)

## Running the Project

1. Clone this repository into a Databricks Git folder.
2. Run `generate_synthetic_data.py` to create the patient data tables.
3. Open the project in the Databricks editor.
4. Select the `dev` target and deploy the bundle.
5. Run the deployed `retention-workflow` job under Jobs & Pipelines.

The DAB runs the Data Collector first, then the AI Agent.

**Note:** The project uses synthetic data stored in `workspace.chiro_hackathon`. The dashboard is separate from the DAB deployment.

## Team Contributions

**Cooper Scott**
- Data collection and risk scoring
- AI retention agent
- Databricks Asset Bundle setup

**Ibrahim**
- Backend documentation and workflow explanation
- Project planning and presentation

---

*University of Iowa × Xorbix Agentic AI Hackathon — October 2026*
