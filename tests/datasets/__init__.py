import os
import importlib.util

TEST_CASES = []

# Dynamically load all test cases from python files in this directory
current_dir = os.path.dirname(__file__)
for filename in os.listdir(current_dir):
    if filename.endswith(".py") and filename != "__init__.py" and filename != "eval_data.py":
        module_name = filename[:-3]
        file_path = os.path.join(current_dir, filename)
        
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is not None and spec.loader is not None:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, 'test_cases'):
                TEST_CASES.extend(module.test_cases)
            elif hasattr(module, 'test_case'):
                TEST_CASES.append(module.test_case)
