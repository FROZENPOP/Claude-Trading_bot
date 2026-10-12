import os
import sys

print("Current directory:", os.getcwd())
print("Current sys.path:")
for i, p in enumerate(sys.path):
    print(f"  {i}: {p}")

print("\nChecking if current directory is in path...")
current_dir = os.getcwd()
if current_dir in sys.path:
    idx = sys.path.index(current_dir)
    print(f"  Yes, at index {idx}: {current_dir}")
else:
    print("  No")

print("\nChecking for Webull execution wrapper in current directory...")
local_webull_wrapper_path = os.path.join(current_dir, 'webull_execution.py')
if os.path.exists(local_webull_wrapper_path):
    print(f"  Found Webull execution wrapper (webull_execution.py) at: {local_webull_wrapper_path}")
else:
    print(f"  No Webull execution wrapper found at: {local_webull_wrapper_path}")

print("\nAdding project root to path...")
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
print(f"Project root: {project_root}")
if project_root not in sys.path:
    sys.path.append(project_root)

print("\nUpdated sys.path:")
for i, p in enumerate(sys.path):
    print(f"  {i}: {p}")

print("\nChecking for Webull execution wrapper (webull_execution.py)...")
try:
    import webull_execution
    print(f"Found Webull execution wrapper (webull_execution.py) at: {webull_execution.__file__}")
except Exception as e:
    print(f"Error importing Webull execution wrapper: {e}")