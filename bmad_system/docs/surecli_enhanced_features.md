# Enhanced SureCli Intelligent CLI System

## Overview

The Enhanced SureCli is an intelligent command-line interface that can understand AI responses and autonomously decide what file operations to perform. It supports multiple input formats and provides real-time logging with detailed user feedback.

## Key Features

### 1. Intelligent File Operations
The system can automatically:
- Parse AI responses for file operations
- Search for existing files before creating new ones
- Perform self-correction through bug reporting
- Provide real-time logging with emojis for better user experience

### 2. Multiple Input Format Support

#### Structured File Operations (Preferred)
```json
{
  "file_operations": [
    {
      "filename": "path/to/file.ext",
      "operation": "write|append|delete|search|create_dir|replace",
      "content": "file content or search term",
      "search": "text to search for (for replace operations)",
      "replace": "text to replace with (for replace operations)",
      "location": "optional/custom/path"
    }
  ]
}
```

#### Legacy Files Array (Backward Compatibility)
```json
{
  "files": [
    {
      "path": "file.ext",
      "content": "...",
      "is_dir": false
    }
  ]
}
```

#### Auto-Detection from Content Keys
```json
{
  "readme.md": "content",
  "src/app.py": "code"
}
```

### 3. Supported Operations

| Operation | Aliases | Description |
|-----------|---------|-------------|
| write | create, w | Create or overwrite files |
| append | add, a | Add content to existing files |
| delete | remove, rm, d | Delete files or directories |
| search | find, s | Search for content in files |
| create_dir | mkdir, dir | Create directories |
| replace | replace_text, r | Replace text in existing files |

### 4. Advanced Features

#### File Search
Before performing any operation, SureCli automatically searches for existing files in the working directory and subdirectories:
- Exact filename matching
- Case-insensitive matching
- Partial filename matching
- Smart directory traversal (skips hidden directories and virtual environments)

#### Self-Correction
When operations fail, SureCli automatically logs detailed bug reports to `bug-list.md` for review and correction.

#### Real-Time Logging
All operations are logged with emojis for better visual feedback:
- 💾 Writing files
- 📎 Appending to files
- 🗑️ Deleting files
- 🔍 Searching in files
- 📁 Creating directories
- 🔄 Replacing content
- 📝 Bug reporting

## Usage Examples

### Creating and Modifying Files
```json
{
  "file_operations": [
    {
      "filename": "README.md",
      "operation": "write",
      "content": "# Project Title\n\nDescription of the project."
    },
    {
      "filename": "README.md",
      "operation": "append",
      "content": "\n\n## Installation\n\nInstructions here."
    }
  ]
}
```

### Directory Management
```json
{
  "file_operations": [
    {
      "filename": "src/components/",
      "operation": "create_dir"
    },
    {
      "filename": "src/components/button.js",
      "operation": "write",
      "content": "console.log('Button component');"
    }
  ]
}
```

### Search and Replace
```json
{
  "file_operations": [
    {
      "filename": "config.json",
      "operation": "search",
      "content": "development"
    },
    {
      "filename": "config.json",
      "operation": "replace",
      "search": "development",
      "replace": "production"
    }
  ]
}
```

### Auto-Detection Example
```json
{
  "package.json": "{\n  \"name\": \"my-project\",\n  \"version\": \"1.0.0\"\n}",
  "src/index.js": "console.log('Hello, World!');",
  "docs/": ""
}
```

## Error Handling and Self-Correction

When an operation fails, SureCli:
1. Logs the error with detailed information
2. Writes a bug report to `bug-list.md`
3. Continues with other operations
4. Provides actionable feedback for correction

Bug report format:
```markdown
## 🐛 Bug Report - YYYY-MM-DD HH:MM:SS

**Operation:** write
**File:** test.txt
**Error:** Permission denied

**Operation Details:**
{
  "filename": "test.txt",
  "operation": "write",
  "content": "test content"
}

**🔍 Action Required:** Review and correct the operation
```

## Integration with io8 Workflows

For io8 workflows with base projects, SureCli:
- Automatically detects base project structure
- Appends to existing predefined documents
- Maintains strict append-only mode for base project files
- Preserves all existing content in predefined documents

## Logging and User Feedback

SureCli provides comprehensive logging with:
- Operation summaries
- File creation/modification reports
- Error notifications
- Success confirmations
- Detailed debugging information

Example log output:
```
[INFO] 🧠 SureCli Intelligent CLI: Analyzing AI response for file operations...
[INFO] 📂 Working directory: /project
[INFO] 🔧 Found structured file_operations array with 2 operations
[INFO] 🔧 Operation #1: WRITE -> README.md
[INFO] 💾 Writing file: README.md
[INFO] ✅ File created: README.md (120 chars)
[INFO] 📊 Operation Summary: 2/2 operations successful
[INFO] ✅ SureCli Intelligent CLI completed file operations successfully
```