"""測試 Azure OpenAI 連接"""
import asyncio
from agents.openai_client import AzureOpenAIClient

async def test():
    client = AzureOpenAIClient()
    
    response = await client.chat([
        {"role": "user", "content": "Reply with just: Hello"}
    ])
    
    print(f"API 類型: {response.api_type}")
    print(f"回應內容: '{response.content}'")
    print(f"回應長度: {len(response.content)}")

if __name__ == "__main__":
    asyncio.run(test())
