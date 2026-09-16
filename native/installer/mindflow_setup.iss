; MIND-FLOW Native Desktop Installer Script (Inno Setup 6+)
; Compiles a single-file installer for Windows 10/11 x64.
;
; Author: ChaChan26 <minhharry2006@gmail.com>
; Copyright (c) 2026 ChaChan26. All rights reserved.

#define MyAppName "MIND-FLOW"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "ChaChan26"
#define MyAppURL "https://github.com/ChaChan26/MIND"
#define MyAppExeName "MIND-FLOW.exe"

[Setup]
AppId={{D9B7B123-93E6-4D2A-B94E-8E95E4F2A252}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist\Installer
OutputBaseFilename=MIND-FLOW-Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Launch MIND-FLOW minimized on Windows startup"; GroupDescription: "System Integration:"; Flags: unchecked

[Files]
Source: "..\..\dist\MIND-FLOW-Native\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "MIND-FLOW"; ValueData: """{app}\{#MyAppExeName}"" --background"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
