"""
Industry-standard data analytics frameworks.

These are the foundational methodologies that guide how each specialist thinks.
Specialists reference relevant phases from these frameworks in their reasoning.
"""

ANALYTICS_FRAMEWORKS = {
    "crisp_dm": {
        "name": "CRISP-DM",
        "full_name": "Cross-Industry Standard Process for Data Mining",
        "phases": [
            {
                "phase": 1,
                "name": "Business Understanding",
                "description": "Understand the objectives and requirements from a business perspective. Convert this knowledge into a data problem definition and a preliminary plan.",
                "mapped_to": "supervisor",
            },
            {
                "phase": 2,
                "name": "Data Understanding",
                "description": "Collect initial data, identify data quality problems, discover first insights, and detect interesting subsets to form hypotheses.",
                "mapped_to": "eda",
            },
            {
                "phase": 3,
                "name": "Data Preparation",
                "description": "Construct the final dataset from the raw data. Tasks include table, record, and attribute selection, data cleaning, and transformation.",
                "mapped_to": "eda + cleaning",
            },
            {
                "phase": 4,
                "name": "Modeling",
                "description": "Select and apply modeling techniques. Calibrate parameters to optimal values.",
                "mapped_to": "statistics",
            },
            {
                "phase": 5,
                "name": "Evaluation",
                "description": "Evaluate the model to ensure it achieves the business objectives. Review the process to determine if there is a step that has been overlooked.",
                "mapped_to": "reflector",
            },
            {
                "phase": 6,
                "name": "Deployment",
                "description": "Present findings and organize results so the customer can use them. Can range from a simple report to a repeatable data mining process.",
                "mapped_to": "narrative",
            },
        ],
    },
    "semma": {
        "name": "SEMMA",
        "full_name": "Sample, Explore, Modify, Model, Assess",
        "phases": [
            {
                "phase": 1,
                "name": "Sample",
                "description": "Extract a representative sample from a large dataset. Assess whether sampling is needed based on dataset size and computational constraints.",
                "mapped_to": "eda",
            },
            {
                "phase": 2,
                "name": "Explore",
                "description": "Search for unanticipated trends and anomalies. Understand the data through visualization and statistical summaries.",
                "mapped_to": "eda",
            },
            {
                "phase": 3,
                "name": "Modify",
                "description": "Transform variables, create derived features, handle missing data, and prepare the dataset for analysis.",
                "mapped_to": "eda + cleaning",
            },
            {
                "phase": 4,
                "name": "Model",
                "description": "Apply statistical and machine learning techniques to find patterns and make predictions.",
                "mapped_to": "statistics",
            },
            {
                "phase": 5,
                "name": "Assess",
                "description": "Evaluate the reliability and usefulness of the findings. Validate against holdout data or domain knowledge.",
                "mapped_to": "reflector",
            },
        ],
    },
    "analytics_maturity": {
        "name": "Analytics Maturity Ladder",
        "full_name": "Descriptive → Diagnostic → Predictive → Prescriptive",
        "levels": [
            {
                "level": 1,
                "name": "Descriptive",
                "question": "What happened?",
                "description": "Summarize historical data. Identify patterns, distributions, and key metrics.",
                "techniques": ["aggregation", "summary statistics", "data visualization", "profiling"],
                "mapped_to": "eda",
            },
            {
                "level": 2,
                "name": "Diagnostic",
                "question": "Why did it happen?",
                "description": "Investigate causes and correlations. Drill down into anomalies and outliers.",
                "techniques": ["correlation analysis", "segmentation", "root cause analysis", "drill-down"],
                "mapped_to": "eda + statistics",
            },
            {
                "level": 3,
                "name": "Predictive",
                "question": "What will happen?",
                "description": "Forecast future outcomes using statistical models and trend analysis.",
                "techniques": ["regression", "time series", "classification", "clustering"],
                "mapped_to": "statistics",
            },
            {
                "level": 4,
                "name": "Prescriptive",
                "question": "What should we do?",
                "description": "Recommend actions based on analysis. Translate findings into decisions.",
                "techniques": ["optimization", "scenario analysis", "recommendation"],
                "mapped_to": "narrative",
            },
        ],
    },
    "insight_communication": {
        "name": "Insight Communication Standard",
        "principles": [
            {"name": "Accurate", "description": "Findings must be factually correct and methodologically sound."},
            {"name": "Precise", "description": "Use specific numbers and ranges, not vague qualifiers."},
            {"name": "Clear", "description": "Non-technical audience should understand the key takeaway."},
            {"name": "Error-free", "description": "Double-check calculations, labels, and data references."},
            {"name": "Relevant", "description": "Every finding should connect back to the user's question."},
            {"name": "Actionable", "description": "Include specific next steps or recommendations."},
        ],
    },
}
