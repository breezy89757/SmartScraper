"""
Azure OpenAI 客戶端 (使用 MAF)
使用 Microsoft Agent Framework 的 AzureOpenAIResponsesClient
"""
import os
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ChatResponse:
    """聊天回應"""
    content: str
    usage: Optional[Dict] = None
    api_type: str = "maf"


class AzureOpenAIClient:
    """
    Azure OpenAI 客戶端 (使用 MAF)
    使用 AzureOpenAIResponsesClient 處理 Responses API
    """
    
    def __init__(
        self,
        deployment: Optional[str] = None,
        prefer_responses: bool = True
    ):
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.deployment = deployment or os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-5.2-chat")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
        self.prefer_responses = prefer_responses
        
        self._agent = None
        self._maf_available = None
    
    async def _init_maf(self):
        """初始化 MAF 客戶端"""
        if self._maf_available is not None:
            return self._maf_available
        
        try:
            from agent_framework.azure import AzureOpenAIResponsesClient
            from azure.core.credentials import AzureKeyCredential
            
            # 使用 API Key 認證
            client = AzureOpenAIResponsesClient(
                endpoint=self.endpoint,
                deployment_name=self.deployment,
                api_version=self.api_version,
                api_key=self.api_key,
            )
            
            self._maf_client = client
            self._maf_available = True
            print("📡 MAF AzureOpenAIResponsesClient: 可用")
            return True
            
        except Exception as e:
            print(f"⚠️ MAF 初始化失敗: {e}，使用 httpx")
            self._maf_available = False
            return False
    
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.3,
        json_mode: bool = False,
        max_tokens: Optional[int] = None
    ) -> ChatResponse:
        """發送聊天請求"""
        if self.prefer_responses and await self._init_maf():
            return await self._chat_maf(messages, temperature)
        else:
            return await self._chat_completions(messages, temperature, json_mode, max_tokens)
    
    async def _chat_maf(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
    ) -> ChatResponse:
        """使用 MAF Responses API"""
        # 提取 system 和 user messages
        system_msg = ""
        user_msg = ""
        
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            elif msg["role"] == "user":
                content = msg["content"]
                if isinstance(content, list):
                    content = " ".join(c.get("text", "") for c in content if c.get("type") == "text")
                user_msg = content
        
        # 建立 agent 並執行
        agent = self._maf_client.create_agent(
            name="SmartScraperAgent",
            instructions=system_msg,
        )
        
        response = await agent.run(user_msg)
        
        return ChatResponse(
            content=str(response),
            api_type="maf_responses"
        )
    
    async def _chat_completions(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
        json_mode: bool,
        max_tokens: Optional[int]
    ) -> ChatResponse:
        """使用 Completions API (httpx)"""
        import httpx
        
        url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"
        
        payload = {
            "messages": messages,
            "temperature": temperature,
        }
        
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                url,
                headers={"api-key": self.api_key},
                json=payload
            )
            
            response.raise_for_status()
            result = response.json()
        
        content = result["choices"][0]["message"]["content"]
        
        return ChatResponse(
            content=content,
            usage=result.get("usage"),
            api_type="completions"
        )
    
    async def close(self):
        pass  # MAF 不需要手動關閉


# 測試
async def main():
    client = AzureOpenAIClient()
    
    response = await client.chat([
        {"role": "system", "content": "你是一個助手，回答要簡短"},
        {"role": "user", "content": "說 Hello"}
    ])
    
    print(f"API 類型: {response.api_type}")
    print(f"回應: {response.content}")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
