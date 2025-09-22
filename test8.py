import ollama

response = ollama.chat(model="deepseek-r1:7b", messages=[{"role": "user", "content": "What floor is U-203 on?"}])
print(response)
