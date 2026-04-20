import threading
import json
from app.config.settings import get_settings

settings = get_settings()


class LLMService:
    """
    Singleton-style LLM service for GGUF models.
    Ensures model is loaded only once per worker.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    # Don't init model here, wait until generate()
        return cls._instance

    def _init_model(self):
        """
        Load GGUF model once.
        """
        from llama_cpp import Llama

        print(f"📦 Loading LLM: {settings.LLM_MODEL_PATH}")
        self.model = Llama(
            model_path=settings.LLM_MODEL_PATH,
            n_ctx=settings.LLM_CTX_SIZE,
            n_threads=settings.LLM_THREADS,
            n_gpu_layers=settings.LLM_GPU_LAYERS,
            verbose=False,
        )

        # optional lock for inference safety
        self.inference_lock = threading.Lock()

    def generate(self, prompt: str, schema: dict = None) -> str:
        """
        Generate text from LLM.
        If schema is provided, forces JSON output matching that schema.
        """

        # Lazy init model only when needed
        if not hasattr(self, "model"):
            with self._lock:
                if not hasattr(self, "model"):
                    self._init_model()

        with self.inference_lock:
            # If schema provided, use grammar-constrained sampling
            extra_args = {}
            if schema:
                from llama_cpp.llama_grammar import LlamaGrammar
                # Convert JSON schema to GBNF grammar (llama-cpp-python helper)
                grammar = LlamaGrammar.from_json_schema(json.dumps(schema))
                extra_args["grammar"] = grammar

            output = self.model(
                prompt,
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
                stop=["</s>", "\n\n\n"],
                **extra_args
            )

        return output["choices"][0]["text"].strip()