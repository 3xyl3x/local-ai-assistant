
import json
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Konfiguration
URL = "http://localhost:11434"
MODEL = "gemma4:26b"

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
PROMPT_FILE = BASE_DIR / "system_prompt.md"


def api(endpoint, data=None, timeout=120):
    """Skicka ett API-anrop till Ollama."""
    body = json.dumps(data).encode("utf-8") if data is not None else None

    request = Request(
        URL + endpoint,
        data=body,
        headers={"Content-Type": "application/json"}
    )

    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def load_knowledge():
    """Läs in alla Markdown-filer från knowledge-mappen."""
    if not KNOWLEDGE_DIR.is_dir():
        raise FileNotFoundError(
            f"Kunskapsmappen saknas: {KNOWLEDGE_DIR}"
        )

    documents = []

    for file in sorted(KNOWLEDGE_DIR.glob("*.md")):
        content = file.read_text(encoding="utf-8")

        if content.strip():
            documents.append(
                f"FIL: {file.name}\n{content}"
            )
            print(f"Inläst: {file.name}")

    if not documents:
        raise ValueError("Inga dokument hittades i knowledge/")

    return "\n\n---\n\n".join(documents)


def load_system_prompt(knowledge):
    """Läs systemprompten och infoga kunskapsbasen."""
    if not PROMPT_FILE.is_file():
        raise FileNotFoundError(
            f"Systemprompten saknas: {PROMPT_FILE}"
        )

    prompt = PROMPT_FILE.read_text(encoding="utf-8")

    if "{knowledge}" not in prompt:
        raise ValueError(
            "system_prompt.md måste innehålla {knowledge}"
        )

    return prompt.replace("{knowledge}", knowledge)


def check_model():
    """Kontrollera Ollama och ladda ner modellen vid behov."""
    try:
        models = api("/api/tags")["models"]
    except URLError:
        raise SystemExit(
            "Kan inte ansluta till Ollama. Starta Ollama först."
        )

    installed = [model["name"] for model in models]

    if MODEL not in installed:
        print(f"Laddar ner modellen {MODEL}...")

        api(
            "/api/pull",
            {"model": MODEL, "stream": False},
            timeout=3600
        )

    print(f"Modell: {MODEL}")

def show_loading(stop_event):
    """Visa animerade punkter medan modellen arbetar."""
    dots = 1

    while not stop_event.is_set():
        print(
            "\rFormulerar svar" + "." * dots + "   ",
            end="",
            flush=True
        )

        dots = dots % 3 + 1
        stop_event.wait(0.4)

    # Rensa statusraden
    print("\r" + " " * 50 + "\r", end="", flush=True)

def ask_ollama(messages):
    """Skicka frågan, visa laddningsanimation och strömma svaret."""

    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": 0.2,
            "num_ctx": 8192
        }
    }

    request = Request(
        URL + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    answer = ""
    response_started = False

    # Starta animation i separat tråd
    stop_event = threading.Event()
    loading_thread = threading.Thread(
        target=show_loading,
        args=(stop_event,),
        daemon=True
    )
    loading_thread.start()

    try:
        with urlopen(request, timeout=300) as response:
            for line in response:
                if not line.strip():
                    continue

                data = json.loads(line)

                if "error" in data:
                    raise RuntimeError(data["error"])

                text = data.get("message", {}).get("content", "")

                if text:
                    # Stoppa animationen vid första texten
                    if not response_started:
                        stop_event.set()
                        loading_thread.join()

                        print("Pulsverket: ", end="", flush=True)
                        response_started = True

                    print(text, end="", flush=True)
                    answer += text

        if not response_started:
            print("Pulsverket: Inget svar mottogs.")

        print()
        return answer

    finally:
        stop_event.set()
        loading_thread.join()


def main():
    print("Startar Pulsverket AI-receptionist...\n")

    try:
        # Kontrollera Ollama och modellen
        check_model()

        # Läs kunskapsbasen
        print("\nLäser kunskapsbasen...")
        knowledge = load_knowledge()

        # Läs systemprompten
        system_prompt = load_system_prompt(knowledge)

    except (OSError, ValueError, URLError, HTTPError) as error:
        print(f"Fel vid uppstart: {error}")
        return

    # Konversationshistorik
    messages = [
        {"role": "system", "content": system_prompt}
    ]

    print("\nPulsverket AI-receptionist är redo!")
    print("Skriv 'exit' för att avsluta.\n")

    while True:
        try:
            question = input("Du: ").strip()

            if question.lower() in ("exit", "quit"):
                break

            if not question:
                continue

            messages.append({
                "role": "user",
                "content": question
            })

            print()

            answer = ask_ollama(messages)

            messages.append({
                "role": "assistant",
                "content": answer
            })

            print()

        except (KeyboardInterrupt, EOFError):
            break

        except (URLError, HTTPError, RuntimeError, ValueError) as error:
            print(f"\nFel: {error}")
            messages.pop()

    print("\nProgrammet avslutas.")


if __name__ == "__main__":
    main()
