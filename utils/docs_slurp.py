import os
import shutil
import logging
import trafilatura
import glob
import zipfile
import time

# Set up logging
logging.basicConfig(filename='trafilatura.log', level=logging.WARNING)

# Define the directory path
directory = 'docs/memgpt'

# Iterate through the directory tree
for root, dirs, files in os.walk(directory, topdown=False):
    # Get a list of all HTML files in the current directory
    html_files = [f for f in files if f.endswith('.html')]

    # Iterate through the list of HTML files and move them to the 'api' level
    for html_file in html_files:
        old_file_path = os.path.join(root, html_file)
        new_file_name = f"{os.path.basename(root)}.html"
        new_file_path = os.path.join(directory, new_file_name)

        # Overwrite the file if it already exists in the destination directory
        if os.path.exists(new_file_path):
            os.remove(new_file_path)
        os.rename(old_file_path, new_file_path)

    # Delete the now empty directory, but not the root directory
    if root != directory:
        try:
            shutil.rmtree(root)
        except OSError as e:
            print(f"Error deleting directory {root}: {e}")

# Wait until all subdirectories are deleted
while next(os.walk(directory))[1]:
    time.sleep(1)

def process_directory(directory):
    # Get a list of all files in the directory
    files = os.listdir(directory)
    print(f"Found {len(files)} files in {directory}")

    # Get the name of the parent directory
    parent_dir_name = os.path.basename(os.path.normpath(directory))

    # Create a file to store all the contents
    with open(os.path.join(directory, f'{parent_dir_name}_ALL.txt'), 'w', encoding='utf-8') as all_file:
        for file in files:
            input_file = os.path.join(directory, file)
            output_file = os.path.join(directory, file + '.txt')

            try:
                # Read the HTML file
                with open(input_file, 'r', encoding='utf-8') as f:
                    html_string = f.read()

                # Extract the main content
                text = trafilatura.extract(html_string)

                # Write the extracted content to a text file
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(text)

                # Write the extracted content to the combined file
                all_file.write(text)

                print(f"Successfully processed file {file}")
                print(f"Extracted text: {text}")

            except Exception as e:
                logging.error(f'Error processing file {file}: {e}')
                print(f"Error processing file {file}: {e}")

    # Remove the individual text files
    for file in glob.glob(os.path.join(directory, '*.txt')):
        if file != os.path.join(directory, f'{parent_dir_name}_ALL.txt'):
           os.remove(file)

    # Zip all HTML files and then delete them
    with zipfile.ZipFile(os.path.join(directory, 'html_files.zip'), 'w') as zipf:
        for file in glob.glob(os.path.join(directory, '*.html')):
            zipf.write(file)
            os.remove(file)

process_directory(directory)
