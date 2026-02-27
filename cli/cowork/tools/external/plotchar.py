"""
📈 Plotchart Tools
Implementations for generating charts using matplotlib and seaborn.
"""

import json
import uuid
import os
import io
from .utils import _env

try:
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns
except ImportError:
    pd, plt, sns = None, None, None

def plotchar(chart_type: str, data: str, x_key: str, y_key: str, output_path: str = "", title: str = "") -> str:
    """Generate a chart from data and save it as an image."""
    if not all([pd, plt, sns]):
        return "Error: Required libraries (pandas, matplotlib, seaborn) are not installed. Run `pip install pandas matplotlib seaborn`."

    try:
        # Prevent interactive plots from blocking
        plt.switch_backend('Agg')
        
        # Parse data
        if isinstance(data, str):
            try:
                parsed_data = json.loads(data)
            except json.JSONDecodeError:
                return "Error: data must be a valid JSON list of dictionaries."
        else:
            parsed_data = data

        if not isinstance(parsed_data, list) or not all(isinstance(item, dict) for item in parsed_data):
            return "Error: data must be a list of dictionaries."

        df = pd.DataFrame(parsed_data)

        if x_key not in df.columns:
            return f"Error: x_key '{x_key}' not found in data."
        
        if y_key in df.columns and chart_type != "pie":
            # Clean up strings like "12.5°C" or "10%" to allow plotting mixed data types
            # We use a regex to keep only numbers, dots, and minus signs.
            try:
                # First try direct conversion
                df[y_key] = pd.to_numeric(df[y_key], errors='coerce')
                # If everything is NaN, it might be due to units, try regex cleaning
                if df[y_key].isna().all() and not parsed_data[0].get(y_key) is None:
                     df[y_key] = pd.to_numeric(df[y_key].astype(str).str.replace(r'[^0-9.-]', '', regex=True), errors='coerce')
            except Exception:
                pass

        # Setup plot style
        sns.set_theme(style="whitegrid")
        plt.figure(figsize=(10, 6))

        if chart_type == "bar":
            sns.barplot(data=df, x=x_key, y=y_key)
        elif chart_type == "line":
            sns.lineplot(data=df, x=x_key, y=y_key, marker="o")
        elif chart_type == "scatter":
            sns.scatterplot(data=df, x=x_key, y=y_key)
        elif chart_type == "box":
            sns.boxplot(data=df, x=x_key, y=y_key)
        elif chart_type == "pie":
            if y_key in df.columns:
                plt.pie(df[y_key], labels=df[x_key], autopct='%1.1f%%', startangle=140)
            else:
                counts = df[x_key].value_counts()
                plt.pie(counts, labels=counts.index, autopct='%1.1f%%', startangle=140)
        else:
             return f"Error: Unsupported chart_type '{chart_type}'. Supported types: bar, line, scatter, box, pie."

        if title:
            plt.title(title)
        else:
            plt.title(f"{chart_type.capitalize()} Chart")
            
        if chart_type != "pie":
            plt.xticks(rotation=45, ha='right')
            
        plt.tight_layout()

        if not output_path:
            output_path = f"chart_{uuid.uuid4().hex[:8]}.png"

        # If not an absolute path, save it in the current workspace artifacts directory
        if not os.path.isabs(output_path):
            try:
                from ...workspace import workspace_manager
                session_id = os.getenv("COWORK_SESSION_ID")
                active_session = None
                
                if session_id:
                    active_session = workspace_manager.get_by_session_id(session_id)
                
                if not active_session:
                    sessions = workspace_manager.list_all()
                    if sessions:
                        active_session = workspace_manager.load(sessions[0]["slug"])
                
                if active_session:
                    output_path = str(active_session.artifacts_path / os.path.basename(output_path))
            except Exception:
                pass

        # Ensure output directory exists if provided
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        abs_path = os.path.abspath(output_path)
        rel_path = output_path
        
        # Try to make it relative to the workspace for cleaner AI reporting
        try:
            from ...workspace import workspace_manager
            session_id = os.getenv("COWORK_SESSION_ID")
            active_session = None
            if session_id:
                active_session = workspace_manager.get_by_session_id(session_id)
            if active_session:
                workspace_root = active_session.root_path
                if abs_path.startswith(str(workspace_root)):
                    rel_path = os.path.relpath(abs_path, workspace_root)
        except Exception:
            pass

        return f"✅ Chart generated successfully. Saved to: {rel_path} (Full path: {abs_path})"

    except Exception as e:
        if plt: plt.close()
        return f"Chart generation failed: {e}"

TOOLS = [
    {
        "category": "DATA_AND_UTILITY",
        "type": "function",
        "function": {
            "name": "plotchar",
            "description": "Generate a chart (bar, line, scatter, pie, box) from JSON data and save it as an image.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chart_type": {"type": "string", "description": "Type of chart to generate: bar, line, scatter, box, pie"},
                    "data": {"type": "string", "description": "JSON string containing a list of dictionaries. Example: '[{\"name\": \"A\", \"value\": 10}, {\"name\": \"B\", \"value\": 20}]'"},
                    "x_key": {"type": "string", "description": "The key in the dictionary to use for the X-axis (or labels for pie)."},
                    "y_key": {"type": "string", "description": "The key in the dictionary to use for the Y-axis (or values for pie)."},
                    "title": {"type": "string", "description": "Optional title for the chart."},
                    "output_path": {"type": "string", "description": "Optional file path to save the chart (e.g., 'my_chart.png'). Defaults to a generated filename."}
                },
                "required": ["chart_type", "data", "x_key", "y_key"],
            },
        },
    }
]
