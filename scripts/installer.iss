; X-Claw Inno Setup Script
; Build with: iscc scripts/installer.iss

#define MyAppName "X-Claw"
#define MyAppVersion "0.5.0"
#define MyAppPublisher "X-Claw"
#define MyAppURL "https://github.com/anthropics/xclaw"

[Setup]
AppId={{B9E7F2A1-3C4D-4E5F-A6B7-8C9D0E1F2A3B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\dist
OutputBaseFilename=XClaw-{#MyAppVersion}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Files]
Source: "..\build\windows\uv.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\build\windows\xclaw.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\build\windows\xclaw-setup.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\build\windows\xclaw-src\*"; DestDir: "{app}\xclaw-src"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\X-Claw Setup"; Filename: "{app}\xclaw-setup.bat"
Name: "{group}\Uninstall X-Claw"; Filename: "{uninstallexe}"

[Tasks]
Name: "addtopath"; Description: "Add X-Claw to PATH"; GroupDescription: "Additional options:"

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NeedsAddPath(ExpandConstant('{app}'))

[Run]
Filename: "{app}\xclaw-setup.bat"; Description: "Install dependencies and download models"; Flags: postinstall shellexec waituntilterminated

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\X-Claw"

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER,
    'Environment', 'Path', OrigPath)
  then begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Param + ';', ';' + OrigPath + ';') = 0;
end;
