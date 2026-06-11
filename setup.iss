; Inno Setup Script for Webtoon Scripter (v3.0)

[Setup]
AppName=Webtoon Scripter
AppVersion=3.0.0
AppPublisher=woo2koon
AppPublisherURL=https://github.com/woo2koon/Webtoon-Scripter
AppSupportURL=https://github.com/woo2koon/Webtoon-Scripter
AppUpdatesURL=https://github.com/woo2koon/Webtoon-Scripter/releases
DefaultDirName={autopf}\Webtoon Scripter
DefaultGroupName=Webtoon Scripter
; 설치 파일 저장 경로 및 이름
OutputDir=dist
OutputBaseFilename=Webtoon_Scripter_v3.0.0_Setup
; 바탕화면 바로가기 아이콘 설정용 아이콘 경로
SetupIconFile=app_icon\webtoon_scripter_icon_windows.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; PyInstaller 빌드 결과물 (폴더 전체 패키징 방식)
Source: "dist\Webtoon_Scripter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Webtoon Scripter"; Filename: "{app}\Webtoon_Scripter.exe"; IconFilename: "{app}\_internal\app_icon\webtoon_scripter_icon_windows.ico"
Name: "{autodesktop}\Webtoon Scripter"; Filename: "{app}\Webtoon_Scripter.exe"; Tasks: desktopicon; IconFilename: "{app}\_internal\app_icon\webtoon_scripter_icon_windows.ico"

[Run]
Description: "{cm:LaunchProgram,Webtoon Scripter}"; Filename: "{app}\Webtoon_Scripter.exe"; Flags: nowait postinstall skipifsilent
