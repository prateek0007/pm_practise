from src.config.timeout_config import get_agent_timeout_config
import pprint

print("io8_mcp_project config:")
config = get_agent_timeout_config('io8_mcp_project')
pprint.pprint(config)
print(f"timeout: {config.get('timeout')}")
print(f"retry_timeout: {config.get('retry_timeout')}")
print(f"overall: {config.get('overall')}")