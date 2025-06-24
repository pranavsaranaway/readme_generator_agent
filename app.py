import gradio as gr
from tools import (
    get_github_repo_link,
    fetch_comprehensive_repo_info,
    analyze_code_content,
    extract_project_features,
    generate_smart_readme,
    finalize_readme_output,
    analyze_python_code,
    analyze_js_code,
    search_tool
)
from smolagents import CodeAgent, tool, OpenAIServerModel
from dotenv import load_dotenv
import os

load_dotenv()
OPEN_API_KEY = os.getenv("OPENAI_API_KEY")

agent = CodeAgent(
    model = OpenAIServerModel(model_id="gpt-4o"),
    tools=[
        get_github_repo_link,
        fetch_comprehensive_repo_info,
        analyze_code_content,
        extract_project_features,
        generate_smart_readme,
        finalize_readme_output,
        analyze_python_code,
        analyze_js_code,
        search_tool
        
    ],
    add_base_tools=True,
    additional_authorized_imports=['pandas', 'cv2', 'numpy', 'requests', 'csv']
)

def run_agent(query):
    """
    Enhanced agent runner with better error handling and instruction clarity.
    """
    try:
        # Provide clear instructions to the agent
        enhanced_query = f"""
Please generate a comprehensive README for: {query}

Follow this workflow:
1. Find the GitHub repository if only a project name was provided
2. Fetch detailed repository information including dependencies and existing README
3. Analyze the repository structure and project type
4. Generate a professional README with appropriate sections for the detected project type
5. Format and return the final README

Make the README informative, professional, and tailored to the specific project.
"""
        
        result = agent.run(enhanced_query)
        return result
    except Exception as e:
        return f"Error generating README: {str(e)}"

# Enhanced Gradio interface
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🔎 Auto README Generator")
    gr.Markdown("Generate comprehensive, professional README files for any GitHub repository")
    gr.Markdown("###### @pranavsaranaway")
    
    with gr.Row():
        with gr.Column(scale=1):
            input_query = gr.Textbox(
                label="Enter project name or GitHub URL", 
                placeholder="e.g., 'llama.cpp repo' or 'https://github.com/owner/repo'",
                lines=2
            )
            btn = gr.Button("Generate README", variant="primary")
            
            gr.Markdown("""
            ### Tips:
            - Enter a project name (e.g., "FastAPI") to search for the repository
            - Or paste a direct GitHub URL
            - The tool will analyze the code structure and dependencies
            - Generated READMEs include installation, usage, and contribution sections
            """)
        
        with gr.Column(scale=2):
            output_readme = gr.Textbox(
                label="Generated README", 
                lines=25,
                show_copy_button=True
            )

    btn.click(fn=run_agent, inputs=input_query, outputs=output_readme)

demo.launch()