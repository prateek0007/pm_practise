    def _execute_flf_save_phase(self, task_id: str, agent_output: str, project_dir: str, previous_docs: Dict[str, str], agent_prompt: str = "") -> Dict[str, Any]:
        """Execute FLF Save phase - prepare prompt for Gemini CLI to handle field analysis"""
        try:
            logger.info(f"Executing FLF Save phase for task {task_id}")
            
            # Import and use the new FLF agent implementation
            from src.agents.flf_agent import FLFAgent
            flf_agent = FLFAgent()
            
            # Use the agent output as the user prompt
            user_prompt = agent_output
            
            # Execute the FLF agent to prepare the prompt for Gemini CLI
            result = flf_agent.execute(task_id, user_prompt)
            
            # The FLF agent already creates the required files, so we just need to return the result
            return result
            
        except Exception as e:
            logger.error(f"Error in FLF save phase: {str(e)}", exc_info=True)
            return {'status': 'error', 'error': str(e)}