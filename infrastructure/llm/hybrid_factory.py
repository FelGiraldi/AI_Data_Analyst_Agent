# infrastructure/llm/hybrid_factory.py
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

class HybridLLMFactory:
    @staticmethod
    def get_model(temperature: float = 0):
        """
        Retorna un modelo LLM con estrategia de Fallback:
        Intenta Gemini 2.5 -> Si falla -> Usa Groq (Llama 3).
        """
        
        # 1. Configurar el Primario (Google Gemini)
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if google_api_key:
            gemini = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash", 
                temperature=temperature,
                google_api_key=google_api_key,
                max_retries=1,        
                request_timeout=10,
            )
        else:
            gemini = None

        # 2. Configurar el Secundario (Groq Llama 3)
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY es obligatoria para el fallback")
            
        groq = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            temperature=temperature,
            groq_api_key=groq_api_key,
            max_retries=3
        )

        # 3. Crear la cadena de Resiliencia
        if gemini:
            # Si gemini lanza error, sigue Groq
            return gemini.with_fallbacks([groq])
        else:
            print("⚠️ Aviso: GOOGLE_API_KEY no encontrada. Usando solo Groq.")
            return groq