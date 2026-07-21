========================================
닥터보이스 프로 확장 프로그램 · 자동 업데이트 설치
========================================

이 방법으로 설치하면 "한 번만" 설치하고, 이후 새 버전은
크롬이 알아서 자동으로 업데이트합니다. (더 이상 다운로드/재등록 불필요)

■ 준비: 기존에 "개발자 모드"로 불러온 확장이 있다면 먼저 제거하세요.
   chrome://extensions → 기존 닥터보이스 확장 → "삭제"

■ [가장 쉬운 방법] 원클릭 설치 (권장):
   1) doctorvoice-auto-update-install.bat 을 더블클릭
   2) "예"(관리자 승인) 클릭 → 자동으로 정책이 등록됩니다
   3) 안내에 따라 크롬 재시작 (파일이 물어보면 Y)
   * 아래 수동 레지스트리 과정을 몰라도 이 파일 하나로 끝납니다.

■ [수동 방법] 레지스트리 직접 병합 (위 방법이 막힐 때):
   1) doctorvoice-auto-update.reg 파일을 우클릭 → "관리자 권한으로 실행"
      (또는 더블클릭 → 사용자 계정 컨트롤 "예" → 레지스트리 병합 "예")
   2) 크롬을 완전히 종료합니다. (모든 크롬 창 닫기)
      확실히 하려면 작업관리자에서 chrome.exe 모두 종료.
   3) 크롬을 다시 실행합니다.
   4) chrome://extensions 에 "닥터보이스 프로"가 자동으로 설치되어 있습니다.
      (상단에 "조직에서 관리하는 브라우저" 표시가 뜰 수 있음 - 정상입니다)

■ 이후:
   - 새 버전이 나오면 크롬이 몇 시간 내 자동으로 업데이트합니다.
   - 즉시 확인하려면: chrome://extensions → 우상단 "개발자 모드" ON →
     "업데이트" 버튼 클릭.

■ 제거하려면:
   regedit → HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Google\Chrome\
   ExtensionInstallForcelist 에서 해당 값 삭제 후 크롬 재시작.

확장 ID: cdmgfoemncdnoigiolpgaaompcmlfcpk
자동업데이트 주소: https://doctor-voice-pro-ghwi.vercel.app/extension/updates.xml
