# Universal Field Analysis Prompt
## Objective
Act as an intelligent agent that analyzes any specified folder or file and generates field usage patterns in a standardized JSON format. Follow the Universal Field Analysis Context Guide to produce consistent output regardless of technology stack.
## Instructions
1. **Read the Universal Field Analysis Context Guide** - Understand the standardized format and processing instructions
2. **Analyze the specified folder or file** - Identify all UI components and their field usage patterns
3. **For each unique field type**, generate JSON entries with standardized keywords
4. **Follow the Universal Processing Instructions** from the guide
## Context Reference
Read and follow the specifications in: @.sureai/UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md
This file contains:
- Universal Field Analysis Process
- Standardized Keywords
- Generic Field Types
- Universal Usage Patterns
- Processing Instructions
- Repetition Pattern Handling
## Required Output Format
Return a JSON array with the following structure for each unique field pattern under .sureai/flf-json.txt and then using the json as request body call the flf mcp server using this tool: saveflf and pass the json which is in .sureai/flf-json.txt as request body and then that output save it in .sureai/flf-mcp-response.txt.
:
```json
[
  {
    "techStack": "generic",
    "javacode": "Standardized template with fieldname and Labelfieldname placeholders",
    "operation_type": "ui_component_section",
    "fieldtype": "generic"
  }
]
```
## Processing Rules
1. **Read UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md first** - Understand the framework completely
2. **Identify all unique field types** in the specified folder/file
3. **For each field type**, locate all usage patterns and categorize by operation type
4. **Generate exactly one JSON entry per unique field pattern**
5. **Use standardized keywords** as specified in the guide
6. **Apply foreach markers** for repeated code sections
7. **Return only the JSON array** - no additional text or explanations
## Standardized Keywords
- `fieldname` - Replaces actual field names
- `Labelfieldname` - Replaces actual label text
- `fieldtype` - The data type of the field
- `fieldOption` - Individual option values for select fields
- `subfield` - Subfield names in nested objects or one-to-many relationships
## Repetition Pattern Handling
When identical code sections are repeated with only value differences:
1. Wrap the repeating section with `//foreachentrysetstart` and `//foreachentrysetend`
2. Replace specific values with appropriate standardized keywords
Example:
```html
//foreachentrysetstart
fieldOption
//foreachentrysetend
```
## Output Requirements
- **Return only the JSON array** - no additional text, no file paths, no explanations
- **Do not create any files** - output JSON directly to stdout
- **No markdown formatting** - plain JSON only
- **No wrapper text** - just the JSON array
- **Use valid JSON syntax** - properly escaped and formatted
## Critical Requirements
- **Each unique field pattern must have exactly one JSON entry**
- **Follow the exact JSON structure** from the guide
- **Return only JSON** - no markdown, no explanations, no file creation
- **Use generic operation types** applicable to any UI framework
- **Do not create any files** - return only the JSON output directly
- **Apply foreach markers** for repeated code sections
- **Handle new field types** by applying the universal patterns
- **Work with any technology stack** by focusing on field patterns rather than syntax
## Target Processing
The folder or file path will be provided at the end of this prompt. Process the target according to these rules:
1. Analyze all files in the provided path for UI component field usage patterns
2. Identify all unique field types and their usage across different operation types
3. Extract code patterns and apply standardized keywords
4. Generate standardized JSON entries following the universal guide
5. Apply foreach markers for repeated code sections
To use this prompt, simply add the folder or file path at the end after specifying this prompt.
Example usage:
"Analyze the field patterns in /path/to/your/project using the Universal Field Analysis Context Guide"
The AI should identify the path as the final part of the input and process it accordingly.
## Expected Output
Return only a JSON array following the format specified in the Universal Field Analysis Context Guide. The output should contain entries for all field patterns found in the target, with each unique pattern having one entry.
Example minimal output:
```json
[/* array of field usage patterns */]
```
- **FOLDER_NAME = Enter by user when workflow is chosen inserted its value here in the prompt*
- **URL = Enter by user when workflow is chosen inserted its value here in the prompt*

From the above URL first step is to clone the project then search the folder name within that cloned project. Return a JSON array with the following structure for each unique field pattern under .sureai/flf-json.txt and then using the json as request body call the flf mcp server using this tool: saveflf and pass the json which is in .sureai/flf-json.txt as request body and then that output save it in .sureai/flf-mcp-response.txt.
