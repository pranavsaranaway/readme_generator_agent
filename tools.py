from smolagents import tool, CodeAgent, FinalAnswerTool, Tool
from smolagents import DuckDuckGoSearchTool
import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin
import base64
import ast
import os

search_tool = DuckDuckGoSearchTool()

@tool
def get_github_repo_link(query: str) -> str:
    """
    Search for a GitHub repository URL using DuckDuckGo based on project name or description.
    Performs a web search specifically scoped to GitHub.com domain and returns the first matching repository URL found in the search results.
    
    Args:
        query (str): The project name, description, or keywords to search for on GitHub.
                    Examples: "FastAPI", "machine learning pytorch", "react router"
    
    Returns:
        str: The GitHub repository URL (e.g., "https://github.com/owner/repo") if found,
             or "No GitHub link found." if no matching repository is discovered.
    """
    results = search_tool(query + " site:github.com")
    for result in results:
        if "github.com" in result["href"]:
            return result["href"]
    return "No GitHub link found."

@tool
def fetch_comprehensive_repo_info(github_url: str) -> str:
    """
    Retrieve comprehensive metadata and content from a GitHub repository.
    Fetches README content, package/dependency files, repository statistics, and basic repository information to provide a complete picture of the project structure and dependencies.
    
    Args:
        github_url (str): A complete GitHub repository URL in the format "https://github.com/owner/repository" or similar variations.
                         Example: "https://github.com/fastapi/fastapi"
    
    Returns:
        str: A formatted text block containing repository name, owner, description, social metrics (stars/forks), topics, homepage, license information, programming languages used, README content, and detected package files with their contents. Returns error information if the repository cannot be accessed or parsed.
    """
    if github_url.endswith("/"):
        github_url = github_url[:-1]
    
    parts = github_url.split("/")
    if len(parts) < 5:
        return "Invalid GitHub URL format"
    
    owner = parts[-2]
    repo_name = parts[-1]
    
    info = {
        "repo_name": repo_name,
        "owner": owner,
        "url": github_url,
        "readme": "",
        "package_info": {},
        "file_structure": [],
        "languages": {},
        "description": "",
        "topics": [],
        "main_files": {},
        "license": "",
        "created_at": "",
        "updated_at": "",
        "default_branch": "main"
    }
    
    # Get detailed repo info from GitHub API first
    try:
        api_url = f"https://api.github.com/repos/{owner}/{repo_name}"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            repo_data = response.json()
            info.update({
                "description": repo_data.get("description", ""),
                "topics": repo_data.get("topics", []),
                "languages": repo_data.get("language", ""),
                "stars": repo_data.get("stargazers_count", 0),
                "forks": repo_data.get("forks_count", 0),
                "license": repo_data.get("license", {}).get("name", "") if repo_data.get("license") else "",
                "created_at": repo_data.get("created_at", ""),
                "updated_at": repo_data.get("updated_at", ""),
                "default_branch": repo_data.get("default_branch", "main"),
                "homepage": repo_data.get("homepage", "")
            })
    except Exception as e:
        print(f"API fetch error: {e}")
    
    # Get languages used
    try:
        lang_url = f"https://api.github.com/repos/{owner}/{repo_name}/languages"
        response = requests.get(lang_url, timeout=5)
        if response.status_code == 200:
            info["languages"] = response.json()
    except:
        pass
    
    # Fetch README with better branch detection
    readme_files = ["README.md", "README.rst", "README.txt", "readme.md", "Readme.md"]
    for branch in [info["default_branch"], "main", "master"]:
        for readme_file in readme_files:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/{readme_file}"
            try:
                response = requests.get(raw_url, timeout=10)
                if response.status_code == 200:
                    info["readme"] = response.text[:8000]  # Increased limit
                    break
            except:
                continue
        if info["readme"]:
            break
    
    # Fetch key configuration and package files
    package_files = {
        "package.json": "npm/node.js",
        "requirements.txt": "python/pip",
        "Pipfile": "python/pipenv", 
        "pyproject.toml": "python/poetry",
        "setup.py": "python/setuptools",
        "Cargo.toml": "rust/cargo",
        "go.mod": "go/modules",
        "pom.xml": "java/maven",
        "build.gradle": "java/gradle",
        "composer.json": "php/composer",
        "Dockerfile": "docker",
        "docker-compose.yml": "docker-compose",
        "Makefile": "make",
        "CMakeLists.txt": "cmake",
        ".github/workflows/ci.yml": "github-actions",
        ".github/workflows/main.yml": "github-actions"
    }
    
    for filename, tech in package_files.items():
        for branch in [info["default_branch"], "main", "master"]:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/{filename}"
            try:
                response = requests.get(raw_url, timeout=5)
                if response.status_code == 200:
                    content = response.text[:3000]
                    info["package_info"][tech] = content
                    break
            except:
                continue
    
    # Format the comprehensive information
    result = f"""Repository Information:
Name: {info['repo_name']}
Owner: {info['owner']}
URL: {info['url']}
Description: {info['description']}
Topics: {', '.join(info['topics'])}
Homepage: {info.get('homepage', 'None')}
Stars: {info.get('stars', 'Unknown')}
Forks: {info.get('forks', 'Unknown')}
License: {info['license']}
Created: {info['created_at']}
Updated: {info['updated_at']}
Default Branch: {info['default_branch']}
Languages: {json.dumps(info['languages'], indent=2)}

Configuration/Package Files Found:
{json.dumps(info['package_info'], indent=2) if info['package_info'] else 'None found'}

Existing README Content:
{info['readme'] if info['readme'] else 'No README found'}
"""
    
    return result

@tool
def analyze_code_content(github_url: str) -> str:
    """
    Analyze actual source code files to understand the project's functionality.
    This provides concrete details about what the project actually does by examining key source files, detecting frameworks, extracting API endpoints, and identifying main functionality patterns.
    
    Args:
        github_url (str): A complete GitHub repository URL in the format "https://github.com/owner/repository".
                         Example: "https://github.com/flask/flask"
    
    Returns:
        str: A formatted analysis report containing main functionality detected, key classes/components, key functions/methods, entry points, API endpoints detected, CLI commands, and common imports/dependencies.
    """
    parts = github_url.split("/")
    owner = parts[-2]
    repo_name = parts[-1]
    
    analysis = {
        "main_functionality": [],
        "key_classes": [],
        "key_functions": [],
        "imports": [],
        "project_structure": [],
        "entry_points": [],
        "apis_endpoints": [],
        "cli_commands": []
    }
    
    try:
        # Get repository contents
        api_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents"
        response = requests.get(api_url, timeout=10)
        if response.status_code != 200:
            return "Could not access repository contents"
        
        contents = response.json()
        
        # Identify key files to analyze
        key_files = []
        for item in contents:
            if item["type"] == "file":
                name = item["name"].lower()
                # Prioritize main entry points and important files
                if name in ["main.py", "app.py", "index.js", "main.js", "server.js", "index.ts", 
                           "main.rs", "lib.rs", "main.go", "main.cpp", "main.c", "app.js"]:
                    key_files.insert(0, item)  # Prioritize these
                elif name.endswith(('.py', '.js', '.ts', '.rs', '.go', '.java', '.cpp', '.c')):
                    key_files.append(item)
        
        # Analyze up to 5 key files
        for item in key_files[:5]:
            try:
                # Get file content
                file_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/main/{item['name']}"
                file_response = requests.get(file_url, timeout=5)
                if file_response.status_code != 200:
                    file_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/master/{item['name']}"
                    file_response = requests.get(file_url, timeout=5)
                
                if file_response.status_code == 200:
                    content = file_response.text[:5000]  # Limit content size
                    
                    # Analyze Python files
                    if item['name'].endswith('.py'):
                        analysis.update(analyze_python_code(content, item['name']))
                    # Analyze JavaScript/TypeScript files
                    elif item['name'].endswith(('.js', '.ts')):
                        analysis.update(analyze_js_code(content, item['name']))
                    # Add more language analyzers as needed
                    
            except Exception as e:
                continue
    
    except Exception as e:
        return f"Could not analyze code content: {str(e)}"
    
    # Format analysis results
    result = f"""Code Analysis Results:

Main Functionality Detected:
{chr(10).join(f"- {func}" for func in analysis['main_functionality'][:10])}

Key Classes/Components:
{chr(10).join(f"- {cls}" for cls in analysis['key_classes'][:10])}

Key Functions/Methods:
{chr(10).join(f"- {func}" for func in analysis['key_functions'][:10])}

Entry Points:
{chr(10).join(f"- {entry}" for entry in analysis['entry_points'][:5])}

API Endpoints Detected:
{chr(10).join(f"- {api}" for api in analysis['apis_endpoints'][:10])}

CLI Commands:
{chr(10).join(f"- {cmd}" for cmd in analysis['cli_commands'][:5])}

Common Imports/Dependencies:
{chr(10).join(f"- {imp}" for imp in list(set(analysis['imports']))[:15])}
"""
    
    return result

@tool
def analyze_python_code(content: str, filename: str) -> dict:
    """
    Analyze Python code for specific functionality patterns.
    
    Args:
        content (str): The Python source code content to analyze
        filename (str): The name of the file being analyzed
    
    Returns:
        dict: Dictionary containing lists of detected functionality, classes, functions, etc.
    """
    analysis = {
        "main_functionality": [],
        "key_classes": [],
        "key_functions": [],
        "imports": [],
        "entry_points": [],
        "apis_endpoints": [],
        "cli_commands": []
    }
    
    try:
        # Parse imports
        import_lines = [line.strip() for line in content.split('\n') if line.strip().startswith(('import ', 'from '))]
        analysis['imports'].extend(import_lines[:10])
        
        # Look for web frameworks
        if 'flask' in content.lower():
            analysis['main_functionality'].append("Flask web application")
            # Find routes
            routes = re.findall(r'@app\.route\([\'"]([^\'"]+)[\'"]', content)
            analysis['apis_endpoints'].extend([f"GET/POST {route}" for route in routes])
        
        if 'fastapi' in content.lower():
            analysis['main_functionality'].append("FastAPI web service")
            # Find endpoints
            endpoints = re.findall(r'@app\.(get|post|put|delete)\([\'"]([^\'"]+)[\'"]', content)
            analysis['apis_endpoints'].extend([f"{method.upper()} {path}" for method, path in endpoints])
        
        if 'django' in content.lower():
            analysis['main_functionality'].append("Django web application")
        
        # Look for CLI tools
        if 'argparse' in content.lower() or 'click' in content.lower():
            analysis['main_functionality'].append("Command-line interface tool")
        
        # Look for data science/ML
        if any(lib in content.lower() for lib in ['pandas', 'numpy', 'sklearn', 'tensorflow', 'pytorch']):
            analysis['main_functionality'].append("Data science/Machine learning project")
        
        # Find class definitions
        class_matches = re.findall(r'class\s+(\w+)', content)
        analysis['key_classes'].extend(class_matches[:5])
        
        # Find function definitions
        func_matches = re.findall(r'def\s+(\w+)', content)
        analysis['key_functions'].extend(func_matches[:10])
        
        # Check for main execution
        if 'if __name__ == "__main__"' in content:
            analysis['entry_points'].append(f"{filename} (main script)")
            
    except Exception as e:
        pass
    
    return analysis

@tool
def analyze_js_code(content: str, filename: str) -> dict:
    """
    Analyze JavaScript/TypeScript code for specific functionality patterns.
    
    Args:
        content (str): The JavaScript/TypeScript source code content to analyze
        filename (str): The name of the file being analyzed
    
    Returns:
        dict: Dictionary containing lists of detected functionality, classes, functions, etc.
    """
    analysis = {
        "main_functionality": [],
        "key_classes": [],
        "key_functions": [],
        "imports": [],
        "entry_points": [],
        "apis_endpoints": [],
        "cli_commands": []
    }
    
    try:
        # Look for imports/requires
        import_lines = re.findall(r'(?:import.*from\s+[\'"][^\'"]+[\'"]|require\([\'"][^\'"]+[\'"])', content)
        analysis['imports'].extend(import_lines[:10])
        
        # Look for web frameworks
        if 'express' in content.lower():
            analysis['main_functionality'].append("Express.js web server")
            # Find routes
            routes = re.findall(r'app\.(get|post|put|delete)\([\'"]([^\'"]+)[\'"]', content)
            analysis['apis_endpoints'].extend([f"{method.upper()} {path}" for method, path in routes])
        
        if 'react' in content.lower():
            analysis['main_functionality'].append("React application")
        
        if 'vue' in content.lower():
            analysis['main_functionality'].append("Vue.js application")
        
        if 'angular' in content.lower():
            analysis['main_functionality'].append("Angular application")
        
        # Find function definitions
        func_matches = re.findall(r'(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:\([^)]*\)\s*=>|\w+))', content)
        functions = [match[0] or match[1] for match in func_matches if match[0] or match[1]]
        analysis['key_functions'].extend(functions[:10])
        
        # Find class definitions
        class_matches = re.findall(r'class\s+(\w+)', content)
        analysis['key_classes'].extend(class_matches[:5])
        
    except Exception as e:
        pass
    
    return analysis

@tool
def extract_project_features(repo_info: str, code_analysis: str) -> str:
    """
    Extract specific features and capabilities from the repository analysis.
    This creates concrete feature lists instead of generic placeholders by analyzing detected technologies, code patterns, and project structure to identify real capabilities and use cases.
    
    Args:
        repo_info (str): Formatted repository information containing name, description, owner, URL, dependencies, and existing README content from fetch_comprehensive_repo_info.
        code_analysis (str): Project structure analysis containing detected project type, key files, and directory organization from analyze_code_content.
    
    Returns:
        str: A structured report containing extracted key features, technologies used, primary use cases, and detected capabilities with specific counts of identified elements.
    """
    features = []
    technologies = []
    use_cases = []
    
    # Parse the input data
    info_lines = repo_info.lower()
    code_lines = code_analysis.lower()
    
    # Extract features based on detected technologies and code patterns
    if 'flask' in info_lines or 'flask' in code_lines:
        features.append("RESTful API endpoints")
        features.append("Web-based user interface")
        technologies.append("Flask web framework")
    
    if 'fastapi' in info_lines or 'fastapi' in code_lines:
        features.append("High-performance async API")
        features.append("Automatic API documentation (OpenAPI/Swagger)")
        features.append("Type hints and validation")
        technologies.append("FastAPI framework")
    
    if 'react' in info_lines or 'react' in code_lines:
        features.append("Interactive user interface")
        features.append("Component-based architecture")
        features.append("Single-page application (SPA)")
        technologies.append("React.js")
    
    if 'machine learning' in info_lines or any(ml in info_lines for ml in ['pandas', 'numpy', 'sklearn', 'tensorflow', 'pytorch']):
        features.append("Data preprocessing and analysis")
        features.append("Machine learning model training")
        features.append("Predictive analytics")
        use_cases.append("Data science and analytics")
    
    if 'database' in info_lines or any(db in info_lines for db in ['sqlite', 'postgresql', 'mysql', 'mongodb']):
        features.append("Data persistence and storage")
        features.append("Database operations (CRUD)")
    
    if 'docker' in info_lines:
        features.append("Containerized deployment")
        features.append("Environment consistency")
        technologies.append("Docker")
    
    if 'api' in info_lines or 'rest' in info_lines:
        features.append("API integration capabilities")
        features.append("HTTP request handling")
    
    # Extract features from code analysis
    if 'api endpoints detected' in code_lines:
        endpoints = re.findall(r'- (GET|POST|PUT|DELETE) [^\n]+', code_analysis)
        if endpoints:
            features.append(f"API endpoints: {', '.join(endpoints[:3])}")
    
    if 'cli commands' in code_lines:
        features.append("Command-line interface")
        use_cases.append("Command-line tool")
    
    # Format the extracted information
    result = f"""Extracted Project Features:

Key Features:
{chr(10).join(f"- {feature}" for feature in features[:8])}

Technologies Used:
{chr(10).join(f"- {tech}" for tech in technologies[:6])}

Primary Use Cases:
{chr(10).join(f"- {case}" for case in use_cases[:4])}

Detected Capabilities:
- {len(features)} specific features identified
- {len(technologies)} technologies detected
- {len(use_cases)} use cases identified
"""
    
    return result

@tool
def generate_smart_readme(repo_info: str, code_analysis: str, features: str) -> str:
    """
    Generate a comprehensive, specific README based on actual project analysis.
    Uses real data instead of generic placeholders to create a professional README with technology-specific installation instructions, actual API endpoints, real features, and project-specific usage examples.
    
    Args:
        repo_info (str): Formatted repository information from fetch_comprehensive_repo_info containing metadata, description, and package details.
        code_analysis (str): Code analysis results from analyze_code_content containing detected functionality and technical details.
        features (str): Extracted features and capabilities from extract_project_features containing specific project features and technologies.
    
    Returns:
        str: A complete README.md content in markdown format with sections including title, overview, installation instructions (technology-specific), usage, features, API endpoints, contributing guidelines, and contact information tailored to the specific project type and technology stack detected.
    """
    # Extract key information
    lines = repo_info.split('\n')
    repo_name = ""
    description = ""
    owner = ""
    url = ""
    topics = ""
    homepage = ""
    license_info = ""
    
    for line in lines:
        if line.startswith("Name:"):
            repo_name = line.split(":", 1)[1].strip()
        elif line.startswith("Description:"):
            description = line.split(":", 1)[1].strip()
        elif line.startswith("Owner:"):
            owner = line.split(":", 1)[1].strip()
        elif line.startswith("URL:"):
            url = line.split(":", 1)[1].strip()
        elif line.startswith("Topics:"):
            topics = line.split(":", 1)[1].strip()
        elif line.startswith("Homepage:"):
            homepage = line.split(":", 1)[1].strip()
        elif line.startswith("License:"):
            license_info = line.split(":", 1)[1].strip()
    
    # Extract project type and technologies
    project_type = "Software Project"
    if "python" in repo_info.lower():
        project_type = "Python Application"
    elif "javascript" in repo_info.lower() or "node" in repo_info.lower():
        project_type = "JavaScript/Node.js Application"
    elif "rust" in repo_info.lower():
        project_type = "Rust Application"
    elif "go" in repo_info.lower():
        project_type = "Go Application"
    
    # Build README content with specific information
    readme_content = f"""# {repo_name}

{description if description and description not in ["None", ""] else f"A {project_type.lower()} built with modern technologies."}

"""
    
    # Add badges if we have the information
    if topics and topics != "None":
        readme_content += f"**Topics:** {topics}\n\n"
    
    if homepage and homepage != "None":
        readme_content += f"🌐 **Live Demo:** [{homepage}]({homepage})\n\n"
    
    # Add overview section with extracted features
    readme_content += "## Overview\n\n"
    
    # Extract main functionality from code analysis
    main_funcs = []
    for line in code_analysis.split('\n'):
        if line.startswith("- ") and ("functionality" in line.lower() or "application" in line.lower()):
            main_funcs.append(line[2:])
    
    if main_funcs:
        readme_content += f"This {project_type.lower()} provides:\n\n"
        for func in main_funcs[:3]:
            readme_content += f"- {func}\n"
        readme_content += "\n"
    
    # Add features section with extracted features
    feature_lines = []
    for line in features.split('\n'):
        if line.startswith("- ") and line[2:].strip():
            feature_lines.append(line[2:].strip())
    
    if feature_lines:
        readme_content += "## Features\n\n"
        for feature in feature_lines[:8]:
            readme_content += f"- {feature}\n"
        readme_content += "\n"
    
    # Add API endpoints if detected
    api_endpoints = []
    for line in code_analysis.split('\n'):
        if "GET" in line or "POST" in line or "PUT" in line or "DELETE" in line:
            if line.startswith("- "):
                api_endpoints.append(line[2:])
    
    if api_endpoints:
        readme_content += "## API Endpoints\n\n"
        for endpoint in api_endpoints[:6]:
            readme_content += f"- {endpoint}\n"
        readme_content += "\n"
    
    # Add installation section based on detected technologies
    readme_content += "## Installation\n\n"
    
    if "python" in repo_info.lower():
        readme_content += """### Prerequisites
- Python 3.7 or higher
- pip package manager

### Setup
```bash
# Clone the repository
git clone """ + url + """
cd """ + repo_name + """

# Install dependencies
pip install -r requirements.txt

# Or if using poetry
poetry install
```

"""
        if "flask" in repo_info.lower() or "fastapi" in repo_info.lower():
            readme_content += """### Running the Application
```bash
# Start the server
python app.py
# or
uvicorn main:app --reload  # for FastAPI
```

"""
    elif "javascript" in repo_info.lower() or "node" in repo_info.lower():
        readme_content += """### Prerequisites
- Node.js 14 or higher
- npm or yarn

### Setup
```bash
# Clone the repository
git clone """ + url + """
cd """ + repo_name + """

# Install dependencies
npm install
# or
yarn install

# Start the application
npm start
# or
yarn start
```

"""
    else:
        readme_content += f"""```bash
# Clone the repository
git clone {url}
cd {repo_name}

# Follow project-specific installation instructions
```

"""
    
    # Add usage section
    readme_content += "## Usage\n\n"
    
    # Add CLI commands if detected
    cli_commands = []
    for line in code_analysis.split('\n'):
        if line.startswith("- ") and ("command" in line.lower() or "cli" in line.lower()):
            cli_commands.append(line[2:])
    
    if cli_commands:
        readme_content += "### Command Line Interface\n\n"
        for cmd in cli_commands[:3]:
            readme_content += f"```bash\n{cmd}\n```\n\n"
    else:
        readme_content += "[Add specific usage examples here]\n\n"
    
    # Add contributing section
    readme_content += """## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

"""
    
    # Add license section if available
    if license_info and license_info != "None":
        readme_content += f"## License\n\nThis project is licensed under the {license_info} License.\n\n"
    
    # Add contact section
    readme_content += f"""## Contact

Project Link: {url}
"""
    
    return readme_content


@tool
def finalize_readme_output(readme_content: str) -> str:
    """
    Format and return the final README content in a clean markdown code block.
    
    Args:
        readme_content (str): The README content to be formatted
        
    Returns:
        str: The formatted README content wrapped in a markdown code block
    """
    return f"```markdown\n{readme_content.strip()}\n```"