from gpt4all import GPT4All

model_path = r"C:\inventi-rag\models\mistral-7b-instruct-v0.1.Q4_K_S.gguf"
model = GPT4All(model_path)
response = model.generate("How are you?")
print(response)
