import google.generativeai as genai

# Replace with your actual key
api_key = "YOUR_API_KEY"

try:

    genai.configure(api_key='AIzaSyDtaqP73ub3cZ5L_VZAZHTrdnn3TP_b-Bk')

    # Try a small test prompt
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    response = model.generate_content("Say hello in a fun way.")

    print("✅ API Key is valid!")
    print("Response:", response.text.strip())

except Exception as e:
    print("❌ API Key might be invalid or there's another issue.")
    print("Error message:", str(e))
