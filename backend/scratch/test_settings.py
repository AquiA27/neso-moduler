
import os
import sys

# Ensure backend path is in sys.path
sys.path.append(os.getcwd())

from app.core.config import settings

def test():
    print(f"DEBUG: VITE_API_URL ENV: {os.environ.get('VITE_API_URL')}")
    print(f"DEBUG: OPENAI_API_KEY in OsEnviron: {'SET' if os.environ.get('OPENAI_API_KEY') else 'NONE'}")
    print(f"Settings API KEY (masked): {settings.OPENAI_API_KEY[:10] if settings.OPENAI_API_KEY else 'None'}...")
    print(f"LLM ENABLED: {settings.ASSISTANT_ENABLE_LLM}")
    print(f"MODEL: {settings.OPENAI_MODEL}")

if __name__ == "__main__":
    test()
