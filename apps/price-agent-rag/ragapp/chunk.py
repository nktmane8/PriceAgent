"""Split text into overlapping word windows so each chunk fits a prompt and keeps some context."""


def chunk_text(text: str, size: int = 120, overlap: int = 20) -> list[str]:
    words = text.split()
    if not words:
        return []
    step, chunks, i = max(1, size - overlap), [], 0
    while True:
        chunks.append(" ".join(words[i:i + size]))
        if i + size >= len(words):      # the window reached the end: no redundant tail chunk
            return chunks
        i += step
