#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import json
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from app.core.config import settings
from app.models.schemas import OpenAIRequest, Message, ModelsResponse, Model, OpenAIResponse, Choice, Usage
from app.utils.logger import get_logger
from app.providers import get_provider_router
from app.utils.token_pool import get_token_pool

logger = get_logger()
router = APIRouter()

# 全局提供商路由器实例
provider_router = None


def get_provider_router_instance():
    """获取提供商路由器实例"""
    global provider_router
    if provider_router is None:
        provider_router = get_provider_router()
    return provider_router


def create_chunk(chat_id: str, model: str, delta: Dict[str, Any], finish_reason: Optional[str] = None) -> Dict[str, Any]:
    """创建标准的 OpenAI chunk 结构"""
    return {
        "choices": [{
            "delta": delta,
            "finish_reason": finish_reason,
            "index": 0,
            "logprobs": None,
        }],
        "created": int(time.time()),
        "id": chat_id,
        "model": model,
        "object": "chat.completion.chunk",
        "system_fingerprint": "fp_zai_001",
    }


async def handle_non_stream_response(stream_response, request: OpenAIRequest) -> JSONResponse:
    """处理非流式响应"""
    logger.info("📄 开始处理非流式响应")

    # 收集所有流式数据
    full_content = []
    async for chunk_data in stream_response():
        if chunk_data.startswith("data: "):
            chunk_str = chunk_data[6:].strip()
            if chunk_str and chunk_str != "[DONE]":
                try:
                    chunk = json.loads(chunk_str)
                    if "choices" in chunk and chunk["choices"]:
                        choice = chunk["choices"][0]
                        if "delta" in choice and "content" in choice["delta"]:
                            content = choice["delta"]["content"]
                            if content:
                                full_content.append(content)
                except json.JSONDecodeError:
                    continue

    # 构建响应
    response_data = OpenAIResponse(
        id=f"chatcmpl-{int(time.time())}",
        object="chat.completion",
        created=int(time.time()),
        model=request.model,
        choices=[Choice(
            index=0,
            message=Message(
                role="assistant",
                content="".join(full_content),
                tool_calls=None
            ),
            finish_reason="stop"
        )],
        usage=Usage(
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0
        )
    )

    logger.info("✅ 非流式响应处理完成")
    return JSONResponse(content=response_data.model_dump(exclude_none=True))


@router.get("/v1/models")
async def list_models():
    """List available models from all providers"""
    try:
        router_instance = get_provider_router_instance()
        models_data = router_instance.get_models_list()
        return JSONResponse(content=models_data)
    except Exception as e:
        logger.error(f"❌ 获取模型列表失败: {e}")
        # 返回默认模型列表作为后备
        current_time = int(time.time())
        fallback_response = ModelsResponse(
            data=[
                Model(id=settings.PRIMARY_MODEL, created=current_time, owned_by="z.ai"),
                Model(id=settings.THINKING_MODEL, created=current_time, owned_by="z.ai"),
                Model(id=settings.SEARCH_MODEL, created=current_time, owned_by="z.ai"),
                Model(id=settings.AIR_MODEL, created=current_time, owned_by="z.ai"),
            ]
        )
        return fallback_response


@router.post("/v1/chat/completions")
async def chat_completions(request: OpenAIRequest, authorization: str = Header(...)):
    """Handle chat completion requests with multi-provider architecture"""
    role = request.messages[0].role if request.messages else "unknown"
    logger.info(f"😶‍🌫️ 收到客户端请求 - 模型: {request.model}, 流式: {request.stream}, 消息数: {len(request.messages)}, 角色: {role}, 工具数: {len(request.tools) if request.tools else 0}")

    try:
        # Validate API key (skip if SKIP_AUTH_TOKEN is enabled)
        if not settings.SKIP_AUTH_TOKEN:
            if not authorization.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

            api_key = authorization[7:]
            if api_key != settings.AUTH_TOKEN:
                raise HTTPException(status_code=401, detail="Invalid API key")

        # 如果启用了USE_REQUEST_API_KEY，则使用请求头中的API Key
        if settings.USE_REQUEST_API_KEY:
            # 从Authorization头中提取API Key
            header_api_key = authorization[7:]
            # 如果请求头中的api_key等于主AUTH_TOKEN，则强制使用token池
            if header_api_key:
                if header_api_key == settings.AUTH_TOKEN:
                    logger.info("🔑 检测到主AUTH_TOKEN，强制使用token池机制")
                    request.api_key = None
                else:
                    logger.info("🔑 使用请求头中的API Key覆盖请求体中的API Key")
                    request.api_key = header_api_key

        # 使用多提供商路由器处理请求
        router_instance = get_provider_router_instance()
        result = await router_instance.route_request(request)

        # 检查是否有错误
        if isinstance(result, dict) and "error" in result:
            error_info = result["error"]
            if error_info.get("code") == "model_not_found":
                raise HTTPException(status_code=404, detail=error_info["message"])
            else:
                raise HTTPException(status_code=500, detail=error_info["message"])

        # 处理响应
        if request.stream:
            # 流式响应
            if hasattr(result, '__aiter__'):
                # 结果是异步生成器
                return StreamingResponse(
                    result,
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "Access-Control-Allow-Origin": "*",
                    }
                )
            else:
                # 结果是字典，可能包含错误
                raise HTTPException(status_code=500, detail="Expected streaming response but got non-streaming result")
        else:
            # 非流式响应
            if isinstance(result, dict):
                return JSONResponse(content=result)
            else:
                # 如果是异步生成器，需要收集所有内容
                return await handle_non_stream_response(result, request)

    except HTTPException:
        # 重新抛出 HTTP 异常
        raise
    except Exception as e:
        logger.error(f"❌ 请求处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Token pool management endpoints


@router.get("/v1/token-pool/status")
async def get_token_pool_status():
    """获取token池状态信息"""
    try:
        token_pool = get_token_pool()
        if not token_pool:
            return {
                "status": "disabled",
                "message": "Token池未初始化，当前仅使用匿名模式",
                "anonymous_mode": settings.ANONYMOUS_MODE,
                "auth_tokens_file": settings.AUTH_TOKENS_FILE,
                "auth_tokens_configured": len(settings.auth_token_list) > 0
            }

        pool_status = token_pool.get_pool_status()
        return {
            "status": "active",
            "pool_info": pool_status,
            "config": {
                "anonymous_mode": settings.ANONYMOUS_MODE,
                "failure_threshold": settings.TOKEN_FAILURE_THRESHOLD,
                "recovery_timeout": settings.TOKEN_RECOVERY_TIMEOUT,
                "health_check_interval": settings.TOKEN_HEALTH_CHECK_INTERVAL
            }
        }
    except Exception as e:
        logger.error(f"获取token池状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get token pool status: {str(e)}")


@router.post("/v1/token-pool/health-check")
async def trigger_health_check():
    """手动触发token池健康检查"""
    try:
        token_pool = get_token_pool()
        if not token_pool:
            raise HTTPException(status_code=404, detail="Token池未初始化")

        start_time = time.time()
        logger.info("🔍 API触发Token池健康检查...")
        await token_pool.health_check_all()
        duration = time.time() - start_time

        pool_status = token_pool.get_pool_status()
        total_tokens = pool_status['total_tokens']
        healthy_tokens = sum(1 for token_info in pool_status['tokens'] if token_info['is_healthy'])

        response = {
            "status": "completed",
            "message": f"健康检查已完成，耗时 {duration:.2f} 秒",
            "summary": {
                "total_tokens": total_tokens,
                "healthy_tokens": healthy_tokens,
                "unhealthy_tokens": total_tokens - healthy_tokens,
                "health_rate": f"{(healthy_tokens/total_tokens*100):.1f}%" if total_tokens > 0 else "0%",
                "duration_seconds": round(duration, 2)
            },
            "pool_info": pool_status
        }

        logger.info(f"✅ API健康检查完成: {healthy_tokens}/{total_tokens} 个token健康")
        return response
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.post("/v1/token-pool/update")
async def update_token_pool_endpoint(tokens: List[str]):
    """动态更新token池"""
    try:
        from app.utils.token_pool import update_token_pool

        valid_tokens = [token.strip() for token in tokens if token.strip()]
        if not valid_tokens:
            raise HTTPException(status_code=400, detail="至少需要提供一个有效的token")

        update_token_pool(valid_tokens)
        token_pool = get_token_pool()

        return {
            "status": "updated",
            "message": f"Token池已更新，共 {len(valid_tokens)} 个token",
            "pool_info": token_pool.get_pool_status() if token_pool else None
        }
    except Exception as e:
        logger.error(f"更新token池失败: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update token pool: {str(e)}")
