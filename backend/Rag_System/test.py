from gpt4all import GPT4All

model = GPT4All("Phi-3-mini-4k-instruct-q4.gguf", model_path="backend/Rag_System/models")
response = model.generate("How are you?")
print(response)
