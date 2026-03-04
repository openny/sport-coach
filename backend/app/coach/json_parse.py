import json, re

def extract_json(text: str) -> dict:
    if not text:
        raise ValueError("empty llm_text")

    t = text.strip()

    # 1) 코드블록 제거
    if "```" in t:
        t = re.sub(r"```[a-zA-Z0-9]*", "", t).replace("```", "").strip()

    # 2) 가장 바깥 {} 추출
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no json object boundaries")

    js = t[start:end+1]

    # 3) 잘린 문자열 복구 시도 (가장 흔한 케이스)
    # "preview": " 로 끝나면 강제로 닫아줌
    js = re.sub(r'"preview"\s*:\s*"[^"]*$', '"preview": ""', js)

    # 4) trailing comma 제거
    js = re.sub(r",\s*}", "}", js)
    js = re.sub(r",\s*]", "]", js)

    return json.loads(js)