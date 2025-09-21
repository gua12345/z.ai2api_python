#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LongCat 提供商适配器
"""

import json
import time
import httpx
import random
import asyncio
from typing import Dict, List, Any, Optional, AsyncGenerator, Union

from app.providers.base import BaseProvider, ProviderConfig
from app.models.schemas import OpenAIRequest, Message
from app.utils.logger import get_logger
from app.utils.user_agent import get_dynamic_headers
from app.core.config import settings

logger = get_logger()


class LongCatProvider(BaseProvider):
    """LongCat 提供商"""

    def __init__(self):
        # 使用动态生成的 headers，不包含 User-Agent（将在请求时动态生成）
        config = ProviderConfig(
            name="longcat",
            api_endpoint="https://longcat.chat/api/v1/chat-completion",
            timeout=30,
            headers={
                'accept': 'text/event-stream,application/json',
                'content-type': 'application/json',
                'origin': 'https://longcat.chat',
                'referer': 'https://longcat.chat/t',
            }
        )
        super().__init__(config)
        self.base_url = "https://longcat.chat"
        self.session_create_url = f"{self.base_url}/api/v1/session-create"
        self.session_delete_url = f"{self.base_url}/api/v1/session-delete"
    
    def get_supported_models(self) -> List[str]:
        """获取支持的模型列表"""
        return ["LongCat-Flash", "LongCat", "LongCat-Search"]

    def get_passport_token(self) -> Optional[str]:
        """获取 LongCat passport token"""
        # 优先使用环境变量中的单个token
        if settings.LONGCAT_PASSPORT_TOKEN:
            return settings.LONGCAT_PASSPORT_TOKEN

        # 从token文件中随机选择一个
        token_list = settings.longcat_token_list
        if token_list:
            return random.choice(token_list)

        return None

    def create_headers_with_auth(self, token: str, user_agent: str, referer: str = None) -> Dict[str, str]:
        """创建带认证的请求头"""
        headers = {
            "User-Agent": user_agent,
            "Content-Type": "application/json",
            "x-requested-with": "XMLHttpRequest",
            "X-Client-Language": "zh",
            "Cookie": f"passport_token_key={token}",
            "Accept": "text/event-stream,application/json",
            "Origin": "https://longcat.chat"
        }
        if referer:
            headers["Referer"] = referer
        else:
            headers["Referer"] = f"{self.base_url}/"
        return headers

    async def create_session(self, token: str, user_agent: str) -> str:
        """创建会话并返回 conversation_id"""
        headers = self.create_headers_with_auth(token, user_agent)
        data = {"model": "", "agentId": ""}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.session_create_url,
                headers=headers,
                json=data
            )

            if response.status_code != 200:
                raise Exception(f"会话创建失败: {response.status_code}")

            response_data = response.json()
            if response_data.get("code") != 0:
                raise Exception(f"会话创建错误: {response_data.get('message')}")

            return response_data["data"]["conversationId"]

    async def delete_session(self, conversation_id: str, token: str, user_agent: str) -> None:
        """删除会话"""
        try:
            headers = self.create_headers_with_auth(
                token,
                user_agent,
                f"{self.base_url}/c/{conversation_id}"
            )

            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{self.session_delete_url}?conversationId={conversation_id}"
                response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    self.logger.debug(f"成功删除会话 {conversation_id}")
                else:
                    self.logger.warning(f"删除会话失败: {response.status_code}")
        except Exception as e:
            self.logger.error(f"删除会话出错: {e}")

    def schedule_session_deletion(self, conversation_id: str, token: str, user_agent: str):
        """异步删除会话（不等待）"""
        asyncio.create_task(self.delete_session(conversation_id, token, user_agent))

    def format_messages_for_longcat(self, messages: List[Message]) -> str:
        """格式化消息为 LongCat 格式"""
        formatted_messages = []
        for msg in messages:
            content = msg.content
            if isinstance(content, list):
                # 处理多模态内容，提取文本
                text_parts = []
                for part in content:
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
                content = "\n".join(text_parts)
            formatted_messages.append(f"{msg.role}:{content}")
        return ";".join(formatted_messages)
    
    async def transform_request(self, request: OpenAIRequest, api_key: Optional[str] = None) -> Dict[str, Any]:
        """转换OpenAI请求为LongCat格式"""
        # 获取认证token
        passport_token = api_key if api_key else self.get_passport_token()
        if not passport_token:
            raise Exception("未配置 LongCat passport token，请设置 LONGCAT_PASSPORT_TOKEN 环境变量或 LONGCAT_TOKENS_FILE")

        # 生成动态 User-Agent
        dynamic_headers = get_dynamic_headers()
        user_agent = dynamic_headers.get("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        # 创建会话
        conversation_id = await self.create_session(passport_token, user_agent)

        # 格式化消息内容
        formatted_content = self.format_messages_for_longcat(request.messages)

        # 构建LongCat请求载荷
        payload = {
            "conversationId": conversation_id,
            "content": formatted_content,
            "reasonEnabled": 0,
            "searchEnabled": 1 if "search" in request.model.lower() else 0,
            "parentMessageId": 0
        }

        # 创建带认证的请求头
        headers = self.create_headers_with_auth(
            passport_token,
            user_agent,
            f"{self.base_url}/c/{conversation_id}"
        )

        return {
            "url": self.config.api_endpoint,
            "headers": headers,
            "payload": payload,
            "model": request.model,
            "conversation_id": conversation_id,
            "passport_token": passport_token,
            "user_agent": user_agent
        }
    
    async def chat_completion(
        self,
        request: OpenAIRequest,
        api_key: Optional[str] = None,
        **kwargs
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """聊天完成接口"""
        self.log_request(request)

        try:
            # 转换请求
            transformed = await self.transform_request(request, api_key=api_key)

            # 发送请求
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    transformed["url"],
                    headers=transformed["headers"],
                    json=transformed["payload"]
                )

                if not response.is_success:
                    error_msg = f"LongCat API 错误: {response.status_code}"
                    try:
                        error_detail = await response.atext()
                        self.logger.error(f"❌ API 错误详情: {error_detail}")
                    except:
                        pass
                    self.log_response(False, error_msg)
                    return self.handle_error(Exception(error_msg))

                # 转换响应
                return await self.transform_response(response, request, transformed)

        except Exception as e:
            self.logger.error(f"❌ LongCat 请求处理异常: {e}")
            self.log_response(False, str(e))
            return self.handle_error(e, "请求处理")
    
    async def transform_response(
        self,
        response: httpx.Response,
        request: OpenAIRequest,
        transformed: Dict[str, Any]
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """转换LongCat响应为OpenAI格式"""
        chat_id = self.create_chat_id()
        model = transformed["model"]
        conversation_id = transformed["conversation_id"]
        passport_token = transformed["passport_token"]
        user_agent = transformed["user_agent"]

        if request.stream:
            return self._handle_stream_response(
                response, chat_id, model, conversation_id, passport_token, user_agent
            )
        else:
            return await self._handle_non_stream_response(
                response, chat_id, model, conversation_id, passport_token, user_agent
            )
    
    async def _handle_stream_response(
        self,
        response: httpx.Response,
        chat_id: str,
        model: str,
        conversation_id: str,
        passport_token: str,
        user_agent: str
    ) -> AsyncGenerator[str, None]:
        """处理LongCat流式响应"""
        session_deleted = False

        try:
            # 发送初始角色块
            yield await self.format_sse_chunk(
                self.create_openai_chunk(chat_id, model, {"role": "assistant"})
            )

            stream_finished = False

            async for line in response.aiter_lines():
                line = line.strip()

                # 首先检查是否是错误响应（JSON格式但不是SSE格式）
                if not line.startswith('data:'):
                    # 尝试解析为JSON错误响应
                    try:
                        error_data = json.loads(line)
                        if isinstance(error_data, dict) and 'code' in error_data and 'message' in error_data:
                            # 这是一个错误响应
                            self.logger.error(f"❌ LongCat API 返回错误: {error_data}")
                            error_message = error_data.get('message', '未知错误')
                            error_code = error_data.get('code', 'unknown')

                            # 使用统一的错误处理函数
                            error_exception = Exception(f"LongCat API 错误 ({error_code}): {error_message}")
                            error_response = self.handle_error(error_exception, "API响应")

                            # 发送错误响应块
                            yield await self.format_sse_chunk(error_response)
                            yield await self.format_sse_done()

                            # 清理会话
                            if not session_deleted:
                                self.schedule_session_deletion(conversation_id, passport_token, user_agent)
                                session_deleted = True
                            return
                    except json.JSONDecodeError:
                        # 不是JSON，跳过这行
                        continue

                    # 如果不是错误响应，跳过
                    continue

                data_str = line[5:].strip()
                if data_str == '[DONE]':
                    # 如果还没有发送完成块，发送一个
                    if not stream_finished:
                        yield await self.format_sse_chunk(
                            self.create_openai_chunk(chat_id, model, {}, "stop")
                        )
                    yield await self.format_sse_done()

                    # 清理会话
                    if not session_deleted:
                        self.schedule_session_deletion(conversation_id, passport_token, user_agent)
                        session_deleted = True
                    break

                try:
                    longcat_data = json.loads(data_str)

                    # 获取 delta 内容
                    choices = longcat_data.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    finish_reason = choices[0].get("finishReason")

                    # 只有当内容不为空时才发送内容块
                    if content is not None and content != "":
                        openai_chunk = self.create_openai_chunk(
                            chat_id,
                            model,
                            {"content": content}
                        )
                        yield await self.format_sse_chunk(openai_chunk)

                    # 检查是否为流的结束
                    # LongCat 使用 lastOne=true 来标识最后一个块
                    if longcat_data.get("lastOne") and not stream_finished:
                        yield await self.format_sse_chunk(
                            self.create_openai_chunk(chat_id, model, {}, "stop")
                        )
                        yield await self.format_sse_done()
                        stream_finished = True

                        # 清理会话
                        if not session_deleted:
                            self.schedule_session_deletion(conversation_id, passport_token, user_agent)
                            session_deleted = True
                        break

                    # 备用检查：如果有 finishReason 但没有 lastOne，也可能是结束
                    elif finish_reason == "stop" and longcat_data.get("contentStatus") == "FINISHED" and not stream_finished:
                        yield await self.format_sse_chunk(
                            self.create_openai_chunk(chat_id, model, {}, "stop")
                        )
                        yield await self.format_sse_done()
                        stream_finished = True

                        # 清理会话
                        if not session_deleted:
                            self.schedule_session_deletion(conversation_id, passport_token, user_agent)
                            session_deleted = True
                        break

                except json.JSONDecodeError as e:
                    self.logger.error(f"❌ 解析LongCat流数据错误: {e}")
                    continue
                except Exception as e:
                    self.logger.error(f"❌ 处理LongCat流数据错误: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"❌ LongCat流处理错误: {e}")
            # 发送错误结束块（只有在还没有结束的情况下）
            if not stream_finished:
                yield await self.format_sse_chunk(
                    self.create_openai_chunk(chat_id, model, {}, "stop")
                )
                yield await self.format_sse_done()
        finally:
            # 确保会话被清理
            if not session_deleted:
                self.schedule_session_deletion(conversation_id, passport_token, user_agent)
    
    async def _handle_non_stream_response(
        self,
        response: httpx.Response,
        chat_id: str,
        model: str,
        conversation_id: str,
        passport_token: str,
        user_agent: str
    ) -> Dict[str, Any]:
        """处理LongCat非流式响应"""
        full_content = ""
        usage_info = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }

        try:
            async for line in response.aiter_lines():
                line = line.strip()
                if not line.startswith('data:'):
                    # 检查是否是错误响应
                    try:
                        error_data = json.loads(line)
                        if isinstance(error_data, dict) and 'code' in error_data and 'message' in error_data:
                            # 这是一个错误响应
                            self.logger.error(f"❌ LongCat API 返回错误: {error_data}")
                            error_message = error_data.get('message', '未知错误')
                            error_code = error_data.get('code', 'unknown')

                            # 使用统一的错误处理函数
                            error_exception = Exception(f"LongCat API 错误 ({error_code}): {error_message}")

                            # 清理会话
                            self.schedule_session_deletion(conversation_id, passport_token, user_agent)

                            return self.handle_error(error_exception, "API响应")
                    except json.JSONDecodeError:
                        # 不是JSON，跳过这行
                        pass
                    continue

                data_str = line[5:].strip()
                if data_str == '[DONE]':
                    break

                try:
                    chunk = json.loads(data_str)

                    # 提取内容 - 只有当内容不为空时才添加
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content")
                        if content is not None and content != "":
                            full_content += content

                    # 提取使用信息（通常在最后的块中）
                    if chunk.get("tokenInfo"):
                        token_info = chunk["tokenInfo"]
                        usage_info = {
                            "prompt_tokens": token_info.get("promptTokens", 0),
                            "completion_tokens": token_info.get("completionTokens", 0),
                            "total_tokens": token_info.get("totalTokens", 0)
                        }

                    # 如果是最后一个块，可以提前结束
                    if chunk.get("lastOne"):
                        break

                except json.JSONDecodeError:
                    continue

        except Exception as e:
            self.logger.error(f"❌ 处理LongCat非流式响应错误: {e}")
            full_content = "处理响应时发生错误"
        finally:
            # 清理会话
            self.schedule_session_deletion(conversation_id, passport_token, user_agent)

        return self.create_openai_response(
            chat_id,
            model,
            full_content.strip(),
            usage_info
        )
