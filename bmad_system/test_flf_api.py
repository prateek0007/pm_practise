import requests
import json

# Test the FLF workflow by making API calls
def test_flf_workflow():
    base_url = "http://localhost:5000/api"  # Adjust this to your actual API URL
    
    try:
        # Get all workflows
        print("Fetching workflows...")
        response = requests.get(f"{base_url}/workflows")
        if response.status_code == 200:
            workflows_data = response.json()
            workflows = workflows_data.get('workflows', [])
            print(f"Found {len(workflows)} workflows:")
            
            flf_workflow = None
            for workflow in workflows:
                print(f"  - {workflow['name']} (ID: {workflow['id']})")
                if 'flf' in workflow['name'].lower():
                    flf_workflow = workflow
                    print(f"    ^ This is the FLF workflow!")
                    print(f"    Agents: {workflow['agent_sequence']}")
            
            if flf_workflow:
                print(f"\nFLF Workflow found: {flf_workflow['name']}")
                return True
            else:
                print("\nFLF Workflow not found!")
                return False
        else:
            print(f"Error fetching workflows: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Error testing FLF workflow: {e}")
        return False

if __name__ == "__main__":
    print("Testing FLF Workflow...")
    success = test_flf_workflow()
    if success:
        print("✅ FLF Workflow test passed!")
    else:
        print("❌ FLF Workflow test failed!")