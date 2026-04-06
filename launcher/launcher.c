/*
 * PDFDeWM Launcher
 * 
 * A minimal Windows launcher that invokes pythonw.exe with GUI.py.
 * Compiled with: gcc -mwindows -o PDFDeWM.exe launcher.c
 * 
 * This binary does NOT embed or unpack Python — it simply calls
 * the real python.exe adjacent to it. Because python.exe is an
 * official Microsoft-signed binary from python.org, antivirus
 * software will never flag this distribution.
 *
 * Copyright (C) 2025 nash-dir — GPLv3
 */

#include <windows.h>
#include <stdio.h>

int WINAPI WinMain(
    HINSTANCE hInstance,
    HINSTANCE hPrevInstance,
    LPSTR     lpCmdLine,
    int       nCmdShow
) {
    /* ── Resolve our own directory ────────────────────────────── */
    char exeDir[MAX_PATH];
    GetModuleFileNameA(NULL, exeDir, MAX_PATH);

    /* Strip the filename to get the directory */
    char *lastSlash = strrchr(exeDir, '\\');
    if (lastSlash) *lastSlash = '\0';

    SetCurrentDirectoryA(exeDir);

    /* ── Build the command line ───────────────────────────────── */
    /*
     * Use pythonw.exe (not python.exe) to suppress the console window.
     * GUI.py lives under the app/ subdirectory.
     */
    char pythonPath[MAX_PATH];
    char scriptPath[MAX_PATH];
    char cmdLine[MAX_PATH * 3];

    snprintf(pythonPath, MAX_PATH, "%s\\python\\pythonw.exe", exeDir);
    snprintf(scriptPath, MAX_PATH, "%s\\app\\GUI.py", exeDir);

    /* Check if pythonw.exe exists */
    DWORD attr = GetFileAttributesA(pythonPath);
    if (attr == INVALID_FILE_ATTRIBUTES) {
        MessageBoxA(
            NULL,
            "Python runtime not found.\n\n"
            "Expected location: python\\pythonw.exe\n\n"
            "Please re-download PDFDeWM from the official GitHub Releases page.",
            "PDFDeWM — Error",
            MB_ICONERROR | MB_OK
        );
        return 1;
    }

    /* Check if GUI.py exists */
    attr = GetFileAttributesA(scriptPath);
    if (attr == INVALID_FILE_ATTRIBUTES) {
        MessageBoxA(
            NULL,
            "Application script not found.\n\n"
            "Expected location: app\\GUI.py\n\n"
            "Please re-download PDFDeWM from the official GitHub Releases page.",
            "PDFDeWM — Error",
            MB_ICONERROR | MB_OK
        );
        return 1;
    }

    snprintf(cmdLine, sizeof(cmdLine),
        "\"%s\" \"%s\"", pythonPath, scriptPath);

    /* ── Launch the process ───────────────────────────────────── */
    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));

    BOOL ok = CreateProcessA(
        NULL,           /* lpApplicationName — use cmdLine instead */
        cmdLine,        /* lpCommandLine */
        NULL,           /* lpProcessAttributes */
        NULL,           /* lpThreadAttributes */
        FALSE,          /* bInheritHandles */
        0,              /* dwCreationFlags */
        NULL,           /* lpEnvironment */
        exeDir,         /* lpCurrentDirectory */
        &si,
        &pi
    );

    if (!ok) {
        char errMsg[512];
        snprintf(errMsg, sizeof(errMsg),
            "Failed to launch Python.\n\n"
            "Command: %s\n"
            "Error code: %lu",
            cmdLine, GetLastError());
        MessageBoxA(NULL, errMsg, "PDFDeWM — Error", MB_ICONERROR | MB_OK);
        return 1;
    }

    /* Don't wait — exit immediately so the launcher disappears */
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);

    return 0;
}
