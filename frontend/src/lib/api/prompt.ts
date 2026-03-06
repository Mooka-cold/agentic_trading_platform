const API_BASE_URL = "/api/ai_engine"; // Use Next.js rewrite proxy

export interface AgentConfigResponse {
  agent: string;
  variant: string;
  config: Record<string, any>;
}

export const PromptAPI = {
  getConfig: async (agentName: string, variant: string = "default"): Promise<AgentConfigResponse> => {
    const response = await fetch(`${API_BASE_URL}/prompts/${agentName}/config?user_variant=${variant}`);
    if (!response.ok) {
      throw new Error("Failed to fetch config");
    }
    return response.json();
  },

  updateConfig: async (agentName: string, config: Record<string, any>, variant: string = "default") => {
    const response = await fetch(`${API_BASE_URL}/prompts/${agentName}/config?user_variant=${variant}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ config }),
    });
    if (!response.ok) {
      throw new Error("Failed to update config");
    }
    return response.json();
  }
};
