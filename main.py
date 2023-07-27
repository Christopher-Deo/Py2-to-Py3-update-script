import os
import subprocess
import re
import shutil
import logging
import pkg_resources
from packaging.markers import interpret


def setup_logging():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger(__name__)
    return logger


def scan_python_version(source_directory):
    try:
        version_info = subprocess.check_output(
            ["python", "--version"], cwd=source_directory, stderr=subprocess.STDOUT)
        python_version = re.search(
            r"Python (\d+\.\d+\.\d+)", version_info.decode()).group(1)
        return python_version
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Failed to determine Python version: {e.output.decode().strip()}")


def scan_dependencies():
    dependency_tree = subprocess.check_output(
        ['pipdeptree', '-w']).decode('utf-8')
    dependencies = re.findall(r'([a-zA-Z0-9_-]+)==([0-9.]+)', dependency_tree)
    return dependencies


def is_compatible(package_name, version):
    package_string = f"{package_name}=={version}"
    marker = pkg_resources.packaging.markers.default_environment()
    return interpret(marker, package_string)


def dry_run_2to3(source_directory):
    proposed_changes = {}
    for root, _, files in os.walk(source_directory):
        for file_name in files:
            if file_name.endswith(".py"):
                file_path = os.path.join(root, file_name)
                try:
                    proposed_output = subprocess.check_output(
                        ['2to3', '-n', file_path])
                    proposed_changes[file_path] = proposed_output.decode()
                except subprocess.CalledProcessError as e:
                    logger.error(
                        f"Error during dry run for {file_path}: {e.output.decode().strip()}")
    with open("changes_for_update.log", "w") as log_file:
        for file_path, changes in proposed_changes.items():
            log_file.write(f"Changes for {file_path}:\n{changes}\n")


def update_to_python_3_9(source_directory, destination_directory):
    shutil.copytree(source_directory, destination_directory)
    subprocess.run(['2to3', '--write', '--nobackups', destination_directory])


def main(source_directory, destination_directory, logger):
    # Step 1: Scan current Python version
    try:
        current_python_version = scan_python_version(source_directory)
        logger.info(f"Detected Python version: {current_python_version}")
    except RuntimeError as e:
        logger.error(str(e))
        return

    # Step 2: Check compatibility with Python 3.9
    if current_python_version.startswith("3.9"):
        logger.info("Python version is already 3.9.x. No need to update.")
    else:
        try:
            dependencies = scan_dependencies()
            incompatible_dependencies = []

            for name, version in dependencies:
                if not is_compatible(name, version):
                    incompatible_dependencies.append((name, version))

            if incompatible_dependencies:
                logger.info(
                    "The following dependencies are not compatible with Python 3.9:")
                with open("compatibility-concerns.log", "w") as logfile:
                    for name, version in incompatible_dependencies:
                        logfile.write(f"{name}=={version}\n")
                        logger.info(f"{name}=={version}")
                logger.info(
                    "Please review the compatibility-concerns.log file for more details.")
            else:
                logger.info(
                    "All dependencies are compatible with Python 3.9. Proceeding with the update.")
                try:
                    dry_run_2to3(source_directory)
                    logger.info(
                        "Dry run completed. Proposed changes logged in 'changes_for_update.log'.")

                    user_input = input(
                        "Enter 'Y' to proceed with the update or 'N' to cancel: ").strip().lower()
                    if user_input == 'y':
                        update_to_python_3_9(
                            source_directory, destination_directory)
                        logger.info("Update to Python 3.9 successful.")
                    elif user_input == 'n':
                        logger.info("Update canceled.")
                    else:
                        logger.error("Invalid input. Update canceled.")
                except Exception as e:
                    logger.error(f"Error during update: {str(e)}")
        except Exception as e:
            logger.error(f"Error during dependency scan: {str(e)}")


if __name__ == "__main__":
    source_directory = "path_to_source_directory"
    destination_directory = "path_to_destination_directory"

    if not os.path.exists(source_directory):
        print(f"Source directory '{source_directory}' not found.")
    elif not os.path.exists(destination_directory):
        print(f"Destination directory '{destination_directory}' not found.")
    else:
        logger = setup_logging()
        main(source_directory, destination_directory, logger)
