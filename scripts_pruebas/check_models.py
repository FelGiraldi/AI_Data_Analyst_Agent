import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

def list_available_models():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ Error: No se encontró GOOGLE_API_KEY")
        return

    genai.configure(api_key=api_key)
    
    print("--- 🔍 Modelos Disponibles para tu API Key ---")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"✅ {m.name}")
    except Exception as e:
        print(f"❌ Error al listar modelos: {str(e)}")

if __name__ == "__main__":
    list_available_models()