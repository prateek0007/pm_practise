#!/usr/bin/env python3
"""
Test to simulate agent execution and check if instructions are loaded correctly
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_runtime_instructions():
    """Test instructions loading during agent execution simulation"""
    
    print("Runtime Instructions Test (Agent Execution Simulation)")
    print("=" * 60)
    
    try:
        from src.agents.agent_manager import AgentManager
        from src.core.sequential_document_builder import SequentialDocumentBuilder
        from src.workflows.master_workflow import MasterWorkflow
        
        # Create instances
        agent_manager = AgentManager()
        
        # Test agent
        test_agent = "developer"
        
        print(f"\n1. Testing agent: {test_agent}")
        
        # Check what instructions are currently stored
        print("\n2. Current stored instructions:")
        stored_instructions = agent_manager.get_agent_instructions(test_agent)
        print(f"   Length: {len(stored_instructions)}")
        print(f"   Content: {stored_instructions[:100]}...")
        
        if "test instruction update for debugging" in stored_instructions:
            print("   → These are CUSTOM instructions (from our test)")
        elif "Provide detailed, actionable output" in stored_instructions:
            print("   → These are DEFAULT instructions")
        elif "CODE GENERATION PHASE" in stored_instructions:
            print("   → These are DEVELOPER default instructions")
        else:
            print("   → These are UNKNOWN instructions")
        
        # Simulate Sequential Document Builder
        print("\n3. Testing Sequential Document Builder:")
        try:
            doc_builder = SequentialDocumentBuilder()
            agent_prompt = doc_builder._get_agent_prompt(test_agent)
            agent_instructions = doc_builder._get_agent_instructions(test_agent)
            
            print(f"   Agent prompt length: {len(agent_prompt)}")
            print(f"   Agent instructions length: {len(agent_instructions)}")
            print(f"   Agent instructions content: {agent_instructions[:100]}...")
            
            if "test instruction update for debugging" in agent_instructions:
                print("   → SUCCESS: Sequential Document Builder loads CUSTOM instructions")
            else:
                print("   → FAILURE: Sequential Document Builder loads DEFAULT instructions")
                return False
                
        except Exception as e:
            print(f"   → Error testing Sequential Document Builder: {e}")
            return False
        
        # Simulate Master Workflow
        print("\n4. Testing Master Workflow:")
        try:
            # Create a mock Gemini client for testing
            class MockGeminiClient:
                def __init__(self):
                    self.last_prompt = None
                
                def generate_response(self, prompt, task_id=None):
                    self.last_prompt = prompt
                    return "Mock response"
            
            mock_client = MockGeminiClient()
            master_workflow = MasterWorkflow(agent_manager, mock_client, None)
            
            # Test the prompt creation
            full_prompt = master_workflow._create_agent_input(test_agent, "Test user prompt", "Test previous work", {}, {}, {}, [])
            
            print(f"   Full prompt length: {len(full_prompt)}")
            print(f"   Full prompt content preview: {full_prompt[:200]}...")
            
            if "test instruction update for debugging" in full_prompt:
                print("   → SUCCESS: Master Workflow includes CUSTOM instructions")
            else:
                print("   → FAILURE: Master Workflow includes DEFAULT instructions")
                return False
                
        except Exception as e:
            print(f"   → Error testing Master Workflow: {e}")
            return False
        
        # Test with a different agent that should have default instructions
        print("\n5. Testing with agent that should have default instructions:")
        test_agent2 = "tester"
        
        # Check what instructions are loaded for tester
        tester_instructions = agent_manager.get_agent_instructions(test_agent2)
        print(f"   Tester instructions length: {len(tester_instructions)}")
        print(f"   Tester instructions content: {tester_instructions[:100]}...")
        
        if "Explicitly mark any subtests" in tester_instructions:
            print("   → SUCCESS: Tester has correct DEFAULT instructions")
        else:
            print("   → FAILURE: Tester has incorrect instructions")
            return False
        
        # Test the full flow with a new instruction update
        print("\n6. Testing full flow with new instruction update:")
        new_instructions = "This is a NEW test instruction that should be sent to Gemini CLI immediately."
        success = agent_manager.update_agent_instructions(test_agent, new_instructions)
        print(f"   Update success: {success}")
        
        if success:
            # Immediately check if the new instructions are loaded
            immediate_instructions = agent_manager.get_agent_instructions(test_agent)
            print(f"   Immediate instructions: {immediate_instructions[:100]}...")
            
            if immediate_instructions == new_instructions:
                print("   → SUCCESS: New instructions are loaded immediately")
            else:
                print("   → FAILURE: New instructions are NOT loaded immediately")
                return False
            
            # Test Sequential Document Builder again
            doc_builder2 = SequentialDocumentBuilder()
            new_agent_instructions = doc_builder2._get_agent_instructions(test_agent)
            
            if new_agent_instructions == new_instructions:
                print("   → SUCCESS: Sequential Document Builder loads NEW instructions")
            else:
                print("   → FAILURE: Sequential Document Builder does NOT load NEW instructions")
                return False
        else:
            print("   → FAILURE: Update failed")
            return False
            
    except Exception as e:
        print(f"✗ Error in test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✓ Runtime test completed successfully!")
    return True

if __name__ == "__main__":
    success = test_runtime_instructions()
    if success:
        print("\n🎉 Runtime instructions are working correctly!")
        print("\n📋 Summary:")
        print("  ✓ Agent Manager loads custom instructions")
        print("  ✓ Sequential Document Builder loads custom instructions")
        print("  ✓ Master Workflow includes custom instructions")
        print("  ✓ Default instructions work for other agents")
        print("  ✓ New instructions are loaded immediately")
        print("\n🔍 If you're still seeing default instructions in Gemini CLI,")
        print("   the issue might be:")
        print("   1. Frontend not refreshing data properly")
        print("   2. Browser cache issues")
        print("   3. API timing issues")
        print("   4. Different agent being executed than expected")
    else:
        print("\n❌ Runtime instructions test failed.")
        print("\n🔧 This indicates the backend is not loading instructions correctly")
        print("   during agent execution.")
