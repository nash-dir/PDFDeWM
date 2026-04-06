#!/usr/bin/env python3
"""Build a portable PDFDeWM release bundle using Python Embeddable.

This script:
  1. Downloads the official Python embeddable zip from python.org
  2. Extracts it and enables site-packages (via ._pth edit)
  3. Installs tkinter (Tcl/Tk) from a full Python installation
  4. Installs pip, then installs runtime dependencies
  5. Copies application source files into app/
  6. Compiles the C launcher (gcc -mwindows)
  7. Packages everything into a distributable zip

Usage (from project root):
    python scripts/build_release.py [--python-version 3.12.8] [--arch amd64]

Designed to run in GitHub Actions on windows-latest.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────

PYTHON_VERSION = "3.12.8"
ARCH = "amd64"

PYTHON_FTP = "https://www.python.org/ftp/python"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

# Files to copy into app/
APP_FILES = [
    "GUI.py",
    "cli.py",
    "core.py",
    "editor.py",
    "identifier.py",
    "models.py",
    "utils.py",
    "__init__.py",
]

# Runtime dependencies (must match pyproject.toml [project.dependencies])
RUNTIME_DEPS = [
    "PyMuPDF>=1.24,<2.0",
    "Pillow>=10.0,<12.0",
    "sv_ttk>=2.0",
    "tkinterdnd2>=0.3.0",
]


def download(url: str, dest: Path) -> Path:
    """Download a URL to a local file."""
    print(f"  Downloading {url} ...")
    urllib.request.urlretrieve(url, str(dest))
    return dest


def main():
    parser = argparse.ArgumentParser(description="Build PDFDeWM portable release.")
    parser.add_argument("--python-version", default=PYTHON_VERSION)
    parser.add_argument("--arch", default=ARCH, choices=["amd64", "win32"])
    parser.add_argument("--output-dir", default="dist", help="Output directory for the zip.")
    parser.add_argument("--skip-compile", action="store_true", help="Skip C launcher compilation.")
    parser.add_argument(
        "--tkinter-source", default=None,
        help="Path to a full Python installation to copy tkinter/Tcl/Tk from. "
             "If not provided, the script will install Python temporarily.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    build_dir = project_root / "build" / "release"
    dist_dir = project_root / args.output_dir

    py_ver = args.python_version
    py_ver_short = "".join(py_ver.split(".")[:2])  # "3.12.8" → "312"
    embed_zip_name = f"python-{py_ver}-embed-{args.arch}.zip"
    embed_url = f"{PYTHON_FTP}/{py_ver}/{embed_zip_name}"

    print(f"=== PDFDeWM Release Builder ===")
    print(f"Python: {py_ver} ({args.arch})")
    print(f"Build dir: {build_dir}")
    print(f"Steps: 7")
    print()

    # ── Clean previous build ──
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True)
    dist_dir.mkdir(parents=True, exist_ok=True)

    python_dir = build_dir / "python"
    app_dir = build_dir / "app"

    # ══════════════════════════════════════════════════════════════
    # Step 1: Download and extract Python Embeddable
    # ══════════════════════════════════════════════════════════════
    print("[1/7] Downloading Python Embeddable...")
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = download(embed_url, Path(tmp) / embed_zip_name)
        print(f"  Extracting to {python_dir} ...")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(python_dir)

    # ── Enable site-packages in _pth file ──
    pth_file = python_dir / f"python{py_ver_short}._pth"
    if pth_file.exists():
        original = pth_file.read_text(encoding="utf-8")
        # Uncomment 'import site' and add Lib/site-packages
        patched = original.replace("#import site", "import site")
        if "import site" not in patched:
            patched += "\nimport site\n"
        # Add app directory to path
        patched += f"\n..\\app\n"
        pth_file.write_text(patched, encoding="utf-8")
        print(f"  Patched {pth_file.name}: enabled site-packages + app path.")
    else:
        print(f"  WARNING: {pth_file.name} not found!")

    # ══════════════════════════════════════════════════════════════
    # Step 2: Install tkinter (Tcl/Tk) from full Python
    # ══════════════════════════════════════════════════════════════
    print("[2/7] Installing tkinter (Tcl/Tk)...")

    tkinter_source = None
    tkinter_installed_here = False

    if args.tkinter_source and Path(args.tkinter_source).exists():
        tkinter_source = Path(args.tkinter_source)
        print(f"  Using pre-installed Python at: {tkinter_source}")
    else:
        # Download and install full Python to a temp location
        full_installer_url = f"{PYTHON_FTP}/{py_ver}/python-{py_ver}-{args.arch}.exe"
        tkinter_source = build_dir / "_python_full"
        print(f"  Downloading full Python installer for tkinter...")
        with tempfile.TemporaryDirectory() as tmp:
            installer_path = download(full_installer_url, Path(tmp) / f"python-{py_ver}-{args.arch}.exe")
            print(f"  Installing to temp location: {tkinter_source} ...")
            subprocess.run(
                [
                    str(installer_path), "/quiet",
                    f"TargetDir={tkinter_source}",
                    "Include_pip=0", "Include_doc=0", "Include_test=0",
                    "Include_dev=0", "Include_launcher=0", "InstallAllUsers=0",
                    "Include_tcltk=1",
                ],
                check=True,
            )
        tkinter_installed_here = True

    # Copy tkinter package (pure Python)
    tkinter_lib_src = tkinter_source / "Lib" / "tkinter"
    tkinter_lib_dst = python_dir / "Lib" / "tkinter"
    if tkinter_lib_src.exists():
        shutil.copytree(tkinter_lib_src, tkinter_lib_dst, dirs_exist_ok=True)
        print(f"  Copied Lib/tkinter/ ({len(list(tkinter_lib_dst.rglob('*.py')))} files)")
    else:
        print(f"  WARNING: {tkinter_lib_src} not found!")

    # Copy _tkinter.pyd (C extension)
    tkinter_pyd_src = tkinter_source / "DLLs" / "_tkinter.pyd"
    if tkinter_pyd_src.exists():
        shutil.copy2(tkinter_pyd_src, python_dir / "_tkinter.pyd")
        print(f"  Copied _tkinter.pyd")
    else:
        print(f"  WARNING: _tkinter.pyd not found!")

    # Copy Tcl/Tk DLLs (tcl86t.dll, tk86t.dll, zlib1.dll)
    for dll_name in ("tcl86t.dll", "tk86t.dll", "zlib1.dll"):
        dll_src = tkinter_source / "DLLs" / dll_name
        if dll_src.exists():
            shutil.copy2(dll_src, python_dir / dll_name)
            print(f"  Copied {dll_name}")

    # Copy tcl/ runtime data directory
    tcl_src = tkinter_source / "tcl"
    tcl_dst = python_dir / "tcl"
    if tcl_src.exists():
        shutil.copytree(tcl_src, tcl_dst, dirs_exist_ok=True)
        print(f"  Copied tcl/ runtime data")
    else:
        print(f"  WARNING: tcl/ directory not found!")

    # Update _pth to include Lib/ for tkinter
    if pth_file.exists():
        pth_content = pth_file.read_text(encoding="utf-8")
        if "Lib" not in pth_content:
            pth_content += "\nLib\n"
            pth_file.write_text(pth_content, encoding="utf-8")
            print(f"  Patched {pth_file.name}: added Lib/ to path.")

    # Clean up temp Python installation
    if tkinter_installed_here and tkinter_source.exists():
        print(f"  Cleaning up temp Python installation...")
        # Uninstall via the installer to be clean
        full_installer_url = f"{PYTHON_FTP}/{py_ver}/python-{py_ver}-{args.arch}.exe"
        with tempfile.TemporaryDirectory() as tmp:
            installer_path = download(full_installer_url, Path(tmp) / f"python-{py_ver}-{args.arch}.exe")
            subprocess.run(
                [str(installer_path), "/quiet", "/uninstall"],
                check=False,
            )
        if tkinter_source.exists():
            shutil.rmtree(tkinter_source, ignore_errors=True)
        print(f"  Temp Python removed.")

    # ══════════════════════════════════════════════════════════════
    # Step 3: Install pip and dependencies
    # ══════════════════════════════════════════════════════════════
    print("[3/7] Installing pip and dependencies...")
    python_exe = python_dir / "python.exe"

    with tempfile.TemporaryDirectory() as tmp:
        get_pip = download(GET_PIP_URL, Path(tmp) / "get-pip.py")
        subprocess.run(
            [str(python_exe), str(get_pip), "--no-warn-script-location"],
            check=True,
        )

    # Install runtime deps into the embedded site-packages
    for dep in RUNTIME_DEPS:
        print(f"  Installing {dep} ...")
        subprocess.run(
            [str(python_exe), "-m", "pip", "install", dep,
             "--no-warn-script-location", "--quiet"],
            check=True,
        )

    # Remove pip/setuptools after installation (they're not needed at runtime)
    print("  Removing pip/setuptools (not needed at runtime)...")
    subprocess.run(
        [str(python_exe), "-m", "pip", "uninstall", "pip", "setuptools", "-y", "--quiet"],
        check=False,  # OK if this fails
    )

    # ══════════════════════════════════════════════════════════════
    # Step 4: Copy application files
    # ══════════════════════════════════════════════════════════════
    print("[4/7] Copying application files...")
    app_dir.mkdir(parents=True, exist_ok=True)

    for filename in APP_FILES:
        src = project_root / filename
        if src.exists():
            shutil.copy2(src, app_dir / filename)
            print(f"  {filename}")
        else:
            print(f"  WARNING: {filename} not found in project root!")

    # Copy license
    for name in ("license.txt", "LICENSE", "LICENSE.txt"):
        lic = project_root / name
        if lic.exists():
            shutil.copy2(lic, build_dir / lic.name)
            break

    # Copy README
    readme_src = project_root / "README.md"
    if readme_src.exists():
        shutil.copy2(readme_src, build_dir / "README.md")

    # ══════════════════════════════════════════════════════════════
    # Step 4: Compile C launcher
    # ══════════════════════════════════════════════════════════════
    launcher_src = project_root / "launcher" / "launcher.c"
    launcher_exe = build_dir / "PDFDeWM.exe"
    launcher_bat = project_root / "launcher" / "PDFDeWM.bat"
    compiled = False

    if args.skip_compile:
        print("[5/7] Skipping launcher compilation (--skip-compile).")
    elif not launcher_src.exists():
        print(f"[5/7] WARNING: {launcher_src} not found, skipping compilation.")
    else:
        print("[5/7] Compiling C launcher...")
        # Check for icon resource
        icon_rc = project_root / "launcher" / "icon.rc"
        icon_obj = build_dir / "icon.o"

        compile_cmd = ["gcc", "-mwindows", "-O2"]

        if icon_rc.exists():
            # Compile resource file for icon
            subprocess.run(
                ["windres", str(icon_rc), "-o", str(icon_obj)],
                check=True,
            )
            compile_cmd.extend([str(icon_obj)])

        compile_cmd.extend(["-o", str(launcher_exe), str(launcher_src)])
        try:
            subprocess.run(compile_cmd, check=True)
            compiled = True
            print(f"  Built {launcher_exe.name}")
        except FileNotFoundError:
            print("  WARNING: gcc not found, skipping C compilation.")

    # Always include .bat launcher as fallback
    if launcher_bat.exists():
        shutil.copy2(launcher_bat, build_dir / "PDFDeWM.bat")
        if not compiled:
            print(f"  Included PDFDeWM.bat as launcher fallback.")

    # ══════════════════════════════════════════════════════════════
    # Step 6: Strip unnecessary files to reduce size
    # ══════════════════════════════════════════════════════════════
    print("[6/7] Stripping unnecessary files...")
    strip_patterns = [
        "**/__pycache__",
        "**/*.pyc",
        "**/test",
        "**/tests",
    ]
    for pattern in strip_patterns:
        for p in build_dir.glob(pattern):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.is_file():
                p.unlink(missing_ok=True)

    # ══════════════════════════════════════════════════════════════
    # Step 7: Create distribution zip
    # ══════════════════════════════════════════════════════════════
    print("[7/7] Creating distribution zip...")

    # Read version from __init__.py
    version = "dev"
    init_file = app_dir / "__init__.py"
    if init_file.exists():
        for line in init_file.read_text().splitlines():
            if "__version__" in line:
                version = line.split("=")[1].strip().strip('"').strip("'")
                break

    zip_name = f"PDFDeWM-v{version}-win-{args.arch}"
    zip_path = dist_dir / f"{zip_name}.zip"

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for file_path in sorted(build_dir.rglob("*")):
            if file_path.is_file():
                arcname = f"{zip_name}/{file_path.relative_to(build_dir)}"
                zf.write(file_path, arcname)

    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
    print()
    print(f"=== Build Complete ===")
    print(f"Output: {zip_path}")
    print(f"Size:   {zip_size_mb:.1f} MB")
    print(f"Contents:")
    print(f"  {zip_name}/PDFDeWM.exe      (launcher)")
    print(f"  {zip_name}/python/           (Python {py_ver} embeddable)")
    print(f"  {zip_name}/app/              (application source)")
    print()


if __name__ == "__main__":
    main()
