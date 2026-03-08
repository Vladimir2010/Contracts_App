; Inno Setup Script

#define MyAppName "Contracts App Pro"
#define MyAppVersion "1.0.9"
#define MyAppPublisher "Vladimir2010"
#define MyAppURL "https://vladi-ivanov.eu"
#define MyAppExeName "ContractsAppPro.exe"

[Setup]
AppId={{623FE323-3C83-40EE-B92E-0FD44ECC4287}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; Install to Local AppData so the app can freely create /data/ and /Generated/ without requiring Admin rights.
DefaultDirName={localappdata}\{#MyAppName}
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
OutputDir=C:\Users\Dell\PycharmProjects\Contracts_App\Installer
OutputBaseFilename=Contracts App Installer
SetupIconFile=C:\Users\Dell\PycharmProjects\Contracts_App\Contracts_App_Pro\resources\vladpos_logo.ico
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "bulgarian"; MessagesFile: "compiler:Languages\Bulgarian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Distribute the final built standalone executable
Source: "C:\Users\Dell\PycharmProjects\Contracts_App\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent shellexec
