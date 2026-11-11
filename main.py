## Importerar all dokumentation i knowledge-mappen till en variabel
from pathlib import Path


knowledge_dir = Path(__file__).resolve().parent / "knowledge"

documents = []

for file in sorted(knowledge_dir.glob("*.md")):
    content = file.read_text(encoding="utf-8")
    documents.append(f"FIL: {file.name}\n{content}")

knowledge = "\n\n---\n\n".join(documents)

