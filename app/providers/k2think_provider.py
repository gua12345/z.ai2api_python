#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
K2Think 提供商适配器
"""

import json
import re
import time
import uuid
import httpx
from typing import Dict, List, Any, Optional, AsyncGenerator, Union

from app.providers.base import BaseProvider, ProviderConfig
from app.models.schemas import OpenAIRequest, Message
from app.utils.logger import get_logger

logger = get_logger()


class K2ThinkProvider(BaseProvider):
    """K2Think 提供商"""
    
    def __init__(self):
        config = ProviderConfig(
            name="k2think",
            api_endpoint="https://www.k2think.ai/api/guest/chat/completions",
            timeout=30,
            headers={
                'Accept': 'text/event-stream',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
                'Content-Type': 'application/json',
                'Origin': 'https://www.k2think.ai',
                'Pragma': 'no-cache',
                'Referer': 'https://www.k2think.ai/guest',
                'Sec-Ch-Ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"macOS"',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            }
        )
        super().__init__(config)

        # K2Think 特定配置
        self.handshake_url = "https://www.k2think.ai/guest"
        self.new_chat_url = "https://www.k2think.ai/api/v1/chats/guest/new"
        
        # 内容解析正则表达式 - 使用DOTALL标志确保.匹配换行符
        self.reasoning_pattern = re.compile(r'<details type="reasoning"[^>]*>.*?<summary>.*?</summary>(.*?)</details>', re.DOTALL)
        self.answer_pattern = re.compile(r'<answer>(.*?)</answer>', re.DOTALL)
    
    def get_supported_models(self) -> List[str]:
        """获取支持的模型列表"""
        return ["MBZUAI-IFM/K2-Think"]
    
    def parse_cookies(self, headers) -> str:
        """解析Cookie"""
        cookies = []
        for key, value in headers.items():
            if key.lower() == 'set-cookie':
                cookies.append(value.split(';')[0])
        return '; '.join(cookies)
    
    def extract_reasoning_and_answer(self, content: str) -> tuple[str, str]:
        """提取推理内容和答案内容"""
        if not content:
            return "", ""
        
        try:
            reasoning_match = self.reasoning_pattern.search(content)
            reasoning = reasoning_match.group(1).strip() if reasoning_match else ""
            
            answer_match = self.answer_pattern.search(content)
            answer = answer_match.group(1).strip() if answer_match else ""
            
            return reasoning, answer
        except Exception as e:
            self.logger.error(f"提取K2内容错误: {e}")
            return "", ""
    
    def calculate_delta(self, previous: str, current: str) -> str:
        """计算内容增量"""
        if not previous:
            return current
        if not current or len(current) < len(previous):
            return ""
        return current[len(previous):]
    
    def parse_api_response(self, obj: Any) -> tuple[str, bool]:
        """解析API响应"""
        if not obj or not isinstance(obj, dict):
            return "", False
        
        if obj.get("done") is True:
            return "", True
        
        choices = obj.get("choices", [])
        if choices and len(choices) > 0:
            delta = choices[0].get("delta", {})
            return delta.get("content", ""), False
        
        content = obj.get("content")
        if isinstance(content, str):
            return content, False
        
        return "", False
    
    async def get_k2_auth_data(self, request: OpenAIRequest) -> Dict[str, Any]:
        """获取K2Think认证数据"""
        # 1. 握手请求 - 使用更简单的Accept-Encoding来避免Brotli问题
        headers_for_handshake = {**self.config.headers}
        headers_for_handshake['Accept-Encoding'] = 'gzip, deflate'  # 移除br和zstd

        async with httpx.AsyncClient() as client:
            handshake_response = await client.get(
                self.handshake_url,
                headers=headers_for_handshake,
                follow_redirects=True
            )
            if not handshake_response.is_success:
                try:
                    # 使用httpx的text属性，它会自动处理解压缩和编码
                    error_text = handshake_response.text
                    raise Exception(f"K2 握手失败: {handshake_response.status_code} {error_text[:200]}")
                except Exception as e:
                    raise Exception(f"K2 握手失败: {handshake_response.status_code}")
            
            initial_cookies = self.parse_cookies(handshake_response.headers)
        
        # 2. 准备消息
        prepared_messages = self.prepare_k2_messages(request.messages)
        first_user_message = next((m for m in prepared_messages if m["role"] == "user"), None)
        if not first_user_message:
            raise Exception("没有找到用户消息来初始化对话")
        
        # 3. 创建新对话
        message_id = str(uuid.uuid4())
        now = int(time.time() * 1000)
        model_id = request.model or "MBZUAI-IFM/K2-Think"
        
        new_chat_payload = {
            "chat": {
                "id": "",
                "title": "Guest Chat",
                "models": [model_id],
                "params": {},
                "history": {
                    "messages": {
                        message_id: {
                            "id": message_id,
                            "parentId": None,
                            "childrenIds": [],
                            "role": "user",
                            "content": first_user_message["content"],
                            "timestamp": now // 1000,
                            "models": [model_id]
                        }
                    },
                    "currentId": message_id
                },
                "messages": [{
                    "id": message_id,
                    "parentId": None,
                    "childrenIds": [],
                    "role": "user",
                    "content": first_user_message["content"],
                    "timestamp": now // 1000,
                    "models": [model_id]
                }],
                "tags": [],
                "timestamp": now
            }
        }
        
        headers_with_cookies = {**self.config.headers, 'Cookie': initial_cookies}
        headers_with_cookies['Accept-Encoding'] = 'gzip, deflate'  # 移除br和zstd

        async with httpx.AsyncClient() as client:
            new_chat_response = await client.post(
                self.new_chat_url,
                headers=headers_with_cookies,
                json=new_chat_payload,
                follow_redirects=True
            )
            if not new_chat_response.is_success:
                try:
                    # 使用httpx的text属性，它会自动处理解压缩和编码
                    error_text = new_chat_response.text
                except Exception:
                    error_text = f"Status: {new_chat_response.status_code}"
                raise Exception(f"K2 新对话创建失败: {new_chat_response.status_code} {error_text[:200]}")

            try:
                new_chat_data = new_chat_response.json()
            except Exception as e:
                # 如果JSON解析失败，尝试获取原始内容
                try:
                    # 使用httpx的text属性，它会自动处理解压缩和编码
                    content_str = new_chat_response.text
                    self.logger.debug(f"K2 响应原始内容: {content_str[:500]}")
                    raise Exception(f"K2 响应JSON解析失败: {e}, 原始内容: {content_str[:200]}")
                except Exception as decode_error:
                    # 如果text也失败，尝试手动处理
                    try:
                        raw_bytes = new_chat_response.content
                        content_str = raw_bytes.decode('utf-8', errors='replace')
                        raise Exception(f"K2 响应解析失败: {e}, 手动解码内容: {content_str[:200]}")
                    except Exception:
                        raise Exception(f"K2 响应解析完全失败: {e}, 解码错误: {decode_error}")
            conversation_id = new_chat_data.get("id")
            if not conversation_id:
                raise Exception("无法从K2 /new端点获取conversation_id")
            
            chat_specific_cookies = self.parse_cookies(new_chat_response.headers)
        
        # 4. 组合最终Cookie
        base_cookies = [initial_cookies, chat_specific_cookies]
        base_cookies = [c for c in base_cookies if c]
        final_cookie = '; '.join(base_cookies) + '; guest_conversation_count=1'
        
        # 5. 构建最终请求载荷
        final_payload = {
            "stream": True,
            "model": model_id,
            "messages": prepared_messages,
            "conversation_id": conversation_id,
            "params": {}
        }
        
        # 添加可选参数
        if request.temperature is not None:
            final_payload["params"]["temperature"] = request.temperature
        if request.max_tokens is not None:
            final_payload["params"]["max_tokens"] = request.max_tokens
        
        final_headers = {**self.config.headers, 'Cookie': final_cookie}
        
        return {
            "payload": final_payload,
            "headers": final_headers
        }
    
    def prepare_k2_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """准备K2Think消息格式"""
        result = []
        system_content = ""
        
        for msg in messages:
            if msg.role == "system":
                system_content = system_content + "\n\n" + msg.content if system_content else msg.content
            else:
                content = msg.content
                if isinstance(content, list):
                    # 处理多模态内容，提取文本
                    text_parts = [part.text for part in content if hasattr(part, 'text') and part.text]
                    content = "\n".join(text_parts)
                
                result.append({
                    "role": msg.role,
                    "content": content
                })
        
        # 将系统消息合并到第一个用户消息中
        if system_content:
            first_user_idx = next((i for i, m in enumerate(result) if m["role"] == "user"), -1)
            if first_user_idx >= 0:
                result[first_user_idx]["content"] = f"{system_content}\n\n{result[first_user_idx]['content']}"
            else:
                result.insert(0, {"role": "user", "content": system_content})
        
        return result

    async def _handle_stream_request(
        self,
        transformed: Dict[str, Any],
        request: OpenAIRequest
    ) -> AsyncGenerator[str, None]:
        """处理流式请求 - 在client.stream上下文内直接处理"""
        chat_id = self.create_chat_id()
        model = transformed["model"]

        # 准备请求头
        headers_for_request = {**transformed["headers"]}
        headers_for_request['Accept-Encoding'] = 'gzip, deflate'

        self.logger.info(f"🌊 开始K2Think流式请求")

        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST",
                transformed["url"],
                headers=headers_for_request,
                json=transformed["payload"]
            ) as response:
                if not response.is_success:
                    error_msg = f"K2Think API 错误: {response.status_code}"
                    self.log_response(False, error_msg)
                    # 对于流式响应，我们需要yield错误信息
                    yield await self.format_sse_chunk({
                        "error": {
                            "message": error_msg,
                            "type": "provider_error",
                            "code": "api_error"
                        }
                    })
                    return

                # 发送初始角色块
                yield await self.format_sse_chunk(
                    self.create_openai_chunk(chat_id, model, {"role": "assistant"})
                )

                # 处理流式数据
                accumulated_content = ""
                previous_reasoning = ""
                previous_answer = ""
                reasoning_phase = True
                chunk_count = 0

                try:
                    async for line in response.aiter_lines():
                        chunk_count += 1
                        self.logger.debug(f"📦 收到数据块 #{chunk_count}: {line[:100]}...")

                        if not line.startswith("data:"):
                            continue

                        data_str = line[5:].strip()
                        if self._is_end_marker(data_str):
                            self.logger.debug(f"🏁 检测到结束标记: {data_str}")
                            continue

                        content = self._parse_data_string(data_str)
                        if not content:
                            continue

                        accumulated_content = content
                        current_reasoning, current_answer = self.extract_reasoning_and_answer(accumulated_content)

                        # 处理推理阶段
                        if reasoning_phase and current_reasoning:
                            delta = self.calculate_delta(previous_reasoning, current_reasoning)
                            if delta.strip():
                                self.logger.debug(f"🧠 推理增量: {delta[:50]}...")
                                yield await self.format_sse_chunk(
                                    self.create_openai_chunk(chat_id, model, {"reasoning_content": delta})
                                )
                                previous_reasoning = current_reasoning

                        # 切换到答案阶段
                        if current_answer and reasoning_phase:
                            reasoning_phase = False
                            self.logger.debug("🔄 切换到答案阶段")
                            # 发送剩余的推理内容
                            final_reasoning_delta = self.calculate_delta(previous_reasoning, current_reasoning)
                            if final_reasoning_delta.strip():
                                yield await self.format_sse_chunk(
                                    self.create_openai_chunk(chat_id, model, {"reasoning_content": final_reasoning_delta})
                                )

                        # 处理答案阶段
                        if not reasoning_phase and current_answer:
                            delta = self.calculate_delta(previous_answer, current_answer)
                            if delta.strip():
                                self.logger.debug(f"💬 答案增量: {delta[:50]}...")
                                yield await self.format_sse_chunk(
                                    self.create_openai_chunk(chat_id, model, {"content": delta})
                                )
                                previous_answer = current_answer

                except Exception as e:
                    self.logger.error(f"流式响应处理错误: {e}")
                    yield await self.format_sse_chunk({
                        "error": {
                            "message": f"流式处理错误: {str(e)}",
                            "type": "stream_error",
                            "code": "processing_error"
                        }
                    })
                    return

                # 发送结束块
                self.logger.info(f"✅ K2Think流式响应完成，共处理 {chunk_count} 个数据块")
                yield await self.format_sse_chunk(
                    self.create_openai_chunk(chat_id, model, {}, "stop")
                )
                yield await self.format_sse_done()

    async def transform_request(self, request: OpenAIRequest) -> Dict[str, Any]:
        """转换OpenAI请求为K2Think格式"""
        self.logger.info(f"🔄 转换 OpenAI 请求到 K2Think 格式: {request.model}")
        
        auth_data = await self.get_k2_auth_data(request)
        
        return {
            "url": self.config.api_endpoint,
            "headers": auth_data["headers"],
            "payload": auth_data["payload"],
            "model": request.model
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
            transformed = await self.transform_request(request)

            # 发送请求 - 使用更兼容的压缩设置
            headers_for_request = {**transformed["headers"]}
            headers_for_request['Accept-Encoding'] = 'gzip, deflate'  # 移除br和zstd

            if request.stream:
                # 流式请求 - 直接在这里处理流式响应
                return self._handle_stream_request(transformed, request)
            else:
                # 非流式请求 - 使用传统的 client.post()
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        transformed["url"],
                        headers=headers_for_request,
                        json=transformed["payload"]
                    )

                    if not response.is_success:
                        error_msg = f"K2Think API 错误: {response.status_code}"
                        self.log_response(False, error_msg)
                        return self.handle_error(Exception(error_msg))

                    # 转换非流式响应
                    return await self.transform_response(response, request, transformed)

        except Exception as e:
            self.log_response(False, str(e))
            return self.handle_error(e, "请求处理")
    
    async def transform_response(
        self,
        response: httpx.Response,
        request: OpenAIRequest,
        transformed: Dict[str, Any]
    ) -> Dict[str, Any]:
        """转换K2Think响应为OpenAI格式 - 仅用于非流式请求"""
        chat_id = self.create_chat_id()
        model = transformed["model"]

        # 流式请求现在由 _handle_stream_request 直接处理
        # 这里只处理非流式请求
        return await self._handle_non_stream_response(response, chat_id, model)

    def _is_end_marker(self, data: str) -> bool:
        """检查是否为结束标记"""
        return not data or data in ["-1", "[DONE]", "DONE", "done"]
    
    def _parse_data_string(self, data_str: str) -> str:
        """解析数据字符串"""
        try:
            obj = json.loads(data_str)
            content, is_done = self.parse_api_response(obj)
            return "" if is_done else content
        except:
            return data_str
    
    async def _handle_non_stream_response(
        self,
        response: httpx.Response,
        chat_id: str,
        model: str
    ) -> Dict[str, Any]:
        """处理K2Think非流式响应"""
        # 聚合流式内容 - 使用httpx的aiter_lines，它会自动处理解压缩
        final_content = ""

        try:
            # 使用aiter_lines()，httpx会自动处理压缩和编码
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue

                data_str = line[5:].strip()
                if self._is_end_marker(data_str):
                    continue

                content = self._parse_data_string(data_str)
                if content:
                    final_content = content

        except Exception as e:
            self.logger.error(f"非流式响应处理错误: {e}")
            raise

        # 提取推理内容和答案内容
        reasoning, answer = self.extract_reasoning_and_answer(final_content)

        # 清理内容格式
        reasoning = reasoning.replace("\\n", "\n") if reasoning else ""
        answer = answer.replace("\\n", "\n") if answer else final_content

        # 创建包含推理内容的响应
        return self.create_openai_response_with_reasoning(chat_id, model, answer, reasoning)
