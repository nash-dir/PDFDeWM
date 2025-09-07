# PDFDeWM - PDF Watermark Remover

## Overview

PDF Watermark Remover is a desktop GUI application designed to easily remove image-based watermarks from PDF files.

This program intelligently identifies images that appear commonly across multiple pages as watermarks. It then presents these candidates to the user as thumbnails for visual confirmation.

## Key Features

* **Intuitive GUI**: Built with Tkinter for a simple and effective user experience.
* **Intelligent Watermark Detection**: Automatically identifies potential watermarks based on repetition.
* **Visual Confirmation**: Allows users to visually inspect and select which candidates to remove.
* **Flexible File Handling**: Supports processing single files, multiple files, or all PDFs in a folder.
* **Safe Operation**: Creates new files with watermarks removed, leaving the original files untouched.

## Requirements & Installation

To run this application, you need Python 3. The required libraries are listed in the project's configuration and can be installed easily.

1.  **Clone the Repository**
    ```
    git clone [https://github.com/nash-dir/PDFDeWM.git](https://github.com/nash-dir/PDFDeWM.git)
    cd PDFDeWM
    ```

2.  **Install Dependencies**
    The simplest way to install all required libraries is to use `pip` with the local project files. This command reads the `pyproject.toml` file and installs everything needed.
    ```
    pip install .
    ```

## How to Use

1.  **Launch the Application**
    Run the following command in your terminal from the project's root directory:
    ```
    python GUI.py
    ```

2.  **Add Files & Set Options**
    * Click **"Add Files"** or **"Add Folder"**.
    * Click **"Browse"** to select an Output folder. If Output path is not designated, results will be saved to Input path.
    * Designate **"Outfut Suffix"** to concatenate after original filename. Leaving it blank would result in Output filename being identical to input file. 
    * Check **"Copy unprocessed files"** in order to have unprocessed files in selected batch be copied to Output directory.
    * Check **"Overwrite existing files"** to have existing files in result directory overwritten. If not checked, program will skip file if 'filename_suffix' already exists in Output directory.
    * **Be extra precautious if "Outfut Suffix" is blank, and "Overwrite existing files" is checked. It will make original input files be overwritten irreversibly.**

3.  **Scan for Watermarks**
    * Click **"Scan Selected Files"**. The application will analyze the files and display potential watermarks.
    * Adjust **"Scan Threshold"** to set threshold for watermark detection. **Lower Threshold** means that an image object that appears in lesser pages are more likely to be detected as watermark. 

4.  **Select and Remove**
    * Uncheck any images you do not want to remove.
    * Click **"Run Watermark Removal"**.

## Project Structure

* `GUI.py`: Manages the user interface (UI) and user events.
* `core.py`: Orchestrates the scanning and removal workflow.
* `identifier.py`: Contains the logic for finding watermark candidates.
* `editor.py`: Handles the low-level modification and saving of PDF files.

## License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**.

This is a "copyleft" license, chosen because this project depends on libraries like **PyMuPDF (AGPL)**. This means that if you use or modify this project's source code and distribute your modified version, you are required to make your source code available under the same GPLv3 license.

For commercial use cases where GPL compliance is not feasible, a commercial license for the underlying **MuPDF** library can be purchased from [Artifex Software, Inc.](https://artifex.com/licensing/).