# TODO: Check if url should be blocked (Gemini API)
import os
from urllib import response
from dotenv import load_dotenv
from google import genai

load_dotenv()


def check_blacklist(url: str) -> bool:
    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=f"Check if this domain would ever be detrimental to schoolwork, be more harsh when deciding detrimentalness: {url},respond with only 'Yes' or 'No'."
    )
    print(response.text)
    return response.text.strip().lower() == "yes"
check_blacklist("https://github.com/Azurinine/diamondhack2026")