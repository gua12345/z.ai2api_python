/**
 * Cloudflare Worker for OpenAI Compatible API Server
 * Converted from Python FastAPI application
 */

// Configuration
const CONFIG = {
  // API Configuration
  API_ENDPOINT: "https://chat.z.ai/api/chat/completions",
  AUTH_TOKEN: "sk-your-api-key",
  BACKUP_TOKEN: "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjMxNmJjYjQ4LWZmMmYtNGExNS04NTNkLWYyYTI5YjY3ZmYwZiIsImVtYWlsIjoiR3Vlc3QtMTc1NTg0ODU4ODc4OEBndWVzdC5jb20ifQ.PktllDySS3trlyuFpTeIZf-7hl8Qu1qYF3BxjgIul0BrNux2nX9hVzIjthLXKMWAf9V0qM8Vm_iyDqkjPGsaiQ",
  
  // Model Configuration
  PRIMARY_MODEL: "ZAI2API/GLM-4.5",
  THINKING_MODEL: "ZAI2API/GLM-4.5-Thinking",
  SEARCH_MODEL: "ZAI2API/GLM-4.5-Search",
  AIR_MODEL: "ZAI2API/GLM-4.5-Air",
  
  // Server Configuration
  LISTEN_PORT: 8080,
  DEBUG_LOGGING: true,
  
  // Feature Configuration
  THINKING_PROCESSING: "think",  // strip: 去除<details>标签；think: 转为<span>标签；raw: 保留原样
  ANONYMOUS_MODE: true,
  TOOL_SUPPORT: true,
  SCAN_LIMIT: 200000,
  SKIP_AUTH_TOKEN: true,
  
  // Browser Headers
  CLIENT_HEADERS: {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
    "Accept-Language": "zh-CN",
    "sec-ch-ua": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "X-FE-Version": "prod-fe-1.0.70",
    "Origin": "https://chat.z.ai",
  }
};

// Utility functions
function debugLog(message, ...args) {
  if (CONFIG.DEBUG_LOGGING) {
    if (args.length > 0) {
      console.log(`[DEBUG] ${message}`, ...args);
    } else {
      console.log(`[DEBUG] ${message}`);
    }
  }
}

function generateRequestIds() {
  const timestamp = Math.floor(Date.now() / 1000);
  const chatId = `${timestamp * 1000}-${timestamp}`;
  const msgId = String(timestamp * 1000000);
  return { chatId, msgId };
}

function contentToString(content) {
  if (typeof content === 'string') {
    return content;
  }
  if (Array.isArray(content)) {
    const parts = [];
    for (const p of content) {
      if (typeof p === 'object' && p.type === 'text') {
        parts.push(p.text || '');
      } else if (typeof p === 'string') {
        parts.push(p);
      }
    }
    return parts.join(' ');
  }
  return '';
}

// Main worker handler
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // Handle CORS preflight requests
    if (request.method === 'OPTIONS') {
      return handleOptions();
    }
    
    // Route handling
    if (url.pathname === '/') {
      return handleRoot();
    }
    
    if (url.pathname === '/v1/models') {
      return handleListModels();
    }
    
    if (url.pathname === '/v1/chat/completions') {
      return handleChatCompletions(request);
    }
    
    // Default 404 response
    return new Response('Not Found', { status: 404 });
  }
};

// Handle OPTIONS requests for CORS
function handleOptions() {
  return new Response(null, {
    status: 200,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    }
  });
}

// Handle root endpoint
function handleRoot() {
  return new Response(JSON.stringify({
    message: "OpenAI Compatible API Server"
  }), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    }
  });
}

// Handle list models endpoint
function handleListModels() {
  const currentTime = Math.floor(Date.now() / 1000);
  
  const response = {
    object: "list",
    data: [
      {
        id: CONFIG.PRIMARY_MODEL,
        object: "model",
        created: currentTime,
        owned_by: "z.ai"
      },
      {
        id: CONFIG.THINKING_MODEL,
        object: "model",
        created: currentTime,
        owned_by: "z.ai"
      },
      {
        id: CONFIG.SEARCH_MODEL,
        object: "model",
        created: currentTime,
        owned_by: "z.ai"
      },
      {
        id: CONFIG.AIR_MODEL,
        object: "model",
        created: currentTime,
        owned_by: "z.ai"
      }
    ]
  };
  
  return new Response(JSON.stringify(response), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    }
  });
}

// Handle chat completions endpoint
async function handleChatCompletions(request) {
  debugLog("收到chat completions请求");
  
  try {
    // Validate API key (skip if SKIP_AUTH_TOKEN is enabled)
    if (!CONFIG.SKIP_AUTH_TOKEN) {
      const authorization = request.headers.get('Authorization');
      if (!authorization || !authorization.startsWith('Bearer ')) {
        debugLog("缺少或无效的Authorization头");
        return new Response(JSON.stringify({ error: "Missing or invalid Authorization header" }), {
          status: 401,
          headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
          }
        });
      }
      
      const apiKey = authorization.substring(7);
      if (apiKey !== CONFIG.AUTH_TOKEN) {
        debugLog(`无效的API key: ${apiKey}`);
        return new Response(JSON.stringify({ error: "Invalid API key" }), {
          status: 401,
          headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
          }
        });
      }
      
      debugLog(`API key验证通过，AUTH_TOKEN=${apiKey.substring(0, 8)}......`);
    } else {
      debugLog("SKIP_AUTH_TOKEN已启用，跳过API key验证");
    }
    
    // Parse request body
    const requestBody = await request.json();
    debugLog(`请求解析成功 - 模型: ${requestBody.model}, 流式: ${requestBody.stream}, 消息数: ${requestBody.messages.length}`);
    
    // Generate IDs
    const { chatId, msgId } = generateRequestIds();
    
    // Process messages with tools
    const processedMessages = processMessagesWithTools(
      requestBody.messages,
      requestBody.tools,
      requestBody.tool_choice
    );
    
    // Determine model features
    const isThinking = requestBody.model === CONFIG.THINKING_MODEL;
    const isSearch = requestBody.model === CONFIG.SEARCH_MODEL;
    const isAir = requestBody.model === CONFIG.AIR_MODEL;
    const searchMcp = isSearch ? "deep-web-search" : "";
    
    // Determine upstream model ID based on requested model
    let upstreamModelId, upstreamModelName;
    if (isAir) {
      upstreamModelId = "0727-106B-API";  // AIR model upstream ID
      upstreamModelName = "GLM-4.5-Air";
    } else {
      upstreamModelId = "0727-360B-API";  // Default upstream model ID
      upstreamModelName = "GLM-4.5";
    }
    
    // Build upstream request
    const upstreamReq = {
      stream: true,  // Always use streaming from upstream
      chat_id: chatId,
      id: msgId,
      model: upstreamModelId,
      messages: processedMessages,
      params: {},
      features: {
        enable_thinking: isThinking,
        web_search: isSearch,
        auto_web_search: isSearch,
      },
      background_tasks: {
        title_generation: false,
        tags_generation: false,
      },
      mcp_servers: searchMcp ? [searchMcp] : [],
      model_item: {
        id: upstreamModelId,
        name: upstreamModelName,
        owned_by: "openai"
      },
      tool_servers: [],
      variables: {
        "{{USER_NAME}}": "User",
        "{{USER_LOCATION}}": "Unknown",
        "{{CURRENT_DATETIME}}": new Date().toISOString().replace('T', ' ').substring(0, 19),
      }
    };
    
    // Get authentication token
    const authToken = await getAuthToken();
    
    // Check if tools are enabled and present
    const hasTools = (CONFIG.TOOL_SUPPORT && 
                     requestBody.tools && 
                     requestBody.tools.length > 0 && 
                     requestBody.tool_choice !== "none");
    
    // Handle response based on stream flag
    if (requestBody.stream) {
      return handleStreamResponse(upstreamReq, chatId, authToken, hasTools);
    } else {
      return handleNonStreamResponse(upstreamReq, chatId, authToken, hasTools);
    }
    
  } catch (error) {
    debugLog(`处理请求时发生错误: ${error.message}`);
    debugLog(`错误堆栈: ${error.stack}`);
    return new Response(JSON.stringify({ error: `Internal server error: ${error.message}` }), {
      status: 500,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      }
    });
  }
}

// Process messages with tools
function processMessagesWithTools(messages, tools, toolChoice) {
  let processed = [];
  
  if (tools && CONFIG.TOOL_SUPPORT && toolChoice !== "none") {
    const toolsPrompt = generateToolPrompt(tools);
    const hasSystem = messages.some(m => m.role === "system");
    
    if (hasSystem) {
      for (const m of messages) {
        if (m.role === "system") {
          const mm = { ...m };
          const content = contentToString(mm.content || "");
          mm.content = content + toolsPrompt;
          processed.push(mm);
        } else {
          processed.push(m);
        }
      }
    } else {
      processed = [{ role: "system", content: "你是一个有用的助手。" + toolsPrompt }, ...messages];
    }
    
    // Add tool choice hints
    if (toolChoice === "required" || toolChoice === "auto") {
      if (processed.length > 0 && processed[processed.length - 1].role === "user") {
        const last = { ...processed[processed.length - 1] };
        const content = contentToString(last.content || "");
        last.content = content + "\n\n请根据需要使用提供的工具函数。";
        processed[processed.length - 1] = last;
      }
    } else if (typeof toolChoice === 'object' && toolChoice.type === "function") {
      const fname = toolChoice.function?.name;
      if (fname && processed.length > 0 && processed[processed.length - 1].role === "user") {
        const last = { ...processed[processed.length - 1] };
        const content = contentToString(last.content || "");
        last.content = content + `\n\n请使用 ${fname} 函数来处理这个请求。`;
        processed[processed.length - 1] = last;
      }
    }
  } else {
    processed = [...messages];
  }
  
  // Handle tool/function messages
  const finalMsgs = [];
  for (const m of processed) {
    const role = m.role;
    if (role === "tool" || role === "function") {
      const toolName = m.name || "unknown";
      const toolContent = contentToString(m.content || "");
      
      // Ensure content is not empty and doesn't contain None
      let content = `工具 ${toolName} 返回结果:\n\`\`\`json\n${toolContent}\n\`\`\``;
      if (!content.trim()) {
        content = `工具 ${toolName} 执行完成`;
      }
      
      finalMsgs.push({
        role: "assistant",
        content: content,
      });
    } else {
      // For regular messages, ensure content is string format
      const finalMsg = { ...m };
      const content = contentToString(finalMsg.content || "");
      finalMsg.content = content;
      finalMsgs.push(finalMsg);
    }
  }
  
  return finalMsgs;
}

// Generate tool prompt
function generateToolPrompt(tools) {
  if (!tools || tools.length === 0) {
    return "";
  }
  
  const toolDefinitions = [];
  for (const tool of tools) {
    if (tool.type !== "function") {
      continue;
    }
    
    const functionSpec = tool.function || {};
    const functionName = functionSpec.name || "unknown";
    const functionDescription = functionSpec.description || "";
    const parameters = functionSpec.parameters || {};
    
    // Create structured tool definition
    const toolInfo = [`## ${functionName}`, `**Purpose**: ${functionDescription}`];
    
    // Add parameter details
    const parameterProperties = parameters.properties || {};
    const requiredParameters = new Set(parameters.required || []);
    
    if (Object.keys(parameterProperties).length > 0) {
      toolInfo.push("**Parameters**:");
      for (const [paramName, paramDetails] of Object.entries(parameterProperties)) {
        const paramType = paramDetails?.type || "any";
        const paramDesc = paramDetails?.description || "";
        const requirementFlag = requiredParameters.has(paramName) ? "**Required**" : "*Optional*";
        toolInfo.push(`- \`${paramName}\` (${paramType}) - ${requirementFlag}: ${paramDesc}`);
      }
    }
    
    toolDefinitions.push(toolInfo.join("\n"));
  }
  
  if (toolDefinitions.length === 0) {
    return "";
  }
  
  // Build comprehensive tool prompt
  const promptTemplate = (
    "\n\n# AVAILABLE FUNCTIONS\n" + toolDefinitions.join("\n\n---\n") + "\n\n# USAGE INSTRUCTIONS\n" +
    "When you need to execute a function, respond ONLY with a JSON object containing tool_calls:\n" +
    "\`\`\`json\n" +
    "{\n" +
    '  "tool_calls": [\n' +
    "    {\n" +
    '      "id": "call_xxx",\n' +
    '      "type": "function",\n' +
    '      "function": {\n' +
    '        "name": "function_name",\n' +
    '        "arguments": "{\\"param1\\": \\"value1\\"}"\n' +
    "      }\n" +
    "    }\n" +
    "  ]\n" +
    "}\n" +
    "\`\`\`\n" +
    "Important: No explanatory text before or after the JSON. The 'arguments' field must be a JSON string, not an object.\n"
  );
  
  return promptTemplate;
}

// Get authentication token
async function getAuthToken() {
  if (CONFIG.ANONYMOUS_MODE) {
    try {
      const token = await getAnonymousToken();
      debugLog(`匿名token获取成功: ${token.substring(0, 10)}...`);
      return token;
    } catch (error) {
      debugLog(`匿名token获取失败，回退固定token: ${error.message}`);
    }
  }
  
  return CONFIG.BACKUP_TOKEN;
}

// Get anonymous token
async function getAnonymousToken() {
  const headers = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "X-FE-Version": "prod-fe-1.0.70",
    "Origin": CONFIG.CLIENT_HEADERS["Origin"],
    "Referer": `${CONFIG.CLIENT_HEADERS["Origin"]}/`,
  };
  
  const response = await fetch(`${CONFIG.CLIENT_HEADERS["Origin"]}/api/v1/auths/`, {
    method: "GET",
    headers: headers,
  });
  
  if (response.status !== 200) {
    throw new Error(`anon token status=${response.status}`);
  }
  
  const data = await response.json();
  const token = data.token;
  if (!token) {
    throw new Error("anon token empty");
  }
  
  return token;
}

// Transform thinking content
function transformThinkingContent(content) {
  // Remove summary tags
  content = content.replace(/<summary>.*?<\/summary>/gs, '');
  // Clean up remaining tags
  content = content.replace("</thinking>", "").replace("<Full>", "").replace("</Full>", "");
  content = content.trim();
  
  if (CONFIG.THINKING_PROCESSING === "think") {
    content = content.replace(/<details[^>]*>/g, '<span>');
    content = content.replace(/<\/details>/g, '</span>');
  } else if (CONFIG.THINKING_PROCESSING === "strip") {
    content = content.replace(/<details[^>]*>/g, '');
    content = content.replace(/<\/details>/g, '');
  }
  
  // Remove line prefixes
  content = content.trimStart("> ");
  content = content.replace(/\n> /g, "\n");
  
  return content.trim();
}

// Handle stream response
async function handleStreamResponse(upstreamReq, chatId, authToken, hasTools) {
  debugLog(`开始处理流式响应 (chat_id=${chatId})`);
  
  try {
    const response = await callUpstreamApi(upstreamReq, chatId, authToken);
    
    if (response.status !== 200) {
      debugLog(`上游返回错误状态: ${response.status}`);
      if (CONFIG.DEBUG_LOGGING) {
        const errorText = await response.text();
        debugLog(`上游错误响应: ${errorText}`);
      }
      return new Response("data: {\"error\": \"Upstream error\"}\n\n", {
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
          'Access-Control-Allow-Origin': '*',
        }
      });
    }
    
    // Create a readable stream for the SSE response
    const { readable, writable } = new TransformStream();
    const writer = writable.getWriter();
    const encoder = new TextEncoder();
    
    // Process the stream in the background
    (async () => {
      try {
        // Send initial role chunk
        const firstChunk = createOpenAIResponseChunk(
          CONFIG.PRIMARY_MODEL,
          { role: "assistant" }
        );
        await writer.write(encoder.encode(`data: ${JSON.stringify(firstChunk)}\n\n`));
        
        // Process stream
        debugLog("开始读取上游SSE流");
        let sentInitialAnswer = false;
        let bufferedContent = "";
        let toolCalls = null;
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop(); // Keep the last incomplete line in buffer
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.substring(6));
                
                // Check for errors
                if (data.error || data.data?.error || (data.data?.inner?.error)) {
                  const error = data.error || data.data?.error || (data.data?.inner?.error);
                  debugLog(`上游错误: code=${error.code}, detail=${error.detail}`);
                  
                  // Send end chunk
                  const endChunk = createOpenAIResponseChunk(
                    CONFIG.PRIMARY_MODEL,
                    null,
                    "stop"
                  );
                  await writer.write(encoder.encode(`data: ${JSON.stringify(endChunk)}\n\n`));
                  await writer.write(encoder.encode("data: [DONE]\n\n"));
                  return;
                }
                
                debugLog(`解析成功 - 类型: ${data.type}, 阶段: ${data.data?.phase}, ` +
                         `内容长度: ${data.data?.delta_content?.length || 0}, 完成: ${data.data?.done}`);
                
                // Process content
                let content = data.data?.delta_content || data.data?.edit_content;
                
                if (!content) {
                  continue;
                }
                
                // Transform thinking content
                if (data.data?.phase === "thinking") {
                  content = transformThinkingContent(content);
                }
                
                // Buffer content if tools are enabled
                if (hasTools) {
                  bufferedContent += content;
                } else {
                  // Handle initial answer content
                  if (!sentInitialAnswer && 
                      data.data?.edit_content && 
                      data.data?.phase === "answer") {
                    
                    const editContent = extractEditContent(data.data.edit_content);
                    if (editContent) {
                      debugLog(`发送普通内容: ${editContent}`);
                      const chunk = createOpenAIResponseChunk(
                        CONFIG.PRIMARY_MODEL,
                        { content: editContent }
                      );
                      await writer.write(encoder.encode(`data: ${JSON.stringify(chunk)}\n\n`));
                      sentInitialAnswer = true;
                    }
                  }
                  
                  // Handle delta content
                  if (data.data?.delta_content) {
                    if (content) {
                      if (data.data?.phase === "thinking") {
                        debugLog(`发送思考内容: ${content}`);
                        const chunk = createOpenAIResponseChunk(
                          CONFIG.PRIMARY_MODEL,
                          { reasoning_content: content }
                        );
                        await writer.write(encoder.encode(`data: ${JSON.stringify(chunk)}\n\n`));
                      } else {
                        debugLog(`发送普通内容: ${content}`);
                        const chunk = createOpenAIResponseChunk(
                          CONFIG.PRIMARY_MODEL,
                          { content: content }
                        );
                        await writer.write(encoder.encode(`data: ${JSON.stringify(chunk)}\n\n`));
                      }
                    }
                  }
                }
                
                // Check if done
                if (data.data?.done || data.data?.phase === "done") {
                  debugLog("检测到流结束信号");
                  
                  if (hasTools) {
                    // Try to extract tool calls from buffered content
                    toolCalls = extractToolInvocations(bufferedContent);
                    
                    if (toolCalls) {
                      // Send tool calls with proper format
                      for (let i = 0; i < toolCalls.length; i++) {
                        const tc = toolCalls[i];
                        const toolCallDelta = {
                          index: i,
                          id: tc.id,
                          type: tc.type || "function",
                          function: tc.function || {},
                        };
                        
                        const outChunk = createOpenAIResponseChunk(
                          CONFIG.PRIMARY_MODEL,
                          { tool_calls: [toolCallDelta] }
                        );
                        await writer.write(encoder.encode(`data: ${JSON.stringify(outChunk)}\n\n`));
                      }
                    } else {
                      // Send regular content
                      const trimmedContent = removeToolJsonContent(bufferedContent);
                      if (trimmedContent) {
                        const contentChunk = createOpenAIResponseChunk(
                          CONFIG.PRIMARY_MODEL,
                          { content: trimmedContent }
                        );
                        await writer.write(encoder.encode(`data: ${JSON.stringify(contentChunk)}\n\n`));
                      }
                    }
                  }
                  
                  // Send final chunk
                  const finishReason = toolCalls ? "tool_calls" : "stop";
                  const endChunk = createOpenAIResponseChunk(
                    CONFIG.PRIMARY_MODEL,
                    null,
                    finishReason
                  );
                  await writer.write(encoder.encode(`data: ${JSON.stringify(endChunk)}\n\n`));
                  await writer.write(encoder.encode("data: [DONE]\n\n"));
                  debugLog("流式响应完成");
                  return;
                }
              } catch (e) {
                debugLog(`解析SSE数据失败: ${e.message}`);
              }
            }
          }
        }
      } catch (error) {
        debugLog(`处理流式响应时发生错误: ${error.message}`);
        await writer.write(encoder.encode("data: {\"error\": \"Stream processing error\"}\n\n"));
      } finally {
        await writer.close();
      }
    })();
    
    return new Response(readable, {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*',
      }
    });
    
  } catch (error) {
    debugLog(`调用上游失败: ${error.message}`);
    return new Response("data: {\"error\": \"Failed to call upstream\"}\n\n", {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*',
      }
    });
  }
}

// Handle non-stream response
async function handleNonStreamResponse(upstreamReq, chatId, authToken, hasTools) {
  debugLog(`开始处理非流式响应 (chat_id=${chatId})`);
  
  try {
    const response = await callUpstreamApi(upstreamReq, chatId, authToken);
    
    if (response.status !== 200) {
      debugLog(`上游返回错误状态: ${response.status}`);
      if (CONFIG.DEBUG_LOGGING) {
        const errorText = await response.text();
        debugLog(`上游错误响应: ${errorText}`);
      }
      return new Response(JSON.stringify({ error: "Upstream error" }), {
        status: 502,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        }
      });
    }
    
    // Collect full response
    const fullContent = [];
    debugLog("开始收集完整响应内容");
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // Keep the last incomplete line in buffer
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.substring(6));
            
            if (data.data?.delta_content) {
              let content = data.data.delta_content;
              
              if (data.data?.phase === "thinking") {
                content = transformThinkingContent(content);
              }
              
              if (content) {
                fullContent.push(content);
              }
            }
            
            if (data.data?.done || data.data?.phase === "done") {
              debugLog("检测到完成信号，停止收集");
              break;
            }
          } catch (e) {
            debugLog(`解析SSE数据失败: ${e.message}`);
          }
        }
      }
    }
    
    const finalContent = fullContent.join('');
    debugLog(`内容收集完成，最终长度: ${finalContent.length}`);
    
    // Handle tool calls for non-streaming
    let toolCalls = null;
    let finishReason = "stop";
    let messageContent = finalContent;
    
    if (hasTools) {
      toolCalls = extractToolInvocations(finalContent);
      if (toolCalls) {
        // Content must be null when tool_calls are present (OpenAI spec)
        messageContent = null;
        finishReason = "tool_calls";
        debugLog(`提取到工具调用: ${JSON.stringify(toolCalls)}`);
      } else {
        // Remove tool JSON from content
        messageContent = removeToolJsonContent(finalContent);
        if (!messageContent) {
          messageContent = finalContent; // 保留原内容如果清理后为空
        }
      }
    }
    
    // Build response
    const responseData = {
      id: `chatcmpl-${Math.floor(Date.now() / 1000)}`,
      object: "chat.completion",
      created: Math.floor(Date.now() / 1000),
      model: CONFIG.PRIMARY_MODEL,
      choices: [{
        index: 0,
        message: {
          role: "assistant",
          content: messageContent,
          tool_calls: toolCalls
        },
        finish_reason: finishReason
      }],
      usage: {
        prompt_tokens: 0,
        completion_tokens: 0,
        total_tokens: 0
      }
    };
    
    debugLog("非流式响应发送完成");
    return new Response(JSON.stringify(responseData), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      }
    });
    
  } catch (error) {
    debugLog(`调用上游失败: ${error.message}`);
    return new Response(JSON.stringify({ error: "Failed to call upstream" }), {
      status: 502,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      }
    });
  }
}

// Call upstream API
async function callUpstreamApi(upstreamReq, chatId, authToken) {
  const headers = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-US;q=0.7",
    "sec-ch-ua": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "X-FE-Version": "prod-fe-1.0.70",
    "Origin": CONFIG.CLIENT_HEADERS["Origin"],
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Authorization": `Bearer ${authToken}`,
    "Referer": `${CONFIG.CLIENT_HEADERS["Origin"]}/c/${chatId}`,
  };
  
  debugLog(`调用上游API: ${CONFIG.API_ENDPOINT}`);
  debugLog(`上游请求体: ${JSON.stringify(upstreamReq)}`);
  
  const response = await fetch(CONFIG.API_ENDPOINT, {
    method: "POST",
    headers: headers,
    body: JSON.stringify(upstreamReq),
  });
  
  debugLog(`上游响应状态: ${response.status}`);
  return response;
}

// Create OpenAI response chunk
function createOpenAIResponseChunk(model, delta, finishReason) {
  return {
    id: `chatcmpl-${Math.floor(Date.now() / 1000)}`,
    object: "chat.completion.chunk",
    created: Math.floor(Date.now() / 1000),
    model: model,
    choices: [{
      index: 0,
      delta: delta || {},
      finish_reason: finishReason
    }]
  };
}

// Extract edit content
function extractEditContent(editContent) {
  const parts = editContent.split("</details>");
  return parts.length > 1 ? parts[1] : "";
}

// Extract tool invocations
function extractToolInvocations(text) {
  if (!text) {
    return null;
  }
  
  // Limit scan size for performance
  const scannableText = text.substring(0, CONFIG.SCAN_LIMIT);
  
  // Attempt 1: Extract from JSON code blocks
  const jsonBlockRegex = /```json\s*(\{.*?\})\s*```/gs;
  const jsonBlocks = scannableText.match(jsonBlockRegex);
  
  if (jsonBlocks) {
    for (const jsonBlock of jsonBlocks) {
      try {
        const jsonMatch = jsonBlock.match(/```json\s*(\{.*?\})\s*```/s);
        if (jsonMatch) {
          const parsedData = JSON.parse(jsonMatch[1]);
          const toolCalls = parsedData.tool_calls;
          if (toolCalls && Array.isArray(toolCalls)) {
            // Ensure arguments field is a string
            for (const tc of toolCalls) {
              if (tc.function) {
                const func = tc.function;
                if (func.arguments) {
                  if (typeof func.arguments === 'object') {
                    // Convert dict to JSON string
                    func.arguments = JSON.stringify(func.arguments);
                  } else if (typeof func.arguments !== 'string') {
                    func.arguments = JSON.stringify(func.arguments);
                  }
                }
              }
            }
            return toolCalls;
          }
        }
      } catch (e) {
        continue;
      }
    }
  }
  
  // Attempt 2: Extract inline JSON objects using bracket balance method
  // Look for JSON objects containing "tool_calls"
  let i = 0;
  while (i < scannableText.length) {
    if (scannableText[i] === '{') {
      // Try to find matching closing brace
      let braceCount = 1;
      let j = i + 1;
      let inString = false;
      let escapeNext = false;
      
      while (j < scannableText.length && braceCount > 0) {
        if (escapeNext) {
          escapeNext = false;
        } else if (scannableText[j] === '\\') {
          escapeNext = true;
        } else if (scannableText[j] === '"' && !escapeNext) {
          inString = !inString;
        } else if (!inString) {
          if (scannableText[j] === '{') {
            braceCount++;
          } else if (scannableText[j] === '}') {
            braceCount--;
          }
        }
        j++;
      }
      
      if (braceCount === 0) {
        // Found a complete JSON object
        const jsonStr = scannableText.substring(i, j);
        try {
          const parsedData = JSON.parse(jsonStr);
          const toolCalls = parsedData.tool_calls;
          if (toolCalls && Array.isArray(toolCalls)) {
            // Ensure arguments field is a string
            for (const tc of toolCalls) {
              if (tc.function) {
                const func = tc.function;
                if (func.arguments) {
                  if (typeof func.arguments === 'object') {
                    // Convert dict to JSON string
                    func.arguments = JSON.stringify(func.arguments);
                  } else if (typeof func.arguments !== 'string') {
                    func.arguments = JSON.stringify(func.arguments);
                  }
                }
              }
            }
            return toolCalls;
          }
        } catch (e) {
          // Ignore parsing errors
        }
      }
      
      i++;
    } else {
      i++;
    }
  }
  
  // Attempt 3: Parse natural language function calls
  const functionCallRegex = /调用函数\s*[：:]\s*([\w\-\.]+)\s*(?:参数|arguments)[：:]\s*(\{.*?\})/gs;
  const naturalLangMatch = functionCallRegex.exec(scannableText);
  
  if (naturalLangMatch) {
    const functionName = naturalLangMatch[1].trim();
    const argumentsStr = naturalLangMatch[2].trim();
    try {
      // Validate JSON format
      JSON.parse(argumentsStr);
      return [{
        id: `call_${Date.now() * 1000000}`,
        type: "function",
        function: { name: functionName, arguments: argumentsStr },
      }];
    } catch (e) {
      return null;
    }
  }
  
  return null;
}

// Remove tool JSON content
function removeToolJsonContent(text) {
  // Step 1: Remove fenced tool JSON blocks
  const jsonBlockRegex = /```json\s*(\{.*?\})\s*```/gs;
  let cleanedText = text.replace(jsonBlockRegex, (match, jsonContent) => {
    try {
      const parsedData = JSON.parse(jsonContent);
      if ("tool_calls" in parsedData) {
        return "";
      }
    } catch (e) {
      // Ignore parsing errors
    }
    return match;
  });
  
  // Step 2: Remove inline tool JSON - using bracket balance method
  // Find all possible JSON objects and precisely remove those containing tool_calls
  const result = [];
  let i = 0;
  
  while (i < cleanedText.length) {
    if (cleanedText[i] === '{') {
      // Try to find matching closing brace
      let braceCount = 1;
      let j = i + 1;
      let inString = false;
      let escapeNext = false;
      
      while (j < cleanedText.length && braceCount > 0) {
        if (escapeNext) {
          escapeNext = false;
        } else if (cleanedText[j] === '\\') {
          escapeNext = true;
        } else if (cleanedText[j] === '"' && !escapeNext) {
          inString = !inString;
        } else if (!inString) {
          if (cleanedText[j] === '{') {
            braceCount++;
          } else if (cleanedText[j] === '}') {
            braceCount--;
          }
        }
        j++;
      }
      
      if (braceCount === 0) {
        // Found a complete JSON object
        const jsonStr = cleanedText.substring(i, j);
        try {
          const parsed = JSON.parse(jsonStr);
          if ("tool_calls" in parsed) {
            // This is a tool call, skip it
            i = j;
            continue;
          }
        } catch (e) {
          // Ignore parsing errors
        }
      }
      
      // Not a tool call or couldn't parse, keep this character
      result.push(cleanedText[i]);
      i++;
    } else {
      result.push(cleanedText[i]);
      i++;
    }
  }
  
  return result.join('').trim();
}