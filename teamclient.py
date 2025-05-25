import asyncio
from fastmcp import Client

client = Client("teamserver.py")

async def call_tool(name: str):
    async with client:
        #result = await client.call_tool("greet", {"name": name})
        result = await client.call_tool("list_contacts")
        print(result)

async def call_list_contact_tool():
    async with client:
        result = await client.call_tool("list_contacts")
        print(result)

#asyncio.run(call_tool("Ford"))
asyncio.run(call_list_contact_tool())