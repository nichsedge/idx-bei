# remove
# find . -type d -name '__MACOSX' -exec rm -rf {} +

import os
import nbformat

def clear_outputs_in_notebook(file_path):
    """Clears the outputs of a Jupyter notebook."""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        notebook = nbformat.read(f, as_version=4)

    # Clear outputs from all cells
    for cell in notebook.cells:
        if cell.cell_type == 'code':
            cell.outputs = []

    with open(file_path, 'w', encoding='utf-8', errors='ignore') as f:
        nbformat.write(notebook, f)

def clear_outputs_in_dir(root_dir):
    """Recursively clears outputs in all .ipynb files in a directory and subdirectories."""
    for subdir, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.ipynb'):
                file_path = os.path.join(subdir, file)
                print(f"Clearing outputs in {file_path}")
                clear_outputs_in_notebook(file_path)

if __name__ == "__main__":
    root_dir = os.getcwd()  # Start in the current working directory
    clear_outputs_in_dir(root_dir)
