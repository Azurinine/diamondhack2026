import asyncio
import os
from browser_use import Browser, Agent, ChatGoogle
from dotenv import load_dotenv

load_dotenv()

async def main():
    
    # 2. Start the browser with that config
    browser = Browser.from_system_chrome(
        profile_directory=os.getenv("CHROME_PROFILE"),
    )
    
    # 3. Create the agent
    agent = Agent(
        task="Navigate to my gmail and draft an email to myself. Do not send the email.",
        browser=browser,
        llm=ChatGoogle(model="gemini-flash-latest"),
    )
    
    result = await agent.run()
    print(result)

if __name__ == "__main__":
    asyncio.run(main())