#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
提供商工厂和路由机制
负责根据模型名称自动选择合适的提供商
"""

import time
from typing import Dict, List, Optional, Union, AsyncGenerator, Any
from app.providers.base import BaseProvider, provider_registry
from app.providers.zai_provider import ZAIProvider
from app.providers.k2think_provider import K2ThinkProvider
from app.providers.longcat_provider import LongCatProvider
from app.models.schemas import OpenAIRequest
from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger()


class ProviderFactory:
    """提供商工厂"""
    
    def __init__(self):
        self._initialized = False
        self._default_provider = "zai"
    
    def initialize(self):
        """初始化所有提供商"""
        if self._initialized:
            return

        try:
            # 注册 Z.AI 提供商
            zai_provider = ZAIProvider()
            provider_registry.register(
                zai_provider, 
                zai_provider.get_supported_models()
            )
            
            # 注册 K2Think 提供商
            k2think_provider = K2ThinkProvider()
            provider_registry.register(
                k2think_provider,
                k2think_provider.get_supported_models()
            )
            
            # 注册 LongCat 提供商
            longcat_provider = LongCatProvider()
            provider_registry.register(
                longcat_provider,
                longcat_provider.get_supported_models()
            )
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"❌ 提供商工厂初始化失败: {e}")
            raise
    
    def get_provider_for_model(self, model: str) -> Optional[BaseProvider]:
        """根据模型名称获取提供商"""
        if not self._initialized:
            self.initialize()
        
        # 首先尝试从配置的映射中获取
        provider_mapping = settings.provider_model_mapping
        provider_name = provider_mapping.get(model)
        
        if provider_name:
            provider = provider_registry.get_provider_by_name(provider_name)
            if provider:
                logger.debug(f"🎯 模型 {model} 映射到提供商 {provider_name}")
                return provider
        
        # 尝试从注册表中直接获取
        provider = provider_registry.get_provider(model)
        if provider:
            logger.debug(f"🎯 模型 {model} 找到提供商 {provider.name}")
            return provider
        
        # 使用默认提供商
        default_provider = provider_registry.get_provider_by_name(self._default_provider)
        if default_provider:
            logger.warning(f"⚠️ 模型 {model} 未找到专用提供商，使用默认提供商 {self._default_provider}")
            return default_provider
        
        logger.error(f"❌ 无法为模型 {model} 找到任何提供商")
        return None
    
    def list_supported_models(self) -> List[str]:
        """列出所有支持的模型"""
        if not self._initialized:
            self.initialize()
        return provider_registry.list_models()
    
    def list_providers(self) -> List[str]:
        """列出所有提供商"""
        if not self._initialized:
            self.initialize()
        return provider_registry.list_providers()
    
    def get_models_for_provider(self, provider_name: str) -> List[str]:
        """获取指定提供商支持的模型"""
        if not self._initialized:
            self.initialize()
        
        provider = provider_registry.get_provider_by_name(provider_name)
        if provider:
            return provider.get_supported_models()
        return []


class ProviderRouter:
    """提供商路由器"""
    
    def __init__(self):
        self.factory = ProviderFactory()
    
    async def route_request(
        self, 
        request: OpenAIRequest,
        **kwargs
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """路由请求到合适的提供商"""
        logger.info(f"🚦 路由请求: 模型={request.model}, 流式={request.stream}")
        
        # 获取提供商
        provider = self.factory.get_provider_for_model(request.model)
        if not provider:
            error_msg = f"不支持的模型: {request.model}"
            logger.error(f"❌ {error_msg}")
            return {
                "error": {
                    "message": error_msg,
                    "type": "invalid_request_error",
                    "code": "model_not_found"
                }
            }
        
        logger.info(f"✅ 使用提供商: {provider.name}")
        
        try:
            # 调用提供商处理请求
            # 检查是否使用请求中的API Key
            if settings.USE_REQUEST_API_KEY and request.api_key:
                kwargs['api_key'] = request.api_key

            result = await provider.chat_completion(request, **kwargs)
            logger.info(f"🎉 请求处理完成: {provider.name}")
            return result
            
        except Exception as e:
            error_msg = f"提供商 {provider.name} 处理请求失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return provider.handle_error(e, "路由处理")
    
    def get_models_list(self) -> Dict[str, Any]:
        """获取模型列表（OpenAI格式）"""
        models = []
        current_time = int(time.time())
        
        # 按提供商分组获取模型
        for provider_name in self.factory.list_providers():
            provider_models = self.factory.get_models_for_provider(provider_name)
            for model in provider_models:
                models.append({
                    "id": model,
                    "object": "model",
                    "created": current_time,
                    "owned_by": provider_name
                })
        
        return {
            "object": "list",
            "data": models
        }


# 全局路由器实例
_router: Optional[ProviderRouter] = None


def get_provider_router() -> ProviderRouter:
    """获取全局提供商路由器"""
    global _router
    if _router is None:
        _router = ProviderRouter()
        # 确保工厂已初始化
        _router.factory.initialize()
    return _router


def initialize_providers():
    """初始化提供商系统"""
    logger.info("🚀 初始化提供商系统...")
    router = get_provider_router()
    logger.info("✅ 提供商系统初始化完成")
    return router
