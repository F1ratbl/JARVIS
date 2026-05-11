import ollama
try:
    for response in ollama.pull('mistral:7b-q2', stream=True):
        print(response)
except Exception as e:
    print("Error:", e)
