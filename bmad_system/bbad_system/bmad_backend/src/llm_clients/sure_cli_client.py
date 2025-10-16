    def _parse_and_execute_file_operations(self, text: str, working_dir: Optional[str]) -> bool:
        """
        INTELLIGENT FILE OPERATIONS SYSTEM
        Parses AI responses and autonomously decides what file operations to perform.
        Supports structured JSON with file_operations array and auto-detection from content.
        """
        if not working_dir:
            self._log("WARNING", "🚨 No working directory provided for file operations")
            return False
            
        try:
            import json
            
            self._log("INFO", "🧠 SureCli Intelligent CLI: Analyzing AI response for file operations...")
            self._log("INFO", f"📂 Working directory: {working_dir}")
            self._log("DEBUG", f"📝 Response text (first 300 chars): {text[:300]}...")
            
            # Clean and parse JSON response
            data = None
            t = text.strip()
            if t.startswith("```"):
                t = t.strip("`\n").split("\n", 1)[-1]
                if t.startswith("json\n"):
                    t = t[5:]
            
            try:
                data = json.loads(t)
                self._log("DEBUG", f"✅ Successfully parsed JSON: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            except json.JSONDecodeError as e:
                self._log("ERROR", f"❌ Failed to parse JSON response: {e}")
                self._log("DEBUG", f"📝 Raw response: {t[:500]}")
                return False
            
            if not isinstance(data, dict):
                self._log("ERROR", f"❌ Response is not a JSON object: {type(data)}")
                return False
            
            operations_performed = False
            total_operations = 0
            
            # Method 1: Structured file_operations array (preferred)
            if "file_operations" in data and isinstance(data["file_operations"], list):
                total_operations = len(data['file_operations'])
                self._log("INFO", f"🔧 Found structured file_operations array with {total_operations} operations")
                successful_ops = 0
                for i, operation in enumerate(data["file_operations"]):
                    if self._execute_single_file_operation(operation, working_dir, i + 1):
                        successful_ops += 1
                        operations_performed = True
                
                self._log("INFO", f"📊 Operation Summary: {successful_ops}/{total_operations} operations successful")
            
            # Method 2: Legacy files array (backward compatibility)
            elif "files" in data and isinstance(data["files"], list):
                total_operations = len(data['files'])
                self._log("INFO", f"🔄 Found legacy files array with {total_operations} items")
                successful_ops = 0
                for i, item in enumerate(data["files"]):
                    # Convert legacy format to operation format
                    operation = {
                        "filename": item.get("path") or item.get("file"),
                        "operation": "write",
                        "content": item.get("content") or item.get("body"),
                        "location": working_dir
                    }
                    if item.get("is_dir") or (operation["filename"] and operation["filename"].endswith("/")):
                        operation["operation"] = "create_dir"
                    
                    if self._execute_single_file_operation(operation, working_dir, i + 1):
                        successful_ops += 1
                        operations_performed = True
                
                self._log("INFO", f"📊 Operation Summary: {successful_ops}/{total_operations} operations successful")
            
            # Method 3: Auto-detection from top-level content keys
            else:
                self._log("INFO", "🔍 No structured operations found, auto-detecting from content keys...")
                detected_operations = self._auto_detect_file_operations(data, working_dir)
                
                if detected_operations:
                    total_operations = len(detected_operations)
                    self._log("INFO", f"🎯 Auto-detected {total_operations} file operations")
                    successful_ops = 0
                    for i, operation in enumerate(detected_operations):
                        if self._execute_single_file_operation(operation, working_dir, i + 1):
                            successful_ops += 1
                            operations_performed = True
                    
                    self._log("INFO", f"📊 Operation Summary: {successful_ops}/{total_operations} operations successful")
                else:
                    self._log("WARNING", "⚠️ No file operations detected in AI response")
                    self._log("DEBUG", f"📊 Available keys: {list(data.keys())}")
            
            if operations_performed:
                self._log("INFO", "✅ SureCli Intelligent CLI completed file operations successfully")
            else:
                self._log("WARNING", "⚠️ No file operations were performed")
            
            return operations_performed
            
        except Exception as e:
            self._log("ERROR", f"❌ SureCli Intelligent CLI error: {e}")
            import traceback
            self._log("DEBUG", f"🐛 Stack trace: {traceback.format_exc()}")
            return False