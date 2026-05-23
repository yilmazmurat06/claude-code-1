"""
Minimal Anthropic API → DeepSeek (OpenAI-format) proxy.
Accepts Anthropic Messages API requests, translates them to OpenAI chat completions,
calls DeepSeek, and translates the response back to Anthropic format.

Usage:
  export DEEPSEEK_API_KEY="sk-..."
  python anthropic-proxy.py --port 4000

Then run Claude Code with:
  export ANTHROPIC_BASE_URL=http://localhost:4000
  export ANTHROPIC_API_KEY="sk-..."
"""

import json
import os
import re
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# Keep urllib import simple
import urllib.request
import urllib.error

class AnthropicProxy(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        path = self.path.split("?")[0]  # Strip query params

        # Log incoming requests for debugging
        print(f"[proxy] POST {self.path}", file=sys.stderr)

        if path == "/v1/messages":
            self._handle_messages(body)
        elif path == "/v1/messages/count_tokens":
            # Token counting stub - Claude Code uses this
            self._handle_count_tokens(body)
        elif path.startswith("/v1/models"):
            self._handle_models()
        else:
            # Forward to DeepSeek as-is
            self._proxy_forward(body)

    def do_GET(self):
        if self.path == "/v1/models" or self.path.startswith("/v1/models"):
            self._handle_models()
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())

    def _handle_messages(self, body):
        """Translate Anthropic Messages request → OpenAI → Anthropic response."""
        # Log incoming request
        print(f"[proxy] ← Claude Code /v1/messages (stream={json.loads(body).get('stream', False) if body else 'parse error'})", file=sys.stderr)
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            self._error(400, "Invalid JSON")
            return

        # Extract Anthropic params
        messages = req.get("messages", [])
        system = req.get("system", "")
        max_tokens = req.get("max_tokens", 4096)
        temperature = req.get("temperature", 0.7)
        top_p = req.get("top_p", None)
        stop = req.get("stop_sequences", None)
        stream = req.get("stream", False)

        # Build OpenAI-format messages
        openai_messages = self._convert_messages(messages, system)

        # Build OpenAI request body
        openai_body = {
            "model": DEEPSEEK_MODEL,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if top_p is not None:
            openai_body["top_p"] = top_p
        if stop:
            openai_body["stop"] = stop

        # Call DeepSeek API
        try:
            resp_data = self._call_deepseek("/v1/chat/completions", openai_body)
        except Exception as e:
            self._error(500, f"DeepSeek API error: {str(e)}")
            return

        if stream:
            self._handle_stream_response(resp_data)
        else:
            self._handle_normal_response(resp_data, req)

    def _convert_messages(self, anthropic_messages, system_prompt):
        """Convert Anthropic messages to OpenAI format."""
        openai_messages = []

        if system_prompt:
            if isinstance(system_prompt, list):
                # Anthropic system can be a list of content blocks
                sys_text = ""
                for block in system_prompt:
                    if isinstance(block, dict) and block.get("type") == "text":
                        sys_text += block.get("text", "") + "\n"
                    elif isinstance(block, str):
                        sys_text += block + "\n"
                system_prompt = sys_text.strip()

            openai_messages.append({
                "role": "system",
                "content": str(system_prompt)
            })

        for msg in anthropic_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Map Anthropic roles to OpenAI
            if role == "assistant":
                openai_role = "assistant"
            else:
                openai_role = "user"

            # Handle content blocks (text + tool_use + tool_result)
            if isinstance(content, list):
                text_parts = []
                tool_calls = []
                tool_call_index = 0

                for block in content:
                    if isinstance(block, str):
                        text_parts.append(block)
                    elif isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            # Convert to OpenAI tool call
                            tool_calls.append({
                                "id": block.get("id", f"call_{tool_call_index}"),
                                "type": "function",
                                "function": {
                                    "name": block.get("name", ""),
                                    "arguments": json.dumps(block.get("input", {}))
                                }
                            })
                            tool_call_index += 1
                        elif block.get("type") == "tool_result":
                            # OpenAI expects tool results as messages with tool_call_id
                            openai_messages.append({
                                "role": "tool",
                                "tool_call_id": block.get("tool_use_id", ""),
                                "content": str(block.get("content", ""))
                            })
                            continue  # Don't add as separate message

                if openai_role == "assistant" and tool_calls:
                    openai_messages.append({
                        "role": openai_role,
                        "content": "\n".join(text_parts) if text_parts else None,
                        "tool_calls": tool_calls
                    })
                elif text_parts:
                    openai_messages.append({
                        "role": openai_role,
                        "content": "\n".join(text_parts)
                    })
            elif isinstance(content, str):
                openai_messages.append({
                    "role": openai_role,
                    "content": content
                })
            else:
                openai_messages.append({
                    "role": openai_role,
                    "content": str(content)
                })

        return openai_messages

    def _call_deepseek(self, path, data):
        """Make an HTTP request to DeepSeek API."""
        url = f"{DEEPSEEK_BASE}{path}"
        payload = json.dumps(data).encode("utf-8")

        # Log the request (truncated for large requests)
        log_data = json.dumps(data)[:200]
        print(f"[proxy] → DeepSeek {path} body={log_data}", file=sys.stderr)

        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {DEEPSEEK_API_KEY}")

        try:
            response = urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print(f"[proxy] ← DeepSeek HTTP {e.code}: {err_body[:300]}", file=sys.stderr)
            raise Exception(f"DeepSeek returned {e.code}: {err_body[:200]}")
        except Exception as e:
            print(f"[proxy] ← DeepSeek connection error: {e}", file=sys.stderr)
            raise

        body = response.read().decode("utf-8")
        if not body.strip():
            print(f"[proxy] ← DeepSeek empty response (status {response.status})", file=sys.stderr)
            raise Exception(f"DeepSeek returned empty response (status {response.status})")

        print(f"[proxy] ← DeepSeek 200 len={len(body)}", file=sys.stderr)
        return json.loads(body)

    def _handle_normal_response(self, openai_resp, anthropic_req):
        """Convert OpenAI chat completion → Anthropic message response."""
        choice = openai_resp.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])

        # Usage
        usage = openai_resp.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        # Build Anthropic response
        stop_reason = choice.get("finish_reason", "end_turn")
        if stop_reason == "stop":
            stop_reason = "end_turn"
        elif stop_reason == "length":
            stop_reason = "max_tokens"
        elif stop_reason == "tool_calls":
            stop_reason = "tool_use"

        content_blocks = []
        if content:
            content_blocks.append({
                "type": "text",
                "text": content
            })

        for tc in tool_calls:
            try:
                args = json.loads(tc["function"]["arguments"])
            except (json.JSONDecodeError, KeyError):
                args = {}
            content_blocks.append({
                "type": "tool_use",
                "id": tc.get("id", f"toolu_{int(time.time()*1000)}"),
                "name": tc["function"]["name"],
                "input": args
            })

        model = openai_resp.get("model", DEEPSEEK_MODEL)
        resp = {
            "id": f"msg_{int(time.time()*1000)}",
            "type": "message",
            "role": "assistant",
            "content": content_blocks,
            "model": model,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            }
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Proxy", "anthropic-to-deepseek")
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode())

    def _handle_stream_response(self, content):
        """Handle streaming via SSE."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        # For now, just return the full response as a single event
        # Proper streaming would need requests with stream=True
        self.wfile.write(f"data: {json.dumps(content)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")

    def _handle_count_tokens(self, body):
        """Stub token counter - returns approximate count."""
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            req = {}

        # Rough estimate: ~4 chars per token
        total_text = json.dumps(req)
        token_count = len(total_text) // 4

        resp = {"input_tokens": max(token_count, 1)}

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode())

    def _handle_models(self):
        """Return a model list stub."""
        resp = {
            "data": [
                {
                    "id": DEEPSEEK_MODEL,
                    "type": "model",
                    "display_name": f"DeepSeek ({DEEPSEEK_MODEL})"
                }
            ],
            "has_more": False,
            "first_id": DEEPSEEK_MODEL,
            "last_id": DEEPSEEK_MODEL
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode())

    def _proxy_forward(self, body):
        """Forward request to DeepSeek as-is."""
        try:
            deepseek_path = self.path.replace("/v1", "/v1", 1)
            url = f"{DEEPSEEK_BASE}{self.path}"
            data = body.encode("utf-8")
            req = urllib.request.Request(url, data=data, method=self.command)
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", f"Bearer {DEEPSEEK_API_KEY}")
            response = urllib.request.urlopen(req, timeout=30)
            resp_body = response.read()
            self.send_response(response.status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(resp_body)
        except Exception as e:
            self._error(502, f"Proxy error: {str(e)}")

    def _error(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": {"type": "proxy_error", "message": message}}).encode())

    def log_message(self, format, *args):
        print(f"[proxy] {args[0]}", file=sys.stderr)


def main():
    port = 4000
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])

    if not DEEPSEEK_API_KEY:
        print("ERROR: DEEPSEEK_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    server = HTTPServer(("127.0.0.1", port), AnthropicProxy)
    print(f"Anthropic→DeepSeek proxy running on http://127.0.0.1:{port}")
    print(f"Model: {DEEPSEEK_MODEL}")
    print(f"Set: export ANTHROPIC_BASE_URL=http://127.0.0.1:{port}")
    print(f"     export ANTHROPIC_API_KEY=$DEEPSEEK_API_KEY")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
