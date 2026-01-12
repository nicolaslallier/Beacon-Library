"""Beacon Library MCP Tools definitions for LM Studio function calling."""

# Tool definitions in OpenAI function calling format
BEACON_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_libraries",
            "description": "List all available document libraries in Beacon Library. Use this to discover what libraries exist before browsing or searching.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browse_library",
            "description": "Browse the contents of a library or directory. Returns list of folders and files at the specified path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "library_id": {
                        "type": "string",
                        "description": "UUID of the library to browse (get this from list_libraries)"
                    },
                    "path": {
                        "type": "string",
                        "description": "Path within the library. Use '/' for root, or '/folder/subfolder' for nested paths",
                        "default": "/"
                    }
                },
                "required": ["library_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a text file. Only works for text-based files (txt, md, json, xml, etc). Returns the file content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "UUID of the file to read (get this from browse_library or search_files)"
                    }
                },
                "required": ["file_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for files by name across all libraries or within a specific library. Returns matching files with their IDs and locations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query - searches in file names"
                    },
                    "library_id": {
                        "type": "string",
                        "description": "Optional: UUID of a specific library to search in. If not provided, searches all libraries."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new text file in a library. Requires write permission to be enabled for the library.",
            "parameters": {
                "type": "object",
                "properties": {
                    "library_id": {
                        "type": "string",
                        "description": "UUID of the library to create the file in"
                    },
                    "path": {
                        "type": "string",
                        "description": "Full path for the new file, e.g., '/notes/my-note.txt' or '/document.md'"
                    },
                    "content": {
                        "type": "string",
                        "description": "The text content of the file"
                    }
                },
                "required": ["library_id", "path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_file",
            "description": "Update the contents of an existing file. Requires write permission to be enabled for the library.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "UUID of the file to update"
                    },
                    "content": {
                        "type": "string",
                        "description": "The new text content of the file"
                    }
                },
                "required": ["file_id", "content"]
            }
        }
    }
]

# System prompt that explains the tools to the LLM
SYSTEM_PROMPT = """You are a helpful assistant with access to Beacon Library, a document management system.

You have the following tools available:

1. **list_libraries** - List all document libraries. Always start here to discover available libraries.

2. **browse_library** - Browse folders and files in a library. You need the library_id from list_libraries.

3. **read_file** - Read the contents of a text file. You need the file_id from browse_library or search_files.

4. **search_files** - Search for files by name. Optionally limit to a specific library.

5. **create_file** - Create a new text file (requires write permission on the library).

6. **update_file** - Update an existing file's content (requires write permission).

When users ask about documents or files:
1. First use list_libraries to see what's available
2. Use browse_library to explore folder structure
3. Use search_files if looking for something specific
4. Use read_file to get the actual content

Always provide helpful summaries of what you find."""
