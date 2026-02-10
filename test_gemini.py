import google.generativeai as genai
import config
import sys

def test_gemini():
    print(f"Testing Gemini API Key: {config.GEMINI_API_KEY[:10]}...")
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        print("Available models:")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
        
        model = genai.GenerativeModel('models/gemini-flash-latest')
        response = model.generate_content("Hello, this is a test.")
        print("Success! Gemini response:")
        print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_gemini()
