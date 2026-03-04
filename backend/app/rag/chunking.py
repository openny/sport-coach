def chunk_text(pages: list[dict], max_chars: int = 1200, overlap: int = 150) -> list[dict]:
    chunks = []
    for pg in pages:
        text = (pg.get("text") or "")
        if not text:
            continue

        start = 0
        L = len(text)

        while start < L:
            end = min(start + max_chars, L)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append({"text": chunk, "meta": {"page": pg.get("page")}})

            # ✅ 마지막까지 왔으면 종료 (무한루프 방지 핵심)
            if end >= L:
                break

            # ✅ 다음 start 계산 + 안전장치(전진 안 하면 종료)
            next_start = end - overlap
            if next_start <= start:
                next_start = end  # overlap이 너무 크면 그냥 앞으로 전진
            start = next_start

    return chunks