# io8 Project Builder (MCP-Driven)

You orchestrate project bootstrapping using io8 MCP via non-interactive Gemini CLI commands examples are given with what io8 mcp tool to use. store outputs in clear json `.sureai/io8_mcp/responses/*.out`.

## Step 1: Create io8 Project only ONCE

### Project Name Detection
1. Run `pwd` command to get current directory path you will get output as /tmp/bmad_output/create_calculator_app_20251014_053410 so you need to take the last part as io8project name after bmad/output/ which is create_calculator_app_20251014_053410. So you need to take the whole folder name with timestamp which is with the folder name also as the project name.
2. Extract the folder name (last part of the path) - this will be your project name
3. The folder name typically follows pattern: "3words_timestamp" (e.g., "create_calculator_app_20251014_053410") So take the timestamp also these underscores also as the project name for io8 to create take full folder name as project name with timestamp which is with the folder name.
4. **CRITICAL**: Use the EXACT folder name from pwd command - DO NOT use generic names like "App"
5. **CRITICAL**: The project name is determined by the DIRECTORY NAME, not the user prompt
6. **CRITICAL**: Create the io8 project ONLY ONCE with the correct folder name taking full folder name as project name with timestamp otherwise you will get error and its wrong. Do not alter, shorten, or simplify it.
7. **CRITICAL**: NEVER use just "app" as project name dont create io8project with name as "app"
8. **CRITICAL**: ALWAYS verify the project name extracted from `pwd` command matches the actual folder name with till timestamp. Verify Name Integrity: The extracted name must include everything: the words, the underscores, and the full timestamp which is with the folder name.

### Technology Selection
1. Read non root level `.sureai/architecture_document.md` to determine if this docuement is not there ignore:
   - **Backend**: Choose from available options: springboot, nodejs, spring boot mongodb, php, python, NoTech2, Authsec_Springboot_sqlite
   - **Database**: Choose from: MySQL, Mongodb (only 2 options available in io8)
   - **Frontend**: Most likely "Angular Clarity" (check architecture document for confirmation)

### Visibility
- Set visibility as "Public" or "Private" based on project requirements

### Create Project Command - below is just an example and CREATE PROJECT ONLY ONCE RESPONSE you will get in json meaning the project is created FROM MCP SERVER BUT CREATE io8PROJECT  strictly ONLY ONCE an you will know that io8project is create with that json you will get in response from mcp server. Call mcp server only ONCE.

```
gemini yolo command passing this as prompt "process_user_prompt(userPrompt='create io8 project with project name \"[PROJECT_NAME_FROM_PWD]\", visibility \"[PUBLIC_OR_PRIVATE]\", backend \"[BACKEND_FROM_ARCHITECTURE]\", database \"[DATABASE_FROM_ARCHITECTURE]\", and frontend \"[FRONTEND_FROM_ARCHITECTURE]\"')"
```

Just after io8 project creation Save the complete response in clear json format to `.sureai/io8_mcp/responses/create_project.out`
If this file already exists that means io8project has been created check its content if its json with backend id project id module id that means project its already created no need to create another project. So first check this file.

**CRITICAL**: Create the io8project only once not twice & with same name as full folder name ONLY.
**CRITICAL**: Before creating any project, ALWAYS check if `.sureai/io8_mcp/responses/create_project.out` exists and contains valid project data.
**CRITICAL**: If project already exists, skip creation and proceed to Step 2.

## Step 2: Build App only ONCE

### Extract Project ID
1. Read `.sureai/io8_mcp/responses/create_project.out` (JSON format)
2. Extract `projectResp.id` value for the `projectId` parameter
3. Keep `majorId` as `1` and `minorId` as `0` ONLY

Below is an example of build app command to run - BUILD ONLY ONCE as you will get response in json from mcp server meaning build app is called once no need to call build app again:
```
gemini yolo command passing this prompt "build_app(projectId='[PROJECT_ID_FROM_PROJECT_RESPONSE]', majorId='1', minorId='0')"
```

Save response in clear JSON format to `.sureai/io8_mcp/responses/build_app.out`

AFTER BUILD APP IS DONE WAIT EXACTLY  FOR 30 SECONDS BEFORE DOING GIT PULL if you dont wait for atleast 30 seconds then you will find remote likely empty so it takes time to get the code in remote after build app step is done.


## Step 3: Git Pull

Extract IDS from project response
1. Read `.sureai/io8_mcp/responses/create_project.out` (JSON format)
2. Extract `projectResp.gitea_url` value for doing the gitpull of this repo

Then Do through terminal commands WITHOUT ANY MCP:
git init
git pull projectResp.gitea_url

IF REMOTE IS EMPTY THEN RE PULL AGAINA FTER 5 SECONDS UNTIL THE CODE IS PULLED SUCCESSFULLY.

in responses after git pull is successful write in responses folder git pull successful in a file


## Step 4: Create Wireframe

### Extract IDs from Project Response
1. Read `.sureai/io8_mcp/responses/create_project.out` (JSON format)
2. Extract `backendResp.id` value for backendId parameter
3. Extract `moduleResp.id` value for moduleId parameter
4. Also give a appropriate standard package name based on the user's prompt don't include any spaces or special characters in the package name,  you can use underscores instead of spaces.

Below is the command example for create wireframe but this needs to be created based on user prompt specifically.
```
gemini yolo command with this as prompt "create_wireframe_raw(moduleId='[MODULE_ID_FROM_PROJECT_RESPONSE]', backendId='[BACKEND_ID_FROM_PROJECT_RESPONSE]', jsonString='{\"
     wireframeName\":\"[WIREFRAME_NAME_BASED_ON_USER_PROMPT]\",\"packageName\":\"[PACKAGE_NAME_BASED_ON_USER_PROMPT]\",\"fields\":[{\"name\":\"[FIELD_NAME_1]\",\"type\":\"
     [FIELD_TYPE_1]\"},{\"name\":\"[FIELD_NAME_2]\",\"type\":\"[FIELD_TYPE_2]\"}]}')"


  Explanation of Each Part

   * `moduleId='50652'`: Extracted from the moduleResp.id in your create_project.out file.
   * `backendId='2681'`: Extracted from the backendResp.id in your create_project.out file.
   * `jsonString`: This is the core of the wireframe definition.
       * `\"wireframeName\":\"Note\"`: A logical name for the main entity in a note-taking app.
       * `\"packageName\":\"com.simple_notes_taking\"`: A standard Java package name derived from the project name.
       * `\"fields\":[...]`: The fields for a note.
           * {\"name\":\"title\",\"type\":\"text\"}: A field for the note's title.
           * {\"name\":\"content\",\"type\":\"textarea\"}: A field for the note's main content, using textarea for multi-line text.


**Note**: The above is just an example. Create wireframe fields based on the actual user prompt requirements. Use appropriate field types like: text, email, number, date, boolean, etc.

Save response in clear JSON format to `.sureai/io8_mcp/responses/create_wireframe.out`
