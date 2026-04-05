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
        contents=f"Check if this domain is a social media site,: {url},"
    )
    print(response.text)
    return response.text.strip().lower() == "yes"
check_blacklist("https://www.youtube.com")
check_blacklist("https://www.facebook.com" )
check_blacklist("https://www.instagram.com")
