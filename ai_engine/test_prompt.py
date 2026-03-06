from langchain_core.prompts import ChatPromptTemplate
import yaml

with open("prompts/system/reviewer.yaml", "r") as f:
    config = yaml.safe_load(f)

template = config['template']
try:
    prompt = ChatPromptTemplate.from_template(template)
    
    # Simulate user config injection
    user_vars = {"user_risk_config": "Some config with {rule_name} inside?"} 
    # Try with curly braces in value
    
    prompt = prompt.partial(**user_vars)
    
    print("Prompt loaded and partialed successfully.")
    print("Input variables:", prompt.input_variables)
    
    # Simulate invocation
    out = prompt.format(
        strategy_proposal="prop",
        market_volatility="vol",
        computed_metrics="met",
        account_balance="bal"
    )
    print("Formatted successfully.")
    
except Exception as e:
    print("Error:", e)
