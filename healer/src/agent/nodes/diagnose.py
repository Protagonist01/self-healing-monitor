import json
import re
from typing import Dict, Any, List
from openai import OpenAI
from healer.src.config import settings
from healer.src.agent.state import HealerState, DiagnosisData

def extract_json(text: str) -> Dict[str, Any]:
    """
    Cleans up LLM response and parses the inner JSON block.
    """
    # Look for code blocks first
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # Fallback to first '{' to last '}'
        match_raw = re.search(r"(\{.*\})", text, re.DOTALL)
        if match_raw:
            json_str = match_raw.group(1)
        else:
            json_str = text

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing LLM response as JSON: {e}. Raw response: {text}")
        raise

def diagnose_node(state: HealerState) -> HealerState:
    """
    LangGraph node: diagnose.
    Uses OpenRouter API to analyze the gathered incident context and outputs a diagnosis with a confidence score.
    """
    context = state["context"]
    alert = state["alert"]
    
    if not context:
        state["errors"].append("Diagnose node failed: no context available.")
        return state

    # Construct the prompt
    prompt = f"""You are an expert Site Reliability Engineer (SRE).
Analyze the following microservice incident alert and gathered context.

Alert Details:
- Name: {alert.get('name')}
- Service: {alert.get('service')}
- Severity: {alert.get('severity')}
- Labels: {json.dumps(alert.get('labels'))}
- Annotations: {json.dumps(alert.get('annotations'))}

Gathered Context:
- Metrics Summary: {context['metrics_summary']}
- Log Summary: {context['log_summary']}
- Recent Deployments: {", ".join(context['recent_deploys'])}
- Relevant Runbook Section:
{context['runbook_excerpt']}

Based on the above information, determine the most likely root cause. Calculate a confidence score between 0.0 and 1.0 (where 0.0 is completely uncertain and 1.0 is absolute certainty). Provide a list of specific supporting evidence.

Your response MUST be a JSON object matching this schema:
{{
  "root_cause": "A clear, concise explanation of the probable root cause of the incident.",
  "confidence": 0.85,
  "supporting_evidence": [
    "Evidence line 1 from logs/metrics",
    "Evidence line 2 from deploy timeline"
  ]
}}
Do not write any introductory or concluding text outside the JSON object. Keep confidence calibrated (e.g. if logs show explicit OutOfMemory/OOMKilled matching a recent deploy, confidence should be high >= 0.80. If Loki is down and logs are missing, confidence should be lower).
"""

    try:
        # Check if API key is present; if not, return mock diagnosis
        if not settings.OPENROUTER_API_KEY:
            print("No OPENROUTER_API_KEY provided. Using mock diagnosis.")
            state["diagnosis"] = {
                "root_cause": "Memory leak in request handler introduced in v2.4.1 (mocked)",
                "confidence": 0.85,
                "supporting_evidence": ["OOMKilled log lines", "Deployment v2.4.1 was 47 minutes ago"],
                "llm_model": "mock-model",
                "llm_tokens_used": 0
            }
            return state

        client = OpenAI(
            base_url=settings.OPENROUTER_BASE_URL,
            api_key=settings.OPENROUTER_API_KEY
        )
        
        response = client.chat.completions.create(
            model=settings.OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful SRE assistant that outputs structured JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=800
        )
        
        raw_text = response.choices[0].message.content
        diagnosis_json = extract_json(raw_text)
        
        # Verify schema
        root_cause = diagnosis_json.get("root_cause", "Unknown root cause")
        confidence = float(diagnosis_json.get("confidence", 0.5))
        supporting_evidence = diagnosis_json.get("supporting_evidence", [])
        
        state["diagnosis"] = {
            "root_cause": root_cause,
            "confidence": confidence,
            "supporting_evidence": supporting_evidence,
            "llm_model": settings.OPENROUTER_MODEL,
            "llm_tokens_used": response.usage.total_tokens if response.usage else 0
        }

    except Exception as e:
        print(f"Error in LLM diagnosis node: {e}")
        state["errors"].append(f"Diagnosis LLM error: {str(e)}")
        # Provide fallback diagnosis so graph doesn't crash completely
        state["diagnosis"] = {
            "root_cause": f"Failed to run LLM diagnosis. Fallback: service container might have crashed.",
            "confidence": 0.5,
            "supporting_evidence": [str(e)],
            "llm_model": "fallback",
            "llm_tokens_used": 0
        }
        
    return state
