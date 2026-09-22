"""
MODEL CONFIGURATION.  Author: Aditi.

Model names live here and nowhere else. Swapping a model is a one-line edit to
this file - no logic changes anywhere in the agent.

Everything runs against a local Ollama. No cloud, no external calls.

If a model here is not pulled on the machine, ask_model falls back to the
general model rather than failing - see agent/models.py. That fallback is
silent by design, so a mistyped name looks like a working route that never
uses the model you intended. Check these against `ollama list`.
"""

OLLAMA_BASE_URL = "http://localhost:11434"

MODELS = {
    # Tested on this corpus, 15-16 September 2026:
    #   qwen3.5:9b   better analysis - read across four documents and connected
    #                the seal trend to the blocked strainer. But failed to call
    #                write_pptx on a template conversion and claimed success.
    #   qwen3:4b     thinner analysis, calls its tools reliably. The build the
    #                demo was rehearsed on.
    "general": "qwen3.5:9b",
    # "general": "qwen3:4b",

    #   qwen3.5:9b        native tool calling, and better at ignoring the
    #                     retrieved passages when they are irrelevant.
    #   qwen2.5-coder:3b  followed five passages about seal failures instead of
    #                     the instruction, and did arithmetic on numbers nobody
    #                     had asked about.
    "coding":  "qwen3.5:9b",
    # "coding":  "qwen2.5-coder:3b",

    # No text-only substitute. A vision route without a vision model answers
    # about an image it cannot see, which is worse than refusing.
    "vision":  "qwen3-vl:4b",
}
