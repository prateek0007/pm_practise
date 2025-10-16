# Using the Intelligent SureCli System

## Overview
The Intelligent SureCli System is designed to automatically parse AI responses and perform file operations based on the instructions provided. This guide explains how to use the system effectively.

## How It Works
1. The AI generates a response in one of the supported JSON formats
2. SureCli parses the response and identifies file operations
3. The system executes the operations automatically
4. Detailed logs are provided in real-time
5. Errors are automatically reported to bug-list.md

## Supported JSON Formats

### 1. Structured File Operations (Preferred)
```json
{
  "file_operations": [
    {
      "filename": "path/to/file.ext",
      "operation": "write",
      "content": "File content here"
    }
  ]
}
```

### 2. Legacy Files Array
```json
{
  "files": [
    {
      "path": "file.ext",
      "content": "File content here"
    }
  ]
}
```

### 3. Auto-Detected Key-Value Pairs
```json
{
  "readme.md": "# Project README\n\nContent here",
  "src/main.py": "print('Hello World')"
}
```

## Available Operations

### Write/Create
Creates a new file or overwrites an existing one:
```json
{
  "filename": "example.txt",
  "operation": "write",
  "content": "This is the file content"
}
```

### Append/Add
Adds content to an existing file:
```json
{
  "filename": "example.txt",
  "operation": "append",
  "content": "Additional content"
}
```

### Delete/Remove
Deletes a file or directory:
```json
{
  "filename": "unwanted.txt",
  "operation": "delete"
}
```

### Search/Find
Searches for content in a file:
```json
{
  "filename": "example.txt",
  "operation": "search",
  "content": "search term"
}
```

### Create Directory
Creates a new directory:
```json
{
  "filename": "new_directory/",
  "operation": "create_dir"
}
```

### Replace
Replaces text in an existing file:
```json
{
  "filename": "example.txt",
  "operation": "replace",
  "search": "old text",
  "replace": "new text"
}
```

## Real-Time Logging

The system provides detailed feedback during operations:

```
[INFO] 🧠 SureCli Intelligent CLI: Analyzing AI response for file operations...
[INFO] 📂 Working directory: /path/to/project
[INFO] 🔧 Operation #1: WRITE -> example.txt
[INFO] 💾 Writing file: example.txt
[INFO] ✅ File created: example.txt (25 chars)
[INFO] 📊 Operation Summary: 1/1 operations successful
```

## Error Handling

When an operation fails, the system:
1. Logs the error with details
2. Writes a bug report to bug-list.md
3. Continues with other operations
4. Provides clear feedback about what went wrong

Example error log:
```
[ERROR] ❌ Operation #1 failed: Permission denied
[INFO] 📝 Bug report written to: bug-list.md
```

## Best Practices

### 1. Use Structured Format When Possible
The structured file_operations array is the most reliable format:
```json
{
  "file_operations": [
    {
      "filename": "document.md",
      "operation": "write",
      "content": "# Title\n\nContent"
    }
  ]
}
```

### 2. Provide Clear Filenames
Use descriptive filenames with appropriate extensions:
- `README.md` for documentation
- `main.py` for Python code
- `styles.css` for CSS files

### 3. Handle Directory Creation
The system automatically creates parent directories, but you can explicitly create directories:
```json
{
  "file_operations": [
    {
      "filename": "src/",
      "operation": "create_dir"
    },
    {
      "filename": "src/main.py",
      "operation": "write",
      "content": "print('Hello')"
    }
  ]
}
```

### 4. Use Replace Operations Carefully
When using replace operations, be specific with your search terms:
```json
{
  "file_operations": [
    {
      "filename": "config.py",
      "operation": "replace",
      "search": "DEBUG = False",
      "replace": "DEBUG = True"
    }
  ]
}
```

## Troubleshooting

### No Operations Performed
If you see "No file operations were performed":
1. Check that your JSON is properly formatted
2. Ensure you're using one of the supported formats
3. Verify that your content contains actual file operations

### File Not Found Errors
If files aren't being found:
1. Check the working directory path
2. Verify file paths are relative to the working directory
3. Use absolute paths if needed

### Permission Errors
If you encounter permission errors:
1. Check that you have write permissions to the directory
2. Verify that files aren't locked by other processes
3. Run with appropriate privileges if needed

## Example Workflows

### Creating a New Project
```json
{
  "file_operations": [
    {
      "filename": "README.md",
      "operation": "write",
      "content": "# My New Project\n\nDescription here"
    },
    {
      "filename": "src/",
      "operation": "create_dir"
    },
    {
      "filename": "src/main.py",
      "operation": "write",
      "content": "print('Hello, World!')"
    },
    {
      "filename": "requirements.txt",
      "operation": "write",
      "content": "requests==2.28.1"
    }
  ]
}
```

### Updating Documentation
```json
{
  "file_operations": [
    {
      "filename": "README.md",
      "operation": "append",
      "content": "\n\n## Installation\n\npip install -r requirements.txt"
    },
    {
      "filename": "docs/changelog.md",
      "operation": "write",
      "content": "# Changelog\n\n- Added new feature"
    }
  ]
}
```

### Refactoring Code
```json
{
  "file_operations": [
    {
      "filename": "src/utils.py",
      "operation": "replace",
      "search": "def old_function():\n    pass",
      "replace": "def new_function():\n    return 'updated'"
    },
    {
      "filename": "src/main.py",
      "operation": "replace",
      "search": "old_function()",
      "replace": "new_function()"
    }
  ]
}
```