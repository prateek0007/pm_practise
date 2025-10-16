## JSON Format Examples

### Structured File Operations (Preferred)
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

### Legacy Files Array (Backward Compatible)
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

### Auto-Detection (Simple Key-Value)
```json
{
  "readme.md": "content",
  "src/app.py": "code"
}
```

## Enhanced Logging and User Feedback

The system provides detailed real-time logging with emojis:
- `🧠` Analyzing AI response
- `🔧` Operation execution
- `💾` File writing
- `📎` File appending
- `🗑️` File deletion
- `🔍` File searching
- `📁` Directory creation
- `🔄` Text replacement
- `📝` Bug report writing
- `✅` Success indicators
- `⚠️` Warnings
- `❌` Errors
- `📊` Operation summaries

## Self-Correction Through Bug Reporting

When operations fail, the system automatically writes bug reports to `bug-list.md` with:
- Timestamp of the error
- Operation details
- Error message
- Full operation JSON for debugging

## File Search Capabilities

Before performing operations, the system searches for files in:
1. The specified absolute path
2. The relative path from the working directory
3. Subdirectories of the working directory (with intelligent matching)

## Error Handling and Self-Correction

When an operation fails, the system:
1. Logs the error with detailed information
2. Writes a bug report to `bug-list.md`
3. Continues with other operations if possible
4. Provides clear feedback to the user about what went wrong

## Backward Compatibility

The enhanced SureCli maintains full backward compatibility with:
- Legacy JSON formats using "files" array
- Simple key-value content structures
- Existing io8 workflow integrations