import os


def get_startup_file(shell:str) -> str|None:
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
        print("Unable to determine the startup file for this shell.")
        return None


def get_rc_file(shell:str) -> str|None:
    """Return the appropriate rc file based on the shell."""
    home_dir = os.environ["HOME"]

    if "bash" in shell:
        return os.path.join(home_dir, ".bashrc")
    elif "zsh" in shell:
        return os.path.join(home_dir, ".zshrc")
    elif "fish" in shell:
        return os.path.join(home_dir, ".config/fish/fish.config")
    else:
        print("Unable to determine the rc file for this shell.")
        return None



def add_to_path(directory:str, startup_file:str):
    """Add directory to PATH in the startup file."""

    # Check if Dewy has already been installed in this file
    with open(startup_file, 'r') as file:
        if directory in file.read():
            print(f"Dewy has already been installed for {startup_file}.")
            return

    # Add path modification to the startup file
    with open(startup_file, "a") as file:
        if "fish" in startup_file:
            file.write(f"\n# Include dewy compiler in PATH\nif test -d {directory}\n set -U fish_user_paths {directory} $fish_user_paths\nend\n")
        else:
            file.write(f"\n# Include dewy compiler in PATH\nif [ -d \"{directory}\" ]; then\n PATH=\"{directory}:$PATH\"\nfi\n")

    print(f"Updated {startup_file} to include {directory} in PATH.")


def main():
    # Directory to be added to PATH
    directory = os.path.dirname(os.path.abspath(__file__))

    # Get the user's default shell
    shell = os.popen("echo $SHELL").read().strip()

    # Update startup file (e.g. .profile) if it exists
    startup_file = get_startup_file(shell)
    if startup_file:
        add_to_path(directory, startup_file)

    # Update rc file (e.g. .bashrc) if it exists
    rc_file = get_rc_file(shell)
    if rc_file:
        add_to_path(directory, rc_file)

    if not startup_file and not rc_file:
        print(f"Unable to update startup file or rc file. Please add {directory} to your PATH manually.")
    elif not rc_file:
        print(f'Please logout and back in for changes to take effect')
    else:
        print(f'Please source {rc_file} or open a new terminal for changes to take effect')



if __name__ == "__main__":
    main()