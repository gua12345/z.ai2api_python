#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
基础提供商抽象层
定义统一的提供商接口规范
"""

import json
import time
import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, AsyncGenerator, Union
from dataclasses import dataclass

from app.models.schemas import OpenAIRequest, Message
from app.utils.logger import get_logger

logger = get_logger()


@dataclass
class ProviderConfig:
    """提供商配置"""
    name: str
    api_endpoint: str
    timeout: int = 30
    headers: Optional[Dict[str, str]] = None
    extra_config: Optional[Dict[str, Any]] = None


@dataclass
class ProviderResponse:
    """提供商响应"""
    success: bool
    content: str = ""
    error: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    extra_data: Optional[Dict[str, Any]] = None


class BaseProvider(ABC):
    """基础提供商抽象类"""
    
    def __init__(self, config: ProviderConfig):
        """初始化提供商"""
        self.config = config
        self.name = config.name
        self.logger = get_logger()
        
    @abstractmethod
    async def chat_completion(
        self, 
        request: OpenAIRequest,
        api_key: Optional[str] = None,
        **kwargs
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """
        聊天完成接口
        
        Args:
            request: OpenAI格式的请求
            **kwargs: 额外参数
            
        Returns:
            非流式: Dict[str, Any] - OpenAI格式的响应
            流式: AsyncGenerator[str, None] - SSE格式的流式响应
        """
        pass
    
    @abstractmethod
    async def transform_request(self, request: OpenAIRequest) -> Dict[str, Any]:
        """
        转换OpenAI请求为提供商特定格式
        
        Args:
            request: OpenAI格式的请求
            
        Returns:
            Dict[str, Any]: 提供商特定格式的请求
        """
        pass
    
    @abstractmethod
    async def transform_response(
        self, 
        response: Any, 
        request: OpenAIRequest
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """
        转换提供商响应为OpenAI格式
        
        Args:
            response: 提供商的原始响应
            request: 原始请求（用于构造响应）
            
        Returns:
            Union[Dict[str, Any], AsyncGenerator[str, None]]: OpenAI格式的响应
        """
        pass
    
    def get_supported_models(self) -> List[str]:
        """获取支持的模型列表"""
        return []
    
    def create_chat_id(self) -> str:
        """生成聊天ID"""
        return f"chatcmpl-{uuid.uuid4().hex}"
    
    def create_openai_chunk(
        self, 
        chat_id: str, 
        model: str, 
        delta: Dict[str, Any], 
        finish_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建OpenAI格式的流式响应块"""
        return {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
                "logprobs": None,
            }],
            "system_fingerprint": f"fp_{self.name}_001",
        }
    
    def create_openai_response(
        self, 
        chat_id: str, 
        model: str, 
        content: str, 
        usage: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """创建OpenAI格式的非流式响应"""
        return {
            "id": chat_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop",
                "logprobs": None,
            }],
            "usage": usage or {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            },
            "system_fingerprint": f"fp_{self.name}_001",
        }

    def create_openai_response_with_reasoning(
        self,
        chat_id: str,
        model: str,
        content: str,
        reasoning_content: str = None,
        usage: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """创建包含推理内容的OpenAI格式非流式响应"""
        message = {
            "role": "assistant",
            "content": content
        }

        # 只有当推理内容存在且不为空时才添加
        if reasoning_content and reasoning_content.strip():
            message["reasoning_content"] = reasoning_content

        return {
            "id": chat_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": message,
                "finish_reason": "stop",
                "logprobs": None,
            }],
            "usage": usage or {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            },
            "system_fingerprint": f"fp_{self.name}_001",
        }

    async def format_sse_chunk(self, chunk: Dict[str, Any]) -> str:
        """格式化SSE响应块"""
        return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    
    async def format_sse_done(self) -> str:
        """格式化SSE结束标记"""
        return "data: [DONE]\n\n"
    
    def log_request(self, request: OpenAIRequest):
        """记录请求日志"""
        self.logger.info(f"🔄 {self.name} 处理请求: {request.model}")
        self.logger.debug(f"  消息数量: {len(request.messages)}")
        self.logger.debug(f"  流式模式: {request.stream}")
        
    def log_response(self, success: bool, error: Optional[str] = None):
        """记录响应日志"""
        if success:
            self.logger.info(f"✅ {self.name} 响应成功")
        else:
            self.logger.error(f"❌ {self.name} 响应失败: {error}")
    
    def handle_error(self, error: Exception, context: str = "") -> Dict[str, Any]:
        """统一错误处理"""
        error_msg = f"{self.name} {context} 错误: {str(error)}"
        self.logger.error(error_msg)
        
        return {
            "error": {
                "message": error_msg,
                "type": "provider_error",
                "code": "internal_error"
            }
        }


class ProviderRegistry:
    """提供商注册表"""
    
    def __init__(self):
        self._providers: Dict[str, BaseProvider] = {}
        self._model_mapping: Dict[str, str] = {}
    
    def register(self, provider: BaseProvider, models: List[str]):
        """注册提供商"""
        self._providers[provider.name] = provider
        for model in models:
            self._model_mapping[model] = provider.name
        logger.info(f"📝 注册提供商: {provider.name}, 模型: {models}")
    
    def get_provider(self, model: str) -> Optional[BaseProvider]:
        """根据模型获取提供商"""
        provider_name = self._model_mapping.get(model)
        if provider_name:
            return self._providers.get(provider_name)
        return None
    
    def get_provider_by_name(self, name: str) -> Optional[BaseProvider]:
        """根据名称获取提供商"""
        return self._providers.get(name)
    
    def list_models(self) -> List[str]:
        """列出所有支持的模型"""
        return list(self._model_mapping.keys())
    
    def list_providers(self) -> List[str]:
        """列出所有提供商"""
        return list(self._providers.keys())


# 全局提供商注册表
provider_registry = ProviderRegistry()
