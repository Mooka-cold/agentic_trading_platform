import yaml
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any

class PromptRegistry:
    def __init__(self, prompt_dir="prompts"):
        # Base path relative to ai_engine root
        self.base_path = Path(__file__).parent.parent / prompt_dir
        self._cache = {}

    def get_agent_prompt(self, agent_name: str, user_variant: str = "default") -> ChatPromptTemplate:
        """
        Loads a system prompt and injects user configuration.
        """
        cache_key = f"{agent_name}:{user_variant}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 1. Load System Prompt
        system_path = self.base_path / "system" / f"{agent_name}.yaml"
        if not system_path.exists():
            raise FileNotFoundError(f"System prompt not found: {system_path}")

        with open(system_path, 'r') as f:
            system_config = yaml.safe_load(f)
            
        if '_type' not in system_config or system_config['_type'] != 'prompt':
             raise ValueError(f"Invalid prompt config in {system_path}")

        system_template = system_config['template']
        prompt = ChatPromptTemplate.from_template(system_template)
        
        # 2. Load User Config
        user_path = self.base_path / "user" / f"{agent_name}_{user_variant}.yaml"
        user_vars = {}
        
        if user_path.exists():
            with open(user_path, 'r') as f:
                user_yaml = yaml.safe_load(f)
                if user_yaml:
                    # Convention: Prefix user keys with 'user_' to match system prompt variables
                    for key, value in user_yaml.items():
                        user_vars[f"user_{key}"] = value
        else:
            # Fallback: empty strings for user vars if file missing
            pass

        # 3. Partial Application
        if user_vars:
            prompt = prompt.partial(**user_vars)

        self._cache[cache_key] = prompt
        return prompt

    def get_user_config(self, agent_name: str, user_variant: str = "default") -> Dict[str, Any]:
        """
        Returns the raw user configuration dict.
        """
        user_path = self.base_path / "user" / f"{agent_name}_{user_variant}.yaml"
        if user_path.exists():
             with open(user_path, 'r') as f:
                return yaml.safe_load(f) or {}
        return {}

    def update_user_config(self, agent_name: str, config: Dict[str, Any], user_variant: str = "default"):
        """
        Updates the user configuration file.
        """
        user_path = self.base_path / "user" / f"{agent_name}_{user_variant}.yaml"
        with open(user_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        # Invalidate cache
        cache_key = f"{agent_name}:{user_variant}"
        if cache_key in self._cache:
            del self._cache[cache_key]

# Global registry instance
registry = PromptRegistry()
