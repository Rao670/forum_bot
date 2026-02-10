import google.generativeai as genai

keys = [
    "AIzaSyDi2D0hA3pZ8b4hIAEiRi8RsVxAu8gR6_E",
    "AIzaSyAQD9uIqK8KYmNcd5j9cJc6cSPYK1_smu8", 
    "AIzaSyBBjnEpVzo9VH7nfFHOFsW-0KsmUmqYdhs",
    "AIzaSyCxh_ANVqQVOAaK6LpVGshV53ungwIhK9E",
    "AIzaSyAzWAWbkqHSY5IteOS-G83gCL6r7TG7tIs"
]

print("--- TESTING models/gemini-flash-latest ---\n")

for i, key in enumerate(keys, 1):
    print(f"Testing Key {i}:")
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('models/gemini-flash-latest')
        response = model.generate_content("Hi")
        print(f"  ✅ WORKING")
    except Exception as e:
        err = str(e).lower()
        if "429" in err or "quota" in err:
            print(f"  ❌ QUOTA EXCEEDED")
        else:
            print(f"  ❌ ERROR: {str(e)[:100]}")
    print("-" * 20)
