import os
from dotenv import load_dotenv

load_dotenv()

print("GEMINI_API_KEY exists:", bool(os.getenv("GEMINI_API_KEY")))
print("GEMINI_IMAGE_MODEL:", os.getenv("GEMINI_IMAGE_MODEL"))
print("OMISE_PUBLIC_KEY exists:", bool(os.getenv("OMISE_PUBLIC_KEY")))
