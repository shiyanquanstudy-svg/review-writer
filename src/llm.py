import json
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from src.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_llm(prompt: str, system: str = None, temperature: float = 0.3) -> str:
    """基础 LLM 调用，返回文本。"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content


def call_llm_json(prompt: str, system: str = None, temperature: float = 0.2) -> dict:
    """调用 LLM 并解析为 JSON。失败时抛出异常。"""
    raw = call_llm(prompt, system=system, temperature=temperature)
    # 去掉可能的 markdown 代码块包裹
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    return json.loads(cleaned)