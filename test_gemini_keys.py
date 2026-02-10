import google.generativeai as genai
import sys

# Test Gemini API Keys from config.py
keys = [
    "AIzaSyDi2D0hA3pZ8b4hIAEiRi8RsVxAu8gR6_E",
    "AIzaSyAQD9uIqK8KYmNcd5j9cJc6cSPYK1_smu8", 
    "AIzaSyBBjnEpVzo9VH7nfFHOFsW-0KsmUmqYdhs",
    "AIzaSyCxh_ANVqQVOAaK6LpVGshV53ungwIhK9E",
    "AIzaSyAzWAWbkqHSY5IteOS-G83gCL6r7TG7tIs"
]

print("Testing Gemini API Keys (Using 'models/gemini-2.0-flash-exp')...\n")
for i, key in enumerate(keys, 1):
    try:
        genai.configure(api_key=key)
        # Using exact same model name as ai_replier.py
        model = genai.GenerativeModel('models/gemini-2.0-flash-exp')
        
        response = model.generate_content("Say 'Working'")
        print(f"✅ Key {i}: WORKING")
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            print(f"❌ Key {i}: QUOTA EXCEEDED")
        elif "400" in error_msg:
            print(f"❌ Key {i}: INVALID KEY (400)")
        elif "403" in error_msg:
            print(f"❌ Key {i}: PERMISSION DENIED (403)")
        else:
            print(f"❌ Key {i}: ERROR - {error_msg[:100]}")

print("\n✅ Test Complete!")
