
from google import genai

client = genai.Client()

print("Please enter your first prompt:\n")
test_input = input()

interaction1 = client.interactions.create(
    model="gemini-3.5-flash-lite",
    #input="Explain how AI works in a few words"
    input = test_input
)
print(interaction1.output_text)

