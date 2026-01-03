"""
沙箱執行器
安全地執行 AI 生成的爬蟲程式碼
"""
import sys
import io
from typing import Any, Dict, Optional
from dataclasses import dataclass
import traceback


@dataclass
class ExecutionResult:
    """執行結果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    stdout: str = ""


# 允許的模組白名單
ALLOWED_MODULES = {
    "requests",
    "bs4",
    "BeautifulSoup",
    "json",
    "re",
    "datetime",
    "time",
}

# 禁止的內建函數
BLOCKED_BUILTINS = {
    "exec", "eval", "compile",
    "open", "input",
    "__import__",
    "globals", "locals",
    "getattr", "setattr", "delattr",
    "breakpoint",
}


def create_safe_globals() -> Dict:
    """
    建立安全的 globals 環境
    """
    import requests
    from bs4 import BeautifulSoup
    import json
    import re
    from datetime import datetime
    import builtins
    
    # 允許的模組 (常用爬蟲模組)
    allowed_imports = {
        "requests": requests,
        "bs4": __import__("bs4"),
        "json": json,
        "re": re,
        "datetime": __import__("datetime"),
        "time": __import__("time"),
        "typing": __import__("typing"),  # 型別提示
        "collections": __import__("collections"),
        "urllib": __import__("urllib"),
    }
    
    # 受限的 __import__
    def safe_import(name, *args, **kwargs):
        if name in allowed_imports:
            return allowed_imports[name]
        raise ImportError(f"模組 '{name}' 不在白名單中")
    
    # 建立受限的 builtins
    safe_builtins = {}
    for name in dir(builtins):
        if name not in BLOCKED_BUILTINS and not name.startswith("_"):
            try:
                safe_builtins[name] = getattr(builtins, name)
            except:
                pass
    
    # 加入受限的 __import__
    safe_builtins["__import__"] = safe_import
    
    return {
        "__builtins__": safe_builtins,
        "__name__": "__main__",  # 讓 if __name__ == "__main__" 可以執行
        "requests": requests,
        "BeautifulSoup": BeautifulSoup,
        "json": json,
        "re": re,
        "datetime": datetime,
        "print": print,
    }


class SandboxExecutor:
    """
    沙箱執行器
    在受限環境中執行程式碼
    """
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    def execute(self, code: str, url: str) -> ExecutionResult:
        """
        執行爬蟲程式碼
        
        Args:
            code: Python 程式碼
            url: 目標網址
            
        Returns:
            ExecutionResult
        """
        # 捕獲 stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()
        
        try:
            # 檢查危險關鍵字
            dangerous_keywords = ["os.", "subprocess", "socket", "eval(", "exec("]
            for keyword in dangerous_keywords:
                if keyword in code:
                    return ExecutionResult(
                        success=False,
                        error=f"禁止使用危險關鍵字: {keyword}"
                    )
            
            # 建立安全環境
            # 重要：使用同一個 dict 作為 globals 和 locals
            # 這樣函數之間才能互相呼叫
            exec_globals = create_safe_globals()
            
            # 執行程式碼 (定義函數)
            # 只傳一個 dict，這樣定義的函數會在同一個 namespace
            exec(code, exec_globals)
            
            # 呼叫 scrape 函數
            if "scrape" not in exec_globals:
                return ExecutionResult(
                    success=False,
                    error="程式碼必須定義 scrape(url) 函數"
                )
            
            scrape_func = exec_globals["scrape"]
            result = scrape_func(url)
            
            return ExecutionResult(
                success=True,
                data=result,
                stdout=captured_output.getvalue()
            )
            
        except ModuleNotFoundError as e:
            # 提供安裝指令
            module_name = str(e).split("'")[1] if "'" in str(e) else str(e)
            install_hints = {
                "bs4": "uv add beautifulsoup4",
                "beautifulsoup4": "uv add beautifulsoup4",
                "requests": "uv add requests",
            }
            install_cmd = install_hints.get(module_name, f"uv add {module_name}")
            
            return ExecutionResult(
                success=False,
                error=f"缺少模組: {module_name}\n\n請執行安裝指令:\n{install_cmd}",
                stdout=captured_output.getvalue()
            )
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            
            # 簡化錯誤訊息，不要整個 traceback
            if "scrape" in str(e):
                error_msg = "程式碼執行錯誤，請檢查 scrape() 函數"
            
            return ExecutionResult(
                success=False,
                error=error_msg,
                stdout=captured_output.getvalue()
            )
        finally:
            sys.stdout = old_stdout


# 測試
if __name__ == "__main__":
    executor = SandboxExecutor()
    
    # 測試程式碼
    test_code = '''
import requests
from bs4 import BeautifulSoup

def scrape(url):
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    title = soup.find('title')
    return {"title": title.text if title else "N/A"}
'''
    
    result = executor.execute(test_code, "https://www.google.com")
    print(f"Success: {result.success}")
    print(f"Data: {result.data}")
    if result.error:
        print(f"Error: {result.error}")
