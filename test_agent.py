import asyncio
import os
from dotenv import load_dotenv
from browser_use import Agent, Browser
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

async def test_agent():
    print("Initializing Agent and Browser Configuration...")
    
    # Load paths from your .env file
    chrome_path = os.getenv("CHROME_PATH")
    user_data = os.getenv("CHROME_USER_DATA")
    profile = os.getenv("CHROME_PROFILE")
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not all([chrome_path, user_data, profile, api_key]):
        print("Error: Missing required environment variables in .env (CHROME_PATH, CHROME_USER_DATA, CHROME_PROFILE, or GEMINI_API_KEY).")
        return

    print(f"Chrome Path: {chrome_path}")
    print(f"User Data Dir: {user_data}")
    print(f"Profile Directory: {profile}")
    print("Connecting to Chrome profile...")
    
    # Initialize the browser (API v0.12.6)
    browser = Browser(
        executable_path=chrome_path,
        user_data_dir=user_data,
        profile_directory=profile,
        headless=False,
    )
    
    # Initialize the Gemini model
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")

    # Define the task for the Agent
    # Note: Replace 'your.email@example.com' with your actual email address before running.
    task_description = (
        "Go to gmail.com. "
        "Click on the 'Compose' button to start a new email. "
        "Set the recipient to 'your.email@example.com'. "
        "Set the subject to 'Test from Browser Use Agent'. "
        "Set the body to 'Hello! This is an automated test from the Deep Work Pilot using browser-use and Gemini 2.0 Flash.' "
        "Do NOT click send. Just leave the draft open."
    )
    
    print(f"\nTask: {task_description}\n")
    
    # Create the Agent
    agent = Agent(
        task=task_description,
        llm=llm,
        browser=browser
    )
    
    try:
        print("Starting Agent execution...")
        # Run the agent
        result = await agent.run()
        print("\nAgent finished executing.")
        
        print("\nPress Ctrl+C to close the browser and exit.")
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"\nERROR: Agent execution failed.")
        print(f"Details: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            await browser.stop()
        except Exception:
            pass

if __name__ == "__main__":
    # Remember to close all Chrome windows and update the email address before running!
    asyncio.run(test_agent())
