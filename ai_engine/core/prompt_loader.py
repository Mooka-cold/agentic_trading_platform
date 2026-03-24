import yaml
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any
from string import Formatter

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
        input_variables = system_config.get("input_variables")
        if not isinstance(input_variables, list) or not all(isinstance(v, str) for v in input_variables):
            raise ValueError(f"Invalid input_variables in {system_path}")
        template_variables = self._extract_template_variables(system_template)
        declared_variables = set(input_variables)
        if template_variables != declared_variables:
            template_only = sorted(template_variables - declared_variables)
            declared_only = sorted(declared_variables - template_variables)
            raise ValueError(
                f"Prompt variable contract mismatch in {system_path}. "
                f"template_only={template_only}, declared_only={declared_only}"
            )
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

        # 3. Partial Application
        if user_vars:
            prompt = prompt.partial(**user_vars)

        self._cache[cache_key] = prompt
        return prompt

    def _extract_template_variables(self, template: str) -> set[str]:
        variables = set()
        for _, field_name, _, _ in Formatter().parse(template):
            if field_name:
                variables.add(field_name)
        return variables

    def get_user_config(self, agent_name: str, user_variant: str = "default") -> Dict[str, Any]:
        """
        Returns the raw user configuration dict.
        """
        user_path = self.base_path / "user" / f"{agent_name}_{user_variant}.yaml"
        if user_path.exists():
             with open(user_path, 'r') as f:
                return yaml.safe_load(f) or {}
        return {}

    def get_system_prompt_template(self, agent_name: str) -> str:
        system_path = self.base_path / "system" / f"{agent_name}.yaml"
        if not system_path.exists():
            raise FileNotFoundError(f"System prompt not found: {system_path}")
        with open(system_path, 'r') as f:
            system_config = yaml.safe_load(f) or {}
        template = system_config.get("template")
        if not isinstance(template, str):
            raise ValueError(f"Invalid prompt config in {system_path}")
        return template

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
