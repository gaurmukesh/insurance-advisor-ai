"""
Compatibility shim for a known upstream ragas bug: ragas/llms/base.py unconditionally
does `from langchain_community.chat_models.vertexai import ChatVertexAI`, a module path
that langchain-community removed. We never use VertexAI (OpenAI only), so this stubs
out just enough for that import line to succeed.
See: https://github.com/vibrantlabsai/ragas/issues/2745

Import this module before importing anything from `ragas`.
"""

import sys
import types

if "langchain_community.chat_models.vertexai" not in sys.modules:
    _shim = types.ModuleType("langchain_community.chat_models.vertexai")

    class ChatVertexAI:  # placeholder — never instantiated
        pass

    _shim.ChatVertexAI = ChatVertexAI
    sys.modules["langchain_community.chat_models.vertexai"] = _shim
