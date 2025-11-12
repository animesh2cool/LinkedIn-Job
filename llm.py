import os
import logging
from dotenv import load_dotenv  # add this
from openai import OpenAI

# load .env before reading OPENAI_API_KEY
load_dotenv()

logger = logging.getLogger("llm")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def summarize_text(text: str, model: str = "gpt-4o-mini") -> str:
    """
    Summarize job post text using OpenAI API.
    """
    if not text.strip():
        return ""
    
    try:
        prompt = (
            "Summarize the following LinkedIn job post into 2–3 concise bullet points, "
            "highlighting company, role, and key details:\n\n" + text
        )
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes LinkedIn job posts."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=150,
        )

        summary = response.choices[0].message.content.strip()
        return summary

    except Exception as e:
        logger.exception("OpenAI summarization failed: %s", e)
        return text[:300]  # fallback to truncated text