import os

import pdb


def get_startup_file(shell:str):
    """Return the appropriate startup file based on the shell."""
    home_dir = os.environ["HOME"]

    if "bash" in shell:
        # Check for the existence of bash-specific startup files
        for filename in [".bash_profile", ".bash_login", ".profile"]:
            filepath = os.path.join(home_dir, filename)
            if os.path.exists(filepath):
                return filepath
        # If none of the bash-specific files exist, default to .profile
        return os.path.join(home_dir, ".profile")
    elif "zsh" in shell:
        return os.path.join(home_dir, ".zprofile")
    elif "fish" in shell:
        return os.path.join(home_dir, ".config/fish/config.fish")
    else:
        # For other shells, return None or handle accordingly
        return None



def add_to_path(directory:str, startup_file:str):
    """Add directory to PATH in the startup file."""
    if not startup_file:
        print("Unable to determine the startup file for this shell.")
        return

    # Add path modification to the startup file
    with open(startup_file, "a") as file:
        if "fish" in startup_file:
            file.write(f"\n# Include dewy compiler in PATH\nif test -d {directory}\n set -U fish_user_paths {directory} $fish_user_paths\nend\n")
        else:
            file.write(f"\n# Include dewy compiler in PATH\nif [ -d \"{directory}\" ]; then\n PATH=\"{directory}:$PATH\"\nfi\n")

    print(f"Updated {startup_file} to include {directory} in PATH.")
    print(f'Please logout and back in for changes to take effect')

def main():
    # Directory to be added to PATH
    directory = os.path.dirname(os.path.abspath(__file__))

    # Get the user's default shell
    shell = os.popen("echo $SHELL").read().strip()

    # Get the appropriate startup file for the shell
    startup_file = get_startup_file(shell)

    # Add the directory to the startup file's PATH
    add_to_path(directory, startup_file)

if __name__ == "__main__":
    main()