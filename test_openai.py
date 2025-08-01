import os
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
print("Initializing OpenAI client...")
client = OpenAI(api_key=OPENAI_API_KEY)
print("OpenAI client initialized successfully.")
print("Testing chat completion...")
try:
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello"}],
        timeout=20, # Add a timeout
    )
    print("Chat completion successful.")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"An error occurred: {e}")
