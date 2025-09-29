import os
import subprocess
import json
import re
import uuid
from flask import Flask, request, jsonify, Response, stream_with_context
from dotenv import load_dotenv
import glob
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# MCP Protocol Schema Definitions
TOOL_SCHEMAS = {
    "analyze_file": {
        "name": "analyze_file",
        "description": "Analyze a file with Ollama AI and get insights based on a user query",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to analyze"
                },
                "query": {
                    "type": "string",
                    "description": "The question or task to perform on the file content"
                }
            },
            "required": ["file_path", "query"]
        }
    },
    "discover_files": {
        "name": "discover_files",
        "description": "Find files in a directory matching a pattern",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory to search in"
                },
                "pattern": {
                    "type": "string",
                    "description": "File pattern to match (e.g., '*.md', '*.py')"
                }
            },
            "required": ["directory", "pattern"]
        }
    }
}

# Standard MCP routes
@app.route("/", methods=["GET", "POST"])
def root():
    return jsonify({"status": "MCP Bridge API is running"})

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for Gemini CLI to verify connection"""
    return jsonify({"status": "ok"})

@app.route("/mcp/health", methods=["GET"])
def mcp_health():
    """MCP protocol health check endpoint for Gemini CLI to verify connection"""
    return jsonify({"status": "ok"})

# Legacy route for backward compatibility
@app.route("/mcp_query", methods=["POST"])
def mcp_query():
    try:
        # Get the prompt and file_path from the request
        data = request.json
        prompt = data.get("prompt", "")
        file_path = data.get("file_path", "")
        
        # Read file content if file_path is provided
        file_content = read_file_content(file_path)
        
        # Build prompt for Ollama
        combined_prompt = f"Here is the content from a file:\n\n{file_content}\n\nUser query: {prompt}\n\nPlease respond to the user query based on the file content."
        
        # Call Ollama API
        full_response = call_ollama_api(combined_prompt)
        
        return jsonify({"answer": full_response})
            
    except Exception as e:
        return jsonify({"error": f"Exception processing request: {str(e)}"})

# MCP Protocol Endpoints
@app.route("/mcp/version", methods=["GET"])
def mcp_version():
    """Return the MCP protocol version"""
    return jsonify({"version": "0.1"})

@app.route("/mcp/tools", methods=["GET"])
def mcp_tools():
    """Return the list of available tools following MCP protocol"""
    tools = list(TOOL_SCHEMAS.values())
    return jsonify({"tools": tools})

@app.route("/mcp/resources", methods=["GET"])
def mcp_resources():
    """Return the list of available resources following MCP protocol"""
    return jsonify({"resources": []})  # No resources implemented yet

@app.route("/mcp/tools/<tool_name>", methods=["POST"])
def execute_tool(tool_name):
    """Execute a tool by name"""
    if tool_name not in TOOL_SCHEMAS:
        return jsonify({"error": f"Tool '{tool_name}' not found"}), 404
    
    try:
        data = request.json
        
        if tool_name == "analyze_file":
            file_path = data.get("file_path")
            query = data.get("query")
            
            if not file_path or not query:
                return jsonify({"error": "Missing required parameters"}), 400
                
            # Read file content
            file_content = read_file_content(file_path)
            
            # Build prompt for Ollama
            combined_prompt = f"Here is the content from a file:\n\n{file_content}\n\nUser query: {query}\n\nPlease respond to the user query based on the file content."
            
            # Call Ollama API
            response = call_ollama_api(combined_prompt)
            
            return jsonify({"result": response})
            
        elif tool_name == "discover_files":
            directory = data.get("directory")
            pattern = data.get("pattern")
            
            if not directory or not pattern:
                return jsonify({"error": "Missing required parameters"}), 400
                
            # Find files matching pattern
            search_path = os.path.join(directory, "**", pattern)
            matching_files = glob.glob(search_path, recursive=True)
            
            return jsonify({"files": matching_files})
            
    except Exception as e:
        return jsonify({"error": f"Error executing tool: {str(e)}"}), 500

@app.route("/mcp/execute", methods=["POST"])
def mcp_execute():
    """Execute a tool following MCP protocol"""
    try:
        data = request.json
        tool_name = data.get("name")
        arguments = data.get("arguments", {})
        execution_id = str(uuid.uuid4())
        
        if tool_name not in TOOL_SCHEMAS:
            return jsonify({
                "error": f"Unknown tool: {tool_name}",
                "execution_id": execution_id
            }), 404
        
        if tool_name == "analyze_file":
            file_path = arguments.get("file_path")
            query = arguments.get("query")
            
            if not file_path or not query:
                return jsonify({
                    "error": "Missing required parameters: file_path and query",
                    "execution_id": execution_id
                }), 400
            
            file_content = read_file_content(file_path)
            combined_prompt = f"Here is the content from a file:\n\n{file_content}\n\nUser query: {query}\n\nPlease respond to the user query based on the file content."
            response = call_ollama_api(combined_prompt)
            
            return jsonify({
                "execution_id": execution_id,
                "result": response
            })
            
        elif tool_name == "discover_files":
            directory = arguments.get("directory")
            pattern = arguments.get("pattern")
            
            if not directory or not pattern:
                return jsonify({
                    "error": "Missing required parameters: directory and pattern",
                    "execution_id": execution_id
                }), 400
            
            try:
                search_path = os.path.join(directory, "**", pattern)
                files = glob.glob(search_path, recursive=True)
                files = [str(Path(f).resolve()) for f in files]
                
                return jsonify({
                    "execution_id": execution_id,
                    "result": {
                        "files": files,
                        "count": len(files)
                    }
                })
            except Exception as e:
                return jsonify({
                    "error": f"Error discovering files: {str(e)}",
                    "execution_id": execution_id
                }), 500
        
    except Exception as e:
        return jsonify({
            "error": f"Exception processing request: {str(e)}",
            "execution_id": str(uuid.uuid4())
        }), 500

# Helper functions
def read_file_content(file_path):
    """Read file content with error handling and frontmatter removal"""
    if not file_path:
        return "No file was provided. Please specify a file_path in your request to analyze specific content."
    
    try:
        # First try to read as UTF-8
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
        except UnicodeDecodeError:
            # If that fails, try reading as binary and decode with latin-1
            with open(file_path, 'rb') as file:
                file_content = file.read().decode('latin-1', errors='ignore')
        
        # Remove YAML frontmatter if present
        file_content = re.sub(r'^---\s*[\s\S]*?---\s*', '', file_content)
        return file_content
    except Exception as e:
        return f"Failed to read file: {str(e)}"

def call_ollama_api(prompt):
    """Call Ollama API and return the full response"""
    curl_command = [
        "curl", "-s", "-X", "POST", "http://localhost:11434/api/generate",
        "-d", json.dumps({"model": "qwen3:1.7b", "prompt": prompt})
    ]
    
    result = subprocess.run(curl_command, capture_output=True, text=True)
    
    if result.returncode != 0:
        return f"Failed to call Ollama API: {result.stderr}"
    
    # Process the streaming response from Ollama
    lines = result.stdout.strip().split('\n')
    
    # Collect all responses
    full_response = ""
    for line in lines:
        try:
            response_obj = json.loads(line)
            if "response" in response_obj:
                full_response += response_obj["response"]
        except json.JSONDecodeError:
            continue
    
    return full_response

if __name__ == "__main__":
    # Get host and port from environment variables
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5004))
    print(f"Starting MCP Bridge server on {host}:{port}")
    print(f"Available tools: {', '.join(TOOL_SCHEMAS.keys())}")
    app.run(host=host, port=port, debug=True)
