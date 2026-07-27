!include "MUI2.nsh"

Name "Adrenalin Splitter"
OutFile "AdrenalinSplitter_Setup.exe"
InstallDir "$PROGRAMFILES64\Adrenalin Splitter"
RequestExecutionLevel admin

; Registry keys for Add/Remove Programs
!define REG_UNINSTALL "Software\Microsoft\Windows\CurrentVersion\Uninstall\AdrenalinSplitter"

; Interface Settings
!define MUI_ABORTWARNING
; !define MUI_ICON "icon.ico"
; !define MUI_UNICON "icon.ico"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; Languages
!insertmacro MUI_LANGUAGE "Russian"
!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "$INSTDIR"
  
  ; Copy all files from the PyInstaller dist folder
  File /r "dist\AdrenalinSplitter\*.*"
  
  ; Create Uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  
  ; Create Start Menu Shortcuts
  CreateDirectory "$SMPROGRAMS\Adrenalin Splitter"
  CreateShortcut "$SMPROGRAMS\Adrenalin Splitter\Adrenalin Splitter.lnk" "$INSTDIR\AdrenalinSplitter.exe"
  CreateShortcut "$SMPROGRAMS\Adrenalin Splitter\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  
  ; Create Desktop Shortcut
  CreateShortcut "$DESKTOP\Adrenalin Splitter.lnk" "$INSTDIR\AdrenalinSplitter.exe"
  
  ; Write registry keys for uninstaller
  WriteRegStr HKLM "${REG_UNINSTALL}" "DisplayName" "Adrenalin Splitter"
  WriteRegStr HKLM "${REG_UNINSTALL}" "DisplayIcon" "$\"$INSTDIR\AdrenalinSplitter.exe$\""
  WriteRegStr HKLM "${REG_UNINSTALL}" "UninstallString" "$\"$INSTDIR\Uninstall.exe$\""
  WriteRegStr HKLM "${REG_UNINSTALL}" "Publisher" "Custom Build"
  WriteRegDWORD HKLM "${REG_UNINSTALL}" "NoModify" 1
  WriteRegDWORD HKLM "${REG_UNINSTALL}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  ; Remove files and directories
  RMDir /r "$INSTDIR"
  
  ; Remove Shortcuts
  Delete "$SMPROGRAMS\Adrenalin Splitter\Adrenalin Splitter.lnk"
  Delete "$SMPROGRAMS\Adrenalin Splitter\Uninstall.lnk"
  RMDir "$SMPROGRAMS\Adrenalin Splitter"
  Delete "$DESKTOP\Adrenalin Splitter.lnk"
  
  ; Remove registry keys
  DeleteRegKey HKLM "${REG_UNINSTALL}"
  
  ; Optional: Remove auto-start registry key if it exists
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "AdrenalinSplitter"
SectionEnd
