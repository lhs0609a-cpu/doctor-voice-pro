; 닥터보이스 프로 PC 실행기 설치 프로그램 (Inno Setup 6)
; build_desktop.py 가 PyInstaller 결과물을 만든 뒤 이 스크립트를 컴파일합니다.
;   ISCC /DAppVersion=1.0.0 /DSourceDir=...\dist\DoctorVoiceAutopilot /DOutputDir=...\dist installer.iss

#define AppName "닥터보이스 프로 자동 발행"
#define AppExe "DoctorVoiceAutopilot.exe"
#define AppMutex "DoctorVoiceAutopilot.Singleton"

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir AddBackslash(SourcePath) + "dist\DoctorVoiceAutopilot"
#endif
#ifndef OutputDir
  #define OutputDir AddBackslash(SourcePath) + "dist"
#endif
#define KoreanIsl AddBackslash(CompilerPath) + "Languages\Korean.isl"

[Setup]
AppId={{2F5B4A6C-8D31-4E2A-9C77-0B1C6A55E401}
AppName={#AppName}
AppVersion={#AppVersion}
VersionInfoVersion={#AppVersion}
AppPublisher=플라톤마케팅
AppPublisherURL=https://doctor-voice-pro-ghwi.vercel.app
; 관리자 권한 없이 사용자 폴더에 설치합니다 — 자동 업데이트도 UAC 없이 덮어쓸 수 있습니다.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\DoctorVoiceAutopilot
DefaultGroupName={#AppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=DoctorVoiceAutopilotSetup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
; 업데이트 설치 때 실행 중인 실행기를 알아보고 닫습니다(실행기가 같은 이름의 뮤텍스를 잡습니다).
AppMutex={#AppMutex}
CloseApplications=yes
RestartApplications=yes

[Languages]
#if FileExists(KoreanIsl)
Name: "korean"; MessagesFile: "{#KoreanIsl}"
#else
Name: "english"; MessagesFile: "compiler:Default.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 아이콘 만들기"; GroupDescription: "추가 작업:"
Name: "startupicon"; Description: "Windows 시작 시 자동으로 실행 (예약 발행을 놓치지 않습니다)"; GroupDescription: "추가 작업:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{#AppName} 제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: startupicon

[Run]
; 새로 설치할 때도, 자동 업데이트(/SILENT)로 덮어쓴 뒤에도 실행기를 다시 띄웁니다.
Filename: "{app}\{#AppExe}"; Description: "지금 실행"; Flags: nowait postinstall

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\DoctorVoicePro\updates"
