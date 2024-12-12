import argparse
import sys

import yaml
from typing import Dict, Any, Set, Optional


def merge_yaml_files(
    primary_file: str, secondary_file: str, overwrite_keys: Optional[Set[str]] = None
) -> Dict[Any, Any]:
    """
    Merge two YAML files, updating the primary file with content from the secondary file.

    This function reads two YAML files, merges their contents, and writes the result
    back to the primary file. It allows for specific keys to be overwritten if specified.

    :param primary_file: Path to the primary YAML file (will be overwritten with merged content).
    :param secondary_file: Path to the secondary YAML file (new keys will be added).
    :param overwrite_keys: Set of keys that can be overwritten. Use dot notation for nested keys
                           (e.g., 'server.host'). Default is None (no keys can be overwritten).
    :return: The merged content of the YAML files.
    :raises yaml.YAMLError: If there is an error parsing the YAML files.
    :raises FileNotFoundError: If either of the YAML files cannot be found.
    """

    def deep_merge(dict1: Dict, dict2: Dict, current_path: str = "") -> Dict:
        """
        Recursively merge two dictionaries, preserving keys from dict1 except for overwritable keys.
        """
        merged = dict1.copy()
        for key, value in dict2.items():
            path = f"{current_path}.{key}".lstrip(".")
            if key not in merged:
                merged[key] = value
            elif isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = deep_merge(merged[key], value, path)
            elif overwrite_keys is not None and path in overwrite_keys:
                merged[key] = value

        return merged

    try:
        # Read primary YAML file
        with open(primary_file, "r") as f1:
            yaml1 = yaml.safe_load(f1) or {}

        # Read secondary YAML file
        with open(secondary_file, "r") as f2:
            yaml2 = yaml.safe_load(f2) or {}

        # Merge the YAML contents
        merged_yaml = deep_merge(yaml1, yaml2)

        # Write back to primary file
        with open(primary_file, "w") as f:
            yaml.dump(merged_yaml, f, default_flow_style=False, sort_keys=False)

        return merged_yaml

    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Error parsing YAML: {str(e)}")
    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found: {str(e)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Merge two YAML files, adding keys from secondary to primary without overwriting existing keys.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s primary.yaml secondary.yaml
  %(prog)s primary.yaml secondary.yaml --overwrite "server.host,database.password"
        """,
    )

    parser.add_argument("primary", help="Primary YAML file (will be modified)")
    parser.add_argument("secondary", help="Secondary YAML file (keys will be added to primary)")
    parser.add_argument(
        "--overwrite", help="Comma-separated list of keys that can be overwritten (using dot notation)", default=""
    )

    args = parser.parse_args()

    try:
        # Convert overwrite string to set if provided
        overwrite_keys = set(args.overwrite.split(",")) if args.overwrite else None

        # Remove empty string from set if it exists
        if overwrite_keys and "" in overwrite_keys:
            overwrite_keys.remove("")

        # Perform the merge
        merged = merge_yaml_files(args.primary, args.secondary, overwrite_keys)

        print("Merge successful!")
        if overwrite_keys:
            print(f"Allowed overwrites: {overwrite_keys}")
        print("\nMerged content:")
        print(yaml.dump(merged, default_flow_style=False, sort_keys=False))

        sys.exit(0)

    except (yaml.YAMLError, FileNotFoundError) as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        sys.exit(2)
