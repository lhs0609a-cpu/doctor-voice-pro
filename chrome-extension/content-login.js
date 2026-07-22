// ============================================================
// 닥터보이스 프로 - 로그인 복귀 브릿지 v15
//  미로그인 상태로 글쓰기를 열면 네이버가 로그인 페이지로 보냄.
//  사용자가 수동 로그인(세션 재사용 설계)을 마치면 → pendingJob 이 있을 때
//  글쓰기 페이지(GoBlogWrite)로 자동 복귀시켜 자동화를 재개한다.
//  실행 대상: nid.naver.com(로그인) + www.naver.com/naver.com(로그인 후 랜딩 대비)
// ============================================================
(() => {
  'use strict';
  const TAG = '[닥터보이스:login]';
  const WRITE_URL = 'https://blog.naver.com/GoBlogWrite.naver';

  // v15 규격: background.startJob 이 chrome.storage.local.pendingJob 저장
  function hasPendingJob() {
    return new Promise((resolve) => {
      try {
        chrome.storage.local.get('pendingJob', (r) => resolve(!!(r && r.pendingJob)));
      } catch (e) { resolve(false); }
    });
  }

  function notify(message) {
    if (!document.body) return;
    const el = document.createElement('div');
    el.textContent = message;
    el.style.cssText =
      'position:fixed;top:20px;right:20px;z-index:2147483647;' +
      'background:linear-gradient(135deg,#10b981,#059669);color:#fff;' +
      'padding:14px 20px;border-radius:12px;font-size:14px;font-weight:600;' +
      "box-shadow:0 8px 28px rgba(16,185,129,.4);font-family:-apple-system,'Malgun Gothic',sans-serif";
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3500);
  }

  const onLoginPage = () => location.href.includes('nid.naver.com');
  const loginFormPresent = () =>
    !!document.querySelector(
      '#frmNIDLogin, form[name="frmNIDLogin"], #id, #pw, .login_form, #login_form'
    );

  // 캡차/보안문자/신규기기 인증 화면 감지 → 자동입력 중단, 사용자 핸드오프
  const securityChallengePresent = () =>
    !!document.querySelector(
      'iframe[id^="ncaptcha-iframe"], iframe[src*="captcha"], .captcha_wrap, #captcha, .device_reg, #deviceRegForm'
    );

  // input 값을 네이티브 setter로 넣고 이벤트를 발생시킨다(폼 스크립트가 감지하도록).
  function setInputValue(el, value) {
    if (!el) return false;
    const proto = Object.getPrototypeOf(el);
    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
    if (setter) setter.call(el, value);
    else el.value = value;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
    return true;
  }

  function getCred() {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage({ action: 'GET_CRED' }, (r) => {
          if (chrome.runtime.lastError) return resolve(null);
          resolve(r && r.ok ? r.cred : null);
        });
      } catch (e) {
        resolve(null);
      }
    });
  }

  let autoLoginTried = false;
  async function tryAutoLogin() {
    if (autoLoginTried) return;
    if (!(await hasPendingJob())) return;      // 우리 작업과 무관하면 개입 안 함
    if (securityChallengePresent()) {
      notify('보안 확인이 필요합니다. 직접 완료해 주세요 — 이후 자동으로 이어집니다.');
      return;                                  // 캡차/기기인증은 핸드오프
    }
    const cred = await getCred();
    if (!cred || !cred.id || !cred.pw) return; // 저장된 계정 없으면 기존 수동 흐름 유지

    const idEl = document.querySelector('#id');
    const pwEl = document.querySelector('#pw');
    if (!idEl || !pwEl) return;                // 폼 아직 안 뜸 → 다음 폴에서 재시도

    autoLoginTried = true;
    notify('저장된 계정으로 자동 로그인합니다…');
    setInputValue(idEl, cred.id);
    setInputValue(pwEl, cred.pw);
    // 로그인 상태 유지 체크
    const keep = document.querySelector('#keep');
    if (keep && !keep.checked) {
      try { keep.click(); } catch (e) { /* noop */ }
    }
    // 제출: 보안 화면이 아직 없을 때만
    setTimeout(() => {
      if (securityChallengePresent()) {
        notify('보안 확인이 필요합니다. 직접 완료해 주세요.');
        return;
      }
      const btn = document.querySelector('#log\\.login, button[type="submit"], .btn_login');
      if (btn) btn.click();
      else {
        const form = document.querySelector('#frmNIDLogin, form[name="frmNIDLogin"]');
        if (form) form.submit();
      }
    }, 400);
  }

  let navigated = false;
  async function goWriteIfPending(reason) {
    if (navigated) return;
    if (!(await hasPendingJob())) return; // 대기 중인 작업 없으면 일반 로그인 → 개입 안 함
    navigated = true;
    console.log(TAG, '로그인 완료 감지(' + reason + ') → 글쓰기로 복귀');
    notify('로그인 완료 — 글 작성을 이어갑니다...');
    setTimeout(() => { window.location.href = WRITE_URL; }, 1000);
  }

  async function main() {
    // 로그인 페이지: 폼이 사라지거나 nid 도메인을 벗어나면 로그인 성공으로 간주
    if (onLoginPage()) {
      if (!(await hasPendingJob())) return; // 우리 작업과 무관한 로그인
      notify('네이버 로그인 후 자동으로 글 작성이 이어집니다');

      // 저장된 계정이 있으면 자동 입력·제출 시도(캡차 시 사용자 핸드오프)
      tryAutoLogin();

      const iv = setInterval(async () => {
        if (!onLoginPage() || !loginFormPresent()) {
          clearInterval(iv);
          await goWriteIfPending('form-gone');
        } else {
          // 폼이 늦게 뜨거나 첫 시도가 이르면 다시 시도(내부 플래그로 1회만 실행)
          tryAutoLogin();
        }
      }, 800);

      // SPA/리다이렉트로 DOM이 바뀌는 경우도 감시
      const obs = new MutationObserver(async () => {
        if (!loginFormPresent()) { obs.disconnect(); await goWriteIfPending('mutation'); }
      });
      if (document.body) obs.observe(document.body, { childList: true, subtree: true });
      return;
    }

    // 네이버 메인 등으로 랜딩한 경우(로그인 후 url 파라미터가 write 로 안 돌아온 케이스)
    await goWriteIfPending('landed');
  }

  if (document.readyState === 'complete' || document.readyState === 'interactive') main();
  else window.addEventListener('DOMContentLoaded', main);
})();
