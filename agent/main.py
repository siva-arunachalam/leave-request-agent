import asyncio
from model import azure_openai_model
from pydantic_ai import Agent
from tools import available_tools
from rich.console import Console
from rich.markdown import Markdown

c = Console()
agent = Agent(
    model=azure_openai_model(), 
    tools=available_tools, 
    system_prompt="pay attention to the context of dates in user queries. use tools to get current date if required. ask for employee id if needed. do not guess dates of holidays, instead use tools."
)

async def main():
    response = None
    while True:
        user_prompt = c.input("[User 😺]: ")
        if user_prompt.lower() in ['bye', 'quit', 'exit']:
            break
        if not response:
            message_history = []
        response = await agent.run(user_prompt, message_history=message_history)
        message_history = response.all_messages()
        # print(f"History: ")
        # for m in message_history:
        #     print(f"{m.kind}: {m.parts}")

        c.print(f"[Agent 🌴]:", end="")
        c.print(Markdown(response.data))

if __name__ == "__main__":
    r = asyncio.run(main())
