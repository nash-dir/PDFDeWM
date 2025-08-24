# PDF Watermark Remover [Project Under Development]

## Overview

**PDF Watermark Remover** is a Graphical User Interface (GUI) application designed to easily remove image-based watermarks from PDF files.

This program automatically identifies images that appear commonly across multiple pages as watermarks. It then allows the user to visually confirm these candidates via thumbnails and selectively remove them. This ensures that only the watermarks are accurately removed while preserving important images within the document's content.

---

## Features

* **Intuitive GUI**: Provides a graphical interface that is easy to use, even for users without coding knowledge.
* **Intelligent Watermark Detection**: Automatically identifies images that appear on a majority of pages as potential watermarks.
* **Visual Confirmation and Selection**: Allows users to visually inspect detected watermark candidates as thumbnails and choose which ones to remove.
* **Flexible File Handling**: Capable of processing a single file, multiple files, or all PDF files within a specific folder at once.
* **Non-Destructive Operation**: Creates a new file with the watermark removed, leaving the original file untouched.

---

## Requirements & Installation

This program requires Python 3 and the following libraries:

* **PyMuPDF**: The core library for reading and modifying PDF files.
* **Pillow**: A library for handling image thumbnails in the GUI.

1.  **Clone Repository**
    ```bash
    git clone [https://github.com/nash-dir/PDFDeWM.git](https://github.com/nash-dir/PDFDeWM.git)
    cd PDFDeWM
    ```

2.  **Install Dependencies**
    Install the required libraries at once using the `requirements.txt` file with the following command:
    ```bash
    pip install -r requirements.txt
    ```

---

## How to Use

1.  **Run the Program**
    Start the GUI application by entering the following command in your terminal:
    ```bash
    python GUI.py
    ```

2.  **Add Files**
    * Click the `Add Files` or `Add Folder` button to add the PDF files you want to process to the list.

3.  **Specify Output Path**
    * Click the `Browse` button to select the folder where the resulting files will be saved.

4.  **Scan for Watermarks**
    * Click the `Scan Selected Files` button. The program will analyze the added files to find watermark candidates.
    * Detected candidates will be displayed as thumbnails in the central area.

5.  **Select and Remove**
    * Review the displayed thumbnails and select the checkboxes for the watermarks you wish to remove (all are selected by default).
    * Click the `Run Watermark Removal` button. New PDF files with the selected watermarks removed will be created in the specified output directory.

---

## Project Structure

This project is modularized into four main Python files based on their roles:

* `GUI.py`: The main application file responsible for the User Interface (UI) and event handling.
* `core.py`: Acts as an orchestrator, connecting the GUI to the backend processing logic. It controls the overall flow of the scan and removal processes.
* `identifier.py`: Specializes in the logic for 'finding' watermarks within PDF documents.
* `editor.py`: Handles the low-level editing functions for 'modifying and saving' the PDF documents.
