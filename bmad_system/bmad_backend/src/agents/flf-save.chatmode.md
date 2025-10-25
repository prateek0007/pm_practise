# Universal Field Analysis Prompt
## Objective
Act as an intelligent agent that analyzes any specified folder or file and generates field usage patterns in a standardized JSON format. Follow the Universal Field Analysis Context Guide provided below to produce consistent output regardless of technology stack.
## Instructions
1. **Read the Universal Field Analysis Context Guide** - Understand the standardized format and processing instructions
2. **Clone the repository from the provided URL** - Use git to clone the repository if a URL is provided
3. **Analyze the specified folder or file** - Identify all UI components and their field usage patterns
4. **For each unique field type**, generate JSON entries with standardized keywords
5. **Follow the Universal Processing Instructions** from the guide
## Context Reference
Read and follow the specifications in the Universal Field Analysis Context Guide provided below.
This guide contains:
- Universal Field Analysis Process
- Standardized Keywords
- Generic Field Types
- Universal Usage Patterns
- Processing Instructions
- Repetition Pattern Handling
## Required Output Format
Return a JSON array with the following structure for each unique field pattern:
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
1. **Read the Universal Field Analysis Context Guide first** - Understand the framework completely
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
- **No markdown formatting** - plain JSON only
- **No wrapper text** - just the JSON array
- **Use valid JSON syntax** - properly escaped and formatted
## Critical Requirements
- **Each unique field pattern must have exactly one JSON entry**
- **Follow the exact JSON structure** from the guide
- **Return only JSON** - no markdown, no explanations.
- **Use generic operation types** applicable to any UI framework
- **Apply foreach markers** for repeated code sections
- **Handle new field types** by applying the universal patterns
- **Work with any technology stack** by focusing on field patterns rather than syntax
## Target Processing
The folder or file path will be provided at the end of this prompt. Process the target according to these rules:
1. If a URL is provided, first clone the repository using git
2. Navigate to the specified folder name within the cloned repository
3. Analyze all files in the provided path for UI component field usage patterns
4. Identify all unique field types and their usage across different operation types
5. Extract code patterns and apply standardized keywords
6. Generate standardized JSON entries following the universal guide
7. Apply foreach markers for repeated code sections

To use this prompt, simply add the folder or file path at the end after specifying this prompt.
Example usage:
"Analyze the field patterns in Folder Name in cloned directory: [FOLDER_NAME] using the Universal Field Analysis Context Guide"

The AI should identify the path as the final part of the input and process it accordingly - first clone the repository, then search inside the cloned directory for the specified folder name, and finally analyze the field patterns in that folder using the universal field analysis context guide.

## Expected Output
Return only a JSON array following the format specified in the Universal Field Analysis Context Guide. The output should contain entries for all field patterns found in the target, with each unique pattern having one entry.
Example minimal output:
```json
[/* array of field usage patterns */]
```

Write the json in @.sureai/flf-json.txt and then send it as body to the flf mcp server using the flf mcp server tool: saveall. Then flf mcp server will return some output write that output json to a file in @.sureai/flf-mcp.txt.

IMPORTANT: When you receive a prompt that includes "First, clone the repository from [URL]. Then, analyze the field patterns in [FOLDER_NAME]", you should:

1. Clone the repository from the provided URL using your git capabilities
2. Navigate to the specified folder name within the cloned repository
3. Perform field analysis on the files in that folder
4. Generate the JSON output as specified above

The repository cloning and file analysis should be done using your file system access and git capabilities, not by generating shell commands.

When analyzing field patterns, make sure to reference the Universal Field Analysis Context Guide provided above for the standardized format and processing instructions.

## Universal Field Analysis Context Guide Content

# Universal Field Analysis Context Guide

## Overview
This guide provides a universal framework for analyzing field types in any folder or file, regardless of technology stack. It defines standardized patterns, processing instructions, and output formats that can be applied universally.

## Universal Field Analysis Process

### 1. Folder/File Analysis
When given any folder or file path:
1. Scan all files in the folder (or the single file)
2. Identify all UI components and their field usage patterns
3. Categorize each field by type and operation context
4. Extract code patterns for each unique field type

### 2. Field Type Identification
Identify these universal field types:
- Text fields (input type="text")
- Number fields (input type="number")
- Email fields (input type="email")
- Password fields (input type="password")
- Date/Time fields (input type="date", "time", "datetime")
- Textarea fields (multi-line text input)
- Select/Dropdown fields (single selection controls)
- Multi-select fields (multiple selection controls)
- Checkbox fields (boolean selection)
- Radio button fields (single selection from multiple options)
- File upload fields (file input controls)
- One-to-many/Array fields (repeating field groups)
- Nested object fields (fields within objects)
- Data grid fields (tabular data displays)

### 3. Code Pattern Extraction
For each field type, extract code from all relevant files:
- UI Display Elements (columns, cells, lists)
- Form Elements (edit forms, create forms)
- Data Definitions (form groups, validations)
- Data Operations (API calls, data binding)
- Helper Methods (utility functions)

### 4. Repetition Handling
When identical code patterns are found with only label/value differences:
1. Wrap the repeating section with `//foreachentrysetstart` and `//foreachentrysetend`
2. Replace specific values with standardized keywords:
   - `fieldname` - Replaces actual field names
   - `Labelfieldname` - Replaces actual label text
   - `fieldtype` - Replaces actual field types
   - `fieldOption` - Replaces option values in select fields
   - `subfield` - Replaces subfield names in nested/one-to-many fields

## Standardized Keywords (Universal)
- `fieldname` - Replaces the actual field name (e.g., "name", "email", "id")
- `Labelfieldname` - Replaces the actual label text for the field
- `fieldtype` - The data type of the field (text, number, password, etc.)
- `fieldOption` - Individual option values for select fields
- `subfield` - Subfield names in nested objects or one-to-many relationships

## Operation Types (Universal)
Each field usage is categorized by operation type:
1. `datagridColumn` - Field usage in data grid column headers
2. `datagridCell` - Field usage in data grid cells
3. `addForm` - Field usage in creation forms
4. `editForm` - Field usage in edit forms
5. `formGroup` - Field definition in form group
6. `dataGrid` - Field usage in data grid displays
7. `propertyDeclaration` - Variable and property declarations
8. `initialization` - Code to initialize fields in component methods
9. `serialization` - Code to serialize/deserialize field values
10. `dataRetrieval` - Methods to fetch dynamic data for fields
11. `helperMethod` - Additional helper methods required for field functionality

## JSON Output Format
Return a JSON array with the following structure for each unique field pattern:

```json
[
  {
    "techStack": "actual_tech_stack",
    "javacode": "Standardized template with fieldname and Labelfieldname placeholders",
    "operation_type": "ui_component_section",
    "fieldtype": "actual_field_type"
  }
]
```

Use actual technology stacks in the `techStack` field, such as:
- `angularClarity` - For Angular applications using Clarity Design System
- `reactMaterial` - For React applications using Material UI
- `vueElement` - For Vue applications using Element UI
- `springBoot` - For Spring Boot backend applications
- `django` - For Django backend applications
- `flutter` - For Flutter mobile applications
- `reactNative` - For React Native mobile applications

Use actual field types in the `fieldtype` field, such as:
- `text` - For text input fields
- `select` - For dropdown/select fields
- `oneToMany` - For repeating field groups
- `checkbox` - For checkbox fields
- `radio` - For radio button fields
- `textarea` - For multi-line text fields
- `date` - For date input fields
- `file` - For file upload fields
- `nestedObject` - For fields within nested objects
- `datagrid` - For data grid/table fields

## Repetition Pattern Markers
When identical code sections are repeated with only value differences:
1. Wrap the repeating section with `//foreachentrysetstart` and `//foreachentrysetend`
2. Replace specific values with appropriate standardized keywords

Example for a `select` field type in an `angularClarity` technology stack:
```html
<select formControlName="fieldname">
  <option [value]="null">Select Labelfieldname</option>
  //foreachentrysetstart
  <option>fieldOption</option>
  //foreachentrysetend
</select>
```

## Processing Workflow

### Step 1: File Scanning
1. Identify all files in the target folder (HTML, CSS, JS, TS, JSX, Vue, etc.)
2. Parse each file to identify UI components and field usage
3. Map field usage to operation types
4. Identify the technology stack being used (Angular Clarity, React Material, Vue Element, etc.)

### Step 2: Pattern Extraction
1. For each field type, extract relevant code from all files
2. Identify repeated patterns and apply foreach markers
3. Replace specific values with standardized keywords
4. Tag each pattern with the appropriate technology stack

### Step 3: JSON Generation
1. Create JSON entries for each unique field pattern
2. Ensure all standardized keywords are properly applied
3. Use actual technology stack names in the `techStack` field
4. Use actual field type names in the `fieldtype` field
5. Validate JSON structure and formatting

### Step 4: Output
1. Return only the JSON array
2. No additional text, explanations, or formatting
3. Ensure valid JSON syntax

## Technology-Agnostic Patterns

### Text Fields
**Add Form Pattern for Angular Clarity:**
```html
<div class="container">
  <label>Labelfieldname</label>
  <input type="text" formControlName="fieldname" />
</div>
```

**Edit Form Pattern for Angular Clarity:**
```html
<div class="container">
  <label>Labelfieldname</label>
  <input type="text" [(ngModel)]="rowSelected.fieldname" name="fieldname" />
</div>
```

**Form Group Pattern for Angular Clarity:**
```javascript
fieldname: [null]
```

**Data Grid Column Pattern for Angular Clarity:**
```html
<clr-dg-column [clrDgField]="'fieldname'">
  <ng-container *clrDgHideableColumn="{hidden: false}">
    Labelfieldname
  </ng-container>
</clr-dg-column>
```

**Data Grid Cell Pattern for Angular Clarity:**
```html
<clr-dg-cell>{{user.fieldname}}</clr-dg-cell>
```

### Select/Dropdown Fields
**Add Form Pattern for Angular Clarity:**
```html
<div class="container">
  <label>Labelfieldname</label>
  <select formControlName="fieldname">
    <option [value]="null">Select Labelfieldname</option>
    //foreachentrysetstart
    <option>fieldOption</option>
    //foreachentrysetend
  </select>
</div>
```

**Edit Form Pattern for Angular Clarity:**
```html
<div class="container">
  <label>Labelfieldname</label>
  <select name="fieldname" [(ngModel)]="rowSelected.fieldname">
    <option [value]="null">Select Labelfieldname</option>
    //foreachentrysetstart
    <option>fieldOption</option>
    //foreachentrysetend
  </select>
</div>
```

**Form Group Pattern for Angular Clarity:**
```javascript
fieldname: [null]
```

### One-to-Many Fields
**Add Form Pattern for Angular Clarity:**
```html
<!-- one to many code start here -->
<div style="margin-top: 30px;">
  <h4 style="display: inline;">Labelfieldname</h4>
</div>
<hr>
<div class="clr-row">
  <div class="clr-col-lg-12">
    <table class="table" style="width:100%;" formArrayName="fieldname">
      <thead>
        <tr>
          //foreachentrysetstart
          <th class="left" style="width:125px;">fieldOption</th>
          //foreachentrysetend
          <th class="right" style="width:125px;">{{ fieldnamecontrols.length > 1 ? 'Actions' : '' }}</th>
        </tr>
      </thead>
      <tbody>
        <tr *ngFor="let item of fieldnamecontrols; let i=index" [formGroupName]="i">
          //foreachentrysetstart
          <td class="left">
            <input type="text" formControlName="fieldOption" placeholder="Enter fieldOption" style="width:180px" class="clr-input">
          </td>
          //foreachentrysetend
          <td style="width:40px;">
            <a *ngIf="fieldnamecontrols.length > 1" (click)="onRemovefieldname(i)">
              <clr-icon shape="trash" class="is-error"></clr-icon>
            </a>
          </td>
        </tr>
      </tbody>
      <button type="button" class="btn btn-primary button1" (click)="onAddfieldname()">
        <clr-icon shape="plus"></clr-icon>
      </button>
    </table>
  </div>
</div>
<!-- one to many code end here -->
```

**Edit Form Pattern for Angular Clarity:**
```html
<!-- one to many code start here -->
<div class="clr-row">
  <div class="clr-col-lg-12">
    <table class="table" style="width:100%;">
      <thead>
        <tr>
          //foreachentrysetstart
          <th class="left" style="width:200px;">fieldOption</th>
          //foreachentrysetend
          <th class="right" style="width:200px;">{{ fieldnamecomponents?.length >= 1 ? 'Actions' : '' }}</th>
        </tr>
      </thead>
      <tbody>
        <tr *ngFor="let component of fieldnamecomponents; let i = index">
          //foreachentrysetstart
          <td class="left">
            <input type="text" name="fieldOption" [(ngModel)]="component.fieldOption" [ngModelOptions]=" {standalone: true}" placeholder="Enter fieldOption" class="clr-input">
          </td>
          //foreachentrysetend
          <td>
            <a>
              <clr-icon shape="trash" class="is-error" (click)="deleteRow(i)"></clr-icon>
            </a>
          </td>
        </tr>
      </tbody>
      <button type="button" class="btn btn-primary button1" (click)="onEditfieldname()" style="margin-left: 20px;">
        <clr-icon shape="plus"></clr-icon>
      </button>
    </table>
  </div>
</div>
<!-- one to many code end here -->
```

**Form Group Pattern for Angular Clarity:**
```javascript
fieldname: this._fb.array([this.initfieldnameForm()])
```

**Helper Method Patterns for Angular Clarity:**
```javascript
initfieldnameForm() {
  return this._fb.group({
    //foreachentrysetstart
    fieldOption: [null],
    //foreachentrysetend
  });
}

get fieldnamecontrols() {return (this.entryForm.get("fieldname") as FormArray).controls;}

onAddfieldname() {
  (this.entryForm.get("fieldname") as FormArray).push(this.initfieldnameForm());
}

onRemovefieldname(index: number) {
  (this.entryForm.get("fieldname") as FormArray).removeAt(index);
}

onEditfieldname() {
  this.fieldnamecomponents.push({
    //foreachentrysetstart
    fieldOption: "",
    //foreachentrysetend
  });
}

deletefieldnameRow(index) {
  this.fieldnamecomponents.splice(index, 1);
}

fieldnamecomponents;
```

## Extensibility

### For New Field Types
When encountering field types not explicitly covered in this guide:
1. Identify the operation contexts where the field is used (addForm, editForm, datagridColumn, etc.)
2. Extract the **complete code patterns** from the source files, not just inline references
3. Apply the standardized keywords (`fieldname`, `Labelfieldname`, etc.)
4. Use foreach markers for repeated sections
5. Categorize under appropriate operation types
6. Generate JSON entries following the universal format

### For Different Technologies
This guide works with any technology stack because:
- **Frontend Frameworks** (Angular Clarity, React Material, Vue Element, etc.): Map framework-specific syntax to generic patterns
- **Backend Frameworks** (Spring Boot, Django, Express, etc.): Focus on data structure patterns rather than UI syntax
- **Mobile Frameworks** (Flutter, React Native, etc.): Apply the same field analysis principles
- **Desktop Applications** (Electron, JavaFX, etc.): Use the same pattern identification approach

The key is to identify **complete field usage patterns** and operation contexts rather than specific syntax implementations, and to use actual technology stack names in the output.

## Output Requirements
- Return only the JSON array, nothing else
- Use the exact JSON structure specified
- Apply standardized keywords consistently
- Use foreach markers for repeated code sections
- Maintain technology-agnostic patterns
- Ensure valid JSON syntax

## Usage Instructions
To use this guide:
1. Reference this document when analyzing any folder/file
2. Follow the processing workflow for field identification
3. Apply standardized keywords and foreach markers as specified
4. Generate JSON output in the specified format
5. Return only the JSON array with no additional content

This universal guide can be applied to any technology stack or folder containing UI components. Simply follow the patterns and instructions to generate standardized field analysis JSON for any component.