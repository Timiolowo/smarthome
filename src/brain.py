import os
from typing import List, Optional

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

from src.memory import memory

LLM_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models",
    "llm",
)
MODEL_3B_PATH = os.path.join(LLM_DIR, "Llama-3.2-3B-Instruct-Q4_K_M.gguf")
MODEL_1B_PATH = os.path.join(LLM_DIR, "Llama-3.2-1B-Instruct-Q4_K_M.gguf")

# Prefer the smarter 3B model if fully downloaded (>= 2 GB), otherwise fall back to 1B
def _get_default_model():
    if os.path.exists(MODEL_3B_PATH) and os.path.getsize(MODEL_3B_PATH) >= 2_000_000_000:
        return MODEL_3B_PATH
    return MODEL_1B_PATH

DEFAULT_MODEL_PATH = _get_default_model()


class LocalBrain:
    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        self.model_path = model_path
        self.llm = None
        self.available = False
        self.history: List[dict] = []

        if Llama is None:
            print("[Brain] llama_cpp not installed. Falling back to rule-based responses.")
            return

        if not os.path.exists(self.model_path):
            print(f"[Brain] Notice: Local model not found at {self.model_path}. Run ./download_models.sh to fetch it.")
            return

        try:
            print(f"[Brain] Loading local LLM: {os.path.basename(self.model_path)}...")
            self.llm = Llama(
                model_path=self.model_path,
                n_ctx=2048,
                n_threads=4,
                n_gpu_layers=0,
                verbose=False,
            )
            self.available = True
            print("[Brain] Local LLM Brain loaded and ready.")
        except Exception as e:
            print(f"[Brain] Failed to load model ({e}). Using rule-based fallback.")

        self.reset_history()

    def reset_history(self) -> None:
        """Resets conversational history and re-injects the current memory context."""
        system_prompt = memory.get_llm_system_prompt()
        self.history = [{"role": "system", "content": system_prompt}]

    def chat(self, user_text: str) -> str:
        """Performs continuous multi-turn dialogue with conversation memory."""
        if not self.available or self.llm is None:
            return "Welcome home, Timilehin. Good to have you back."

        # Keep history from growing beyond context limit
        if len(self.history) > 12:
            system_msg = self.history[0]
            # Keep recent 8 turns + system message
            self.history = [system_msg] + self.history[-8:]

        self.history.append({"role": "user", "content": user_text})

        try:
            response = self.llm.create_chat_completion(
                messages=self.history,
                max_tokens=180,
                temperature=0.6,
            )
            reply = response["choices"][0]["message"]["content"].strip()
            if reply.startswith('"') and reply.endswith('"'):
                reply = reply[1:-1].strip()

            self.history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            print(f"[Brain] Chat error ({e}), falling back...")
            return "Got it."

    def generate_response(self, user_text: str) -> str:
        """Single-turn wrapper that starts a fresh conversation."""
        self.reset_history()
        return self.chat(user_text)


# Global singleton
brain = LocalBrain()
