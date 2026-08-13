import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def summarize_description(full_description):
    prompt = f"""Extract the core requirements (tools, tech stack, hard skills, and domain experience) from this job description.

INSTRUCTIONS:
1. Focus ONLY on sections that list requirements, such as: "Qualifications", "Requirements", "What Makes You A Good Fit", "Preferred Qualifications", "Key Requirements", "Skills & Attributes", or similar.
2. If such sections exist, extract from there ONLY.
3. If no clear "Requirements" section exists, extract from "Key Responsibilities" or "What will you do" but only for explicit technical skills (not general tasks).
4. DO NOT include:
   - Soft skills (e.g. "team player", "communication", "analytical thinking")
   - Education requirements (e.g. "Bachelor's in Computer Science")
   - Years of experience (e.g. "5+ years")
   - Preferred/nice-to-have items (unless they are clearly tools/skills)
   - Introduction sentences like "Here are the requirements:"
5. OUTPUT FORMAT: Return ONLY a single line of plain text. List all items separated by commas (,). DO NOT use bullet points, numbers, dashes, or newlines.

Job description:
{full_description}
"""

    resp = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        temperature=0.2,
    )

    # print(resp.choices[0].message.content)
    result = resp.choices[0].message.content
    return result

if __name__ == "__main__":
    summarize_description(
        full_description="'Key Responsibilities\nLead and deliver advanced\ndata analysis, statistical modeling, and machine learning solutions\nto support\ncredit analytics, risk assessment, credit scoring, and portfolio performance monitoring\n.\nDesign, develop, validate, and continuously improve\npredictive models\nrelated to\ncredit behavior, default risk, fraud indicators, and data quality metrics\n.\nPerform\ndata exploration, experimentation, feature engineering, and model optimization\nusing\nPython/R and SQL\non large-scale, structured, and sensitive credit datasets.\nTake full ownership of the\nanalytical model lifecycle\n, including development, deployment, performance monitoring, stability tracking, recalibration, and documentation.\nEnsure high standards of\ndata quality, consistency, confidentiality, and integrity\nacross all analytical processes.\nTranslate complex analytical results into\nclear, actionable insights\nthrough reports, dashboards, and visualizations using BI tools such as\nPower BI or Tableau\n.\nAct as a strategic data partner to\nRisk, Product, Business, and Technology teams\n, supporting credit product development, risk policy formulation, and enterprise analytics initiatives.\nProvide\ntechnical guidance and mentorship\nto junior data scientists and analysts.\nApply and promote best practices in\ndata governance, data privacy, model governance, and regulatory compliance\nin alignment with financial services regulations.\nContribute to the continuous enhancement of\ndata science standards, methodologies, and analytics frameworks\nwithin the organization.\nQualifications\nBachelor’s or Master’s degree in\nStatistics, Mathematics, Computer Science, Data Science, Economics, Engineering, or a related quantitative field\n.\nMinimum 5 years of relevant experience\nin\ndata science, advanced analytics, or statistical modeling\n, with demonstrated\nsenior-level responsibilities\n.\nStrong hands-on expertise in\nPython and/or R\n,\nSQL\n, and experience working with\nlarge-scale structured datasets\n.\nSolid understanding of\ncredit risk concepts\n, including\ncredit scoring, consumer credit behavior, portfolio analytics, or alternative data\n, preferably within\nfinancial services, banking, fintech, or credit bureau\nenvironments.\nProven experience in\ndeveloping, deploying, and monitoring analytical models in production environments\n.\nExperience with\nmodel governance, documentation, and regulatory or audit review processes\nin a\nregulated environment\n.\nStrong ability to communicate complex analytical insights clearly and effectively to both\ntechnical and non-technical stakeholders\n.\nAbility to work independently, take ownership of analytical outcomes, and provide sound judgment in data-driven decision-making.'"
    )