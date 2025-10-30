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
* **Enhanced List Management**: Improved queue stability, including automatic cursor movement after deletion and quick file opening.
* **Extensive Keyboard Shortcuts** (New in v1.2.0).

---

## Executable Details

The executable version of PDFDeWM is built using **PyInstaller**, but intentionally **excludes the `--onefile` option** (building to a single executable file). This decision was made to **minimize the likelihood of false positives from antivirus software**, as single-file executables are frequently flagged by heuristic analysis.

---

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
    * Click **"Add Files"** ($\text{Ctrl + A}$) or **"Add Folder"** ($\text{Ctrl + Shift + A}$) to select input files.
    * Click **"Browse"** ($\text{Ctrl + S}$) to select an Output folder. If the Output path is not designated, results will be saved to the Input path.
    * Designate **"Output Suffix"** ($\text{Ctrl + Q}$ to focus) to concatenate after the original filename. Leaving it blank would result in the Output filename being identical to the input file.
    * Check **"Copy unprocessed files"** in order to have unprocessed files in the selected batch be copied to the Output directory.
    * Check **"Overwrite existing files"** to have existing files in the result directory overwritten. If not checked, the program will skip the file if 'filename\_suffix' already exists in the Output directory.
    * **Be extra precautious if "Output Suffix" is blank, and "Overwrite existing files" is checked. It will make original input files be overwritten irreversibly.**

3.  **Scan for Watermarks**
    * Click **"Scan Selected Files"** ($\text{Ctrl + D}$). The application will analyze the files and display potential watermarks.
    * Adjust **"Scan Threshold"** to set the threshold for image watermark detection. **Lower Threshold** means that an image object that appears in fewer pages is more likely to be detected as a watermark.

4.  **Select and Remove**
    * Uncheck any images you do not want to remove.
    * Click **"Run Watermark Removal"** ($\text{Ctrl + F}$).

---

## ⌨️ Keyboard Shortcuts (v1.2.0)

| Action | Shortcut | Description |
| :--- | :--- | :--- |
| **Add Files** | $\text{Ctrl + A}$ | Open file selection dialog. |
| **Add Folder** | $\text{Ctrl + Shift + A}$ | Open folder selection dialog. |
| **Browse Output Folder** | $\text{Ctrl + S}$ / $\text{Ctrl + Shift + S}$ | Open the output folder selection dialog. |
| **Scan Selected Files** | $\text{Ctrl + D}$ / $\text{Ctrl + Shift + D}$ | Start the watermark identification scan. |
| **Run Watermark Removal** | $\text{Ctrl + F}$ / $\text{Ctrl + Shift + F}$ | Start the removal process. |
| **Close Application** | $\text{Ctrl + T}$ / $\text{Ctrl + Shift + T}$ | Exit the program. |
| **Focus Output Suffix** | $\text{Ctrl + Q}$ / $\text{Ctrl + Shift + Q}$ | Move cursor to the Output Suffix field and select all text. |
| **Focus Text Keywords** | $\text{Ctrl + W}$ / $\text{Ctrl + Shift + W}$ | Move cursor to the Text Keywords field and select all text. |
| **Remove Selected File** | $\text{Delete}$ / $\text{Backspace}$ | Remove the selected file(s) from the processing list. |
| **Open Selected File** | $\text{Double-Click}$ / $\text{Enter}$ ($\text{Return}$) | Open the selected file in the system's default viewer. |

---

## Project Structure

* `GUI.py`: Manages the user interface (UI) and user events.
* `core.py`: Orchestrates the scanning and removal workflow.
* `identifier.py`: Contains the logic for finding watermark candidates.
* `editor.py`: Handles the low-level modification and saving of PDF files.
* `utils.py`: Contains helper classes for file dialogs and image utilities.

## License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**.

This is a "copyleft" license, chosen because this project depends on libraries like **PyMuPDF (AGPL)**. This means that if you use or modify this project's source code and distribute your modified version, you are required to make your source code available under the same GPLv3 license.

For commercial use cases where GPL compliance is not feasible, a commercial license for the underlying **MuPDF** library can be purchased from [Artifex Software, Inc.](https://artifex.com/licensing/).