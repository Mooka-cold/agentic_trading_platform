import yaml
from pathlib import Path
from langchain.prompts import ChatPromptTemplate

class PromptRegistry:
    def __init__(self, prompt_dir="prompts"):
        # Base path relative to ai_engine root
        self.base_path = Path(__file__).parent.parent / prompt_dir
        self._cache = {}

    def get(self, name: str) -> ChatPromptTemplate:
        """
        Load a prompt by name (e.g., 'strategist/generation')
        """
        if name in self._cache:
            return self._cache[name]
            
        file_path = self.base_path / f"{name}.yaml"
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
            
        with open(file_path, 'r') as f:
            config = yaml.safe_load(f)
            
        # Basic parsing, can be extended to support more complex configs
        if '_type' in config and config['_type'] == 'prompt':
            prompt = ChatPromptTemplate.from_template(config['template'])
            self._cache[name] = prompt
            return prompt
        
        raise ValueError(f"Invalid prompt config in {name}")

# Global registry instance
registry = PromptRegistry()
