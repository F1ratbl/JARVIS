import ollama


def main():
    try:
        for response in ollama.pull('mistral:7b-q2', stream=True):
            print(response)
    except Exception as e:
        print("Error:", e)


if __name__ == "__main__":
    main()
