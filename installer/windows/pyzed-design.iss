; Pyzed Design's Windows installer (Inno Setup 6), made by scripts/build_designer.py --installer.
;
; Like Zed's, it installs for the current user only, in %LOCALAPPDATA%\Programs\Pyzed Design,
; without administrator rights. That folder is the user's, so the app can update itself there
; (pyzed.updater swaps the folder for the new version's on restart). The build passes:
;
;   /DAppVersion=1.2.0 /DSourceDir=<the PyInstaller folder> /DOutputDir=<dist> /DOutputName=<name>
;   and /DSetupIcon=<.ico> when there is one.
;
; Self-updates replace the whole folder, keeping the uninstaller (unins000.*) in it, and the
; designer refreshes the version shown in Settings -> Apps when it starts.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "Pyzed Design"
#define AppExe "Pyzed Design.exe"

[Setup]
; Never change the AppId: Windows finds the installed copy (and its uninstaller) by it.
AppId={{8F4C2E6B-3A1D-4F7E-9B2C-5D6E7F8A9B0C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Pyzed
AppPublisherURL=https://albakore.github.io/pyzed/
AppSupportURL=https://github.com/albakore/pyzed/issues
AppUpdatesURL=https://albakore.github.io/pyzed/download/
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename={#OutputName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
ChangesAssociations=yes
CloseApplications=yes
RestartApplications=no
#ifdef SetupIcon
SetupIconFile={#SetupIcon}
#endif

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "associate"; Description: "{cm:AssocFileExtension,{#AppName},.pzform .pzcomp .pzshad .pzanim}"

[InstallDelete]
; Installing over an older version: remove its app files first. Copying over them would leave behind what the
; new version no longer has, such as the old pyzed_ui-X.Y.Z.dist-info, which then reports the old version (and
; makes the updater offer the version just installed again and again). The uninstaller (unins000.*) stays.
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\{#AppExe}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; .pzform, .pzcomp, .pzshad and .pzanim files open in Pyzed Design (per user: HKCU\Software\Classes).
Root: HKA; Subkey: "Software\Classes\.pzform"; ValueType: string; ValueName: ""; ValueData: "PyzedDesign.Form"; Flags: uninsdeletevalue; Tasks: associate
Root: HKA; Subkey: "Software\Classes\PyzedDesign.Form"; ValueType: string; ValueName: ""; ValueData: "Pyzed form"; Flags: uninsdeletekey; Tasks: associate
Root: HKA; Subkey: "Software\Classes\PyzedDesign.Form\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe},0"; Tasks: associate
Root: HKA; Subkey: "Software\Classes\PyzedDesign.Form\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: associate
Root: HKA; Subkey: "Software\Classes\.pzcomp"; ValueType: string; ValueName: ""; ValueData: "PyzedDesign.Component"; Flags: uninsdeletevalue; Tasks: associate
Root: HKA; Subkey: "Software\Classes\PyzedDesign.Component"; ValueType: string; ValueName: ""; ValueData: "Pyzed component"; Flags: uninsdeletekey; Tasks: associate
Root: HKA; Subkey: "Software\Classes\PyzedDesign.Component\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe},0"; Tasks: associate
Root: HKA; Subkey: "Software\Classes\PyzedDesign.Component\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: associate
Root: HKA; Subkey: "Software\Classes\.pzshad"; ValueType: string; ValueName: ""; ValueData: "PyzedDesign.Shader"; Flags: uninsdeletevalue; Tasks: associate
Root: HKA; Subkey: "Software\Classes\PyzedDesign.Shader"; ValueType: string; ValueName: ""; ValueData: "Pyzed shader"; Flags: uninsdeletekey; Tasks: associate
Root: HKA; Subkey: "Software\Classes\PyzedDesign.Shader\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe},0"; Tasks: associate
Root: HKA; Subkey: "Software\Classes\PyzedDesign.Shader\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: associate
Root: HKA; Subkey: "Software\Classes\.pzanim"; ValueType: string; ValueName: ""; ValueData: "PyzedDesign.Animation"; Flags: uninsdeletevalue; Tasks: associate
Root: HKA; Subkey: "Software\Classes\PyzedDesign.Animation"; ValueType: string; ValueName: ""; ValueData: "Pyzed animation library"; Flags: uninsdeletekey; Tasks: associate
Root: HKA; Subkey: "Software\Classes\PyzedDesign.Animation\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe},0"; Tasks: associate
Root: HKA; Subkey: "Software\Classes\PyzedDesign.Animation\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: associate

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
; The app runs this setup silently with /RELAUNCH=1 when it could not replace its own folder (pyzed.updater
; install_on_exit): start it again once installed.
Filename: "{app}\{#AppExe}"; Flags: nowait skipifnotsilent; Check: RelaunchAfterUpdate

[UninstallDelete]
; Self-updates replace the folder's files, so remove what the installer did not put there too.
Type: filesandordirs; Name: "{app}"

[Code]
function RelaunchAfterUpdate: Boolean;
begin
  Result := ExpandConstant('{param:relaunch|0}') = '1';
end;
