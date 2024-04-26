#!/usr/bin/python3

"""
This script renames keys in a dictionary imported from the param_filter module.
It also replaces all occurrences of the old names with the new names
 in all *.py and *.md files in the current directory.
Finally, it renames the actual files on disk.
"""

import os
import param_filter

file_renames = {}

# Add lines like these to rename files
# file_renames["old_name"] = "new_name"
file_renames["00_Default_Parameters.param"] = "00_default.param"

# Iterate over the purge_dict and rename the keys to be in two-digit prefix ascending order
new_dict = {}
for i, (old_key, old_value) in enumerate(param_filter.intermediate_param_files_dict.items()):
    new_key = f"{i:02d}_{old_key.split('_', 1)[1]}"
    # Get the value associated with new_key in the file_renames dictionary.
    # If new_key is not found, it will return new_key itself as the default value,
    # effectively leaving it unchanged.
    new_key = file_renames.get(new_key, new_key)
    new_dict[new_key] = old_value
    if old_key != new_key:
        print(f"Info: Will rename {old_key} to {new_key}")

param_dirs = ['.']
# Search all *.py and *.md files in the current directory
# and replace all occurrences of the old names with the new names
for root, dirs, files in os.walk("."):
    for file in files:
        if 'params' in root.split(os.sep)[-1]:
            if root not in param_dirs:
                param_dirs.append(root)
        update_file_content = file.endswith(".py") or file.endswith(".md") or file.endswith(".json")
        if update_file_content and (root == '.' or root.split(os.sep)[-1] == 'params') and file != 'param_reorder.py':
            with open(os.path.join(root, file), "r", encoding="utf-8") as handle:
                file_content = handle.read()
            if file in ["README.md", "BLOG.md", "BLOG-discuss.md"]:
                for param_filename in param_filter.intermediate_param_files_dict:
                    if param_filename not in file_content:
                        print(
                            f"Error: The intermediate parameter file '{param_filename}' is not mentioned in the {file} file"
                        )
            for old_name, new_name in zip(param_filter.intermediate_param_files_dict.keys(), new_dict.keys()):
                file_content = file_content.replace(old_name, new_name)
            with open(os.path.join(root, file), "w", encoding="utf-8") as handle:
                handle.write(file_content)

# Rename the actual files on disk
for param_dir in param_dirs:
    for old_name, new_name in zip(param_filter.intermediate_param_files_dict.keys(), new_dict.keys()):
        old_name_path = os.path.join(param_dir, old_name)
        new_name_path = os.path.join(param_dir, new_name)
        if os.path.exists(old_name_path):
            os.rename(old_name_path, new_name_path)
        else:
            print(f"Error: Could not rename file {old_name_path}, file not found")

# Rename the actual files on disk based on file_renames
for param_dir in param_dirs:
    for old_name, new_name in file_renames.items():
        old_name_path = os.path.join(param_dir, old_name)
        new_name_path = os.path.join(param_dir, new_name)
        if os.path.exists(old_name_path):
            os.rename(old_name_path, new_name_path)
        else:
            print(f"Error: Could not rename file {old_name_path}, file not found")

# Change line endings of BLOG*.md files to CRLF
for root, dirs, files in os.walk("."):
    for file in files:
        if (file.startswith("BLOG") and file.endswith(".md")) or file == "README.md":
            file_path = os.path.join(root, file)
            with open(file_path, "rb") as handle:
                content = handle.read()
            content = content.replace(b'\n', b'\r\n')
            with open(file_path, "wb") as handle:
                handle.write(content)
