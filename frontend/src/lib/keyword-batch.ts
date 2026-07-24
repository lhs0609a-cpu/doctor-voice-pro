/**
 * 키워드 대량 생성 - 데이터 계층
 *
 * 엑셀 파싱 / 프롬프트 템플릿 / 확장 프로그램 통신을 담당한다.
 * UI(keyword-batch-manager.tsx)는 여기 있는 것만 쓰고 DOM/확장 세부는 모른다.
 */

// ============================================================
// 타입
// ============================================================
export interface KeywordRow {
  id: string;
  keyword: string;
  volume: number | null; // 검색량. 없으면 null
}

export type GenStatus = 'pending' | 'running' | 'done' | 'failed';

export interface GenItem extends KeywordRow {
  status: GenStatus;
  text?: string;
  chars?: number;
  error?: string;
}

export interface PromptTemplate {
  id: string;
  name: string;
  body: string;
  updatedAt: number;
}

// ============================================================
// 엑셀/CSV 파싱
//   서버로 올리지 않고 브라우저에서 처리한다 — 파일이 나갈 이유가 없고
//   백엔드에 pandas/openpyxl 의존성을 추가할 필요도 없다.
// ============================================================

/** 헤더 이름으로 키워드/검색량 열을 찾는다. 못 찾으면 1·2열로 가정한다. */
function pickColumns(header: unknown[]): { kw: number; vol: number } {
  const norm = header.map((h) => String(h ?? '').replace(/\s/g, '').toLowerCase());
  const kwPat = /키워드|검색어|keyword|query/;
  const volPat = /검색량|조회수|volume|count|검색수/;
  let kw = norm.findIndex((h) => kwPat.test(h));
  let vol = norm.findIndex((h) => volPat.test(h));
  if (kw < 0) kw = 0;
  if (vol < 0) vol = kw === 0 ? 1 : 0;
  return { kw, vol };
}

function toNumber(v: unknown): number | null {
  if (v === null || v === undefined || v === '') return null;
  // "1,200" / "1200회" 같은 표기도 받아준다
  const n = Number(String(v).replace(/[^0-9.-]/g, ''));
  return Number.isFinite(n) ? n : null;
}

/**
 * 엑셀(.xlsx/.xls) 또는 CSV 를 KeywordRow[] 로 변환.
 * xlsx 라이브러리는 파일을 고를 때만 필요하므로 동적 import 로 초기 번들에서 뺀다.
 */
export async function parseKeywordFile(file: File): Promise<KeywordRow[]> {
  const XLSX = await import('xlsx');
  const buf = await file.arrayBuffer();
  const wb = XLSX.read(buf, { type: 'array' });
  const sheet = wb.Sheets[wb.SheetNames[0]];
  if (!sheet) throw new Error('시트를 읽지 못했습니다.');

  const rows = XLSX.utils.sheet_to_json<unknown[]>(sheet, { header: 1, blankrows: false });
  if (!rows.length) throw new Error('빈 파일입니다.');

  // 첫 행이 헤더인지 판단: 두 열 다 숫자가 아니면 헤더로 본다
  const first = rows[0] || [];
  const looksLikeHeader = first.some((c) => typeof c === 'string' && /[가-힣a-z]/i.test(String(c)));
  const { kw, vol } = looksLikeHeader ? pickColumns(first) : { kw: 0, vol: 1 };
  const body = looksLikeHeader ? rows.slice(1) : rows;

  const seen = new Set<string>();
  const out: KeywordRow[] = [];
  body.forEach((r, i) => {
    const keyword = String(r?.[kw] ?? '').trim();
    if (!keyword) return;
    if (seen.has(keyword)) return; // 중복 키워드는 한 번만
    seen.add(keyword);
    out.push({ id: `kw-${Date.now()}-${i}`, keyword, volume: toNumber(r?.[vol]) });
  });
  if (!out.length) throw new Error('키워드를 하나도 찾지 못했습니다. 첫 열에 키워드가 있는지 확인하세요.');
  return out;
}

/** 검색량 내림차순. 검색량 없는 행은 뒤로. */
export function sortByVolume(rows: KeywordRow[]): KeywordRow[] {
  return [...rows].sort((a, b) => (b.volume ?? -1) - (a.volume ?? -1));
}

// ============================================================
// 프롬프트 템플릿
// ============================================================
const TPL_KEY = 'doctorvoice-prompt-templates';

export const DEFAULT_TEMPLATE: PromptTemplate = {
  id: 'default',
  name: '기본 블로그 글',
  updatedAt: 0,
  body: `당신은 네이버 블로그 상위노출 전문 작가입니다.
아래 키워드로 블로그 글을 작성해 주세요.

키워드: {{키워드}}

작성 규칙:
- 첫 줄에 제목만 쓰고, 한 줄 띄운 뒤 본문을 시작하세요.
- 본문은 1500자 이상, 소제목을 3~5개 사용하세요.
- 키워드를 본문에 자연스럽게 5~8회 포함하세요.
- 실제 경험담처럼 구체적으로 쓰고, 광고 문구는 넣지 마세요.
- 마크다운 기호(#, **)는 쓰지 말고 일반 텍스트로만 작성하세요.

모바일 가독성 (독자의 대부분이 휴대폰으로 봅니다):
- 한 줄에 한 문장만 쓰고, 두 문장마다 빈 줄을 넣으세요.
- 한 문장은 60자를 넘기지 마세요. 길어지면 두 문장으로 나누세요.
- 여러 문장을 한 문단에 몰아 쓰지 마세요.`,
};

export function loadTemplates(): PromptTemplate[] {
  try {
    const raw = localStorage.getItem(TPL_KEY);
    const list = raw ? (JSON.parse(raw) as PromptTemplate[]) : [];
    return list.length ? list : [DEFAULT_TEMPLATE];
  } catch {
    return [DEFAULT_TEMPLATE];
  }
}

export function saveTemplates(list: PromptTemplate[]) {
  try {
    localStorage.setItem(TPL_KEY, JSON.stringify(list));
  } catch {
    // 템플릿은 몇 KB라 한도에 걸릴 일이 사실상 없다. 걸리면 조용히 넘어간다.
  }
}

/** 로컬이 기본 템플릿 하나(무편집)뿐이면 '올릴 게 없음'으로 본다. */
function isJustDefault(list: PromptTemplate[]): boolean {
  return (
    list.length === 1 &&
    list[0].id === DEFAULT_TEMPLATE.id &&
    list[0].body === DEFAULT_TEMPLATE.body &&
    list[0].name === DEFAULT_TEMPLATE.name
  );
}

/**
 * 서버(계정)에서 템플릿을 불러온다.
 * - 비로그인/오프라인/서버오류 → null (호출부는 로컬 값을 유지한다)
 * - 성공 시 로컬 캐시도 갱신한다
 */
export async function fetchTemplatesFromServer(): Promise<PromptTemplate[] | null> {
  try {
    const { keywordBatchAPI } = await import('@/lib/api');
    const list = await keywordBatchAPI.getTemplates();
    if (!Array.isArray(list)) return null;
    const mapped: PromptTemplate[] = list.map((t) => ({
      id: t.id,
      name: t.name,
      body: t.body,
      updatedAt: t.updatedAt || 0,
    }));
    try {
      if (mapped.length) localStorage.setItem(TPL_KEY, JSON.stringify(mapped));
    } catch {
      /* 캐시 실패는 무시 */
    }
    return mapped;
  } catch {
    return null;
  }
}

/** 서버에 템플릿 전체를 저장한다. 실패해도 로컬 캐시는 이미 남아 있다. */
export async function saveTemplatesToServer(list: PromptTemplate[]): Promise<boolean> {
  try {
    const { keywordBatchAPI } = await import('@/lib/api');
    await keywordBatchAPI.saveTemplates(
      list.map((t) => ({ id: t.id, name: t.name, body: t.body, updatedAt: t.updatedAt || 0 })),
    );
    return true;
  } catch {
    return false;
  }
}

/**
 * 최초 동기화: 서버 목록을 받아 화면에 쓸 목록을 정한다.
 * - 서버에 값이 있으면 그걸 쓴다(다른 기기에서 만든 것 포함)
 * - 서버가 비었는데 로컬에 편집한 게 있으면 → 로컬을 서버로 올리고 로컬을 쓴다(1회 이관)
 * 반환: 화면에 반영할 목록. 서버 접근 불가면 null(로컬 유지).
 */
export async function syncTemplates(local: PromptTemplate[]): Promise<PromptTemplate[] | null> {
  const server = await fetchTemplatesFromServer();
  if (server === null) return null; // 비로그인/오프라인 → 로컬 유지
  if (server.length > 0) return server;
  // 서버가 비어 있음 → 로컬에 올릴 게 있으면 이관
  if (!isJustDefault(local)) {
    await saveTemplatesToServer(local);
  }
  return local;
}

/** {{키워드}} / {{keyword}} 치환. 변수를 추가하려면 vars 에 넣으면 된다. */
export function renderPrompt(body: string, vars: Record<string, string>): string {
  return body.replace(/\{\{\s*([^}]+?)\s*\}\}/g, (m, name: string) => {
    const key = String(name).trim();
    return vars[key] ?? vars[key.toLowerCase()] ?? m;
  });
}

// ============================================================
// 확장 프로그램 통신
// ============================================================
export interface GenOptions {
  newChatEvery: number;
  reloadEvery: number;
  minChars: number;
  retries: number;
  tempChat: boolean;
}

export const DEFAULT_GEN_OPTIONS: GenOptions = {
  newChatEvery: 1,
  reloadEvery: 20,
  minChars: 800,
  retries: 1,
  tempChat: true,
};

function extensionId(): string | null {
  try {
    return localStorage.getItem('doctorvoice-extension-id');
  } catch {
    return null;
  }
}

type ChromeRuntime = {
  runtime?: { sendMessage: (id: string, msg: unknown, cb: (r: unknown) => void) => void };
};

function sendToExtension<T = unknown>(msg: unknown): Promise<T> {
  return new Promise((resolve, reject) => {
    const id = extensionId();
    const chromeApi = (window as unknown as { chrome?: ChromeRuntime }).chrome;
    if (!id || !chromeApi?.runtime?.sendMessage) {
      reject(new Error('확장 프로그램이 연결되지 않았습니다. 설치 후 페이지를 새로고침하세요.'));
      return;
    }
    try {
      chromeApi.runtime.sendMessage(id, msg, (res: unknown) => {
        if (!res) {
          reject(new Error('확장 프로그램이 응답하지 않습니다.'));
          return;
        }
        resolve(res as T);
      });
    } catch (e) {
      reject(e instanceof Error ? e : new Error('확장 호출 실패'));
    }
  });
}

export async function startGeneration(
  items: { id: string; keyword: string; prompt: string }[],
  options: GenOptions,
): Promise<{ success: boolean; accepted?: number; error?: string }> {
  return sendToExtension({ action: 'SUBMIT_GEN_BATCH', items, options });
}

export async function cancelGeneration(): Promise<{ success: boolean }> {
  return sendToExtension({ action: 'CANCEL_GEN_BATCH' });
}

export interface GenResultEvent {
  id: string;
  ok: boolean;
  keyword: string;
  text: string;
  chars: number;
  error: string;
  done: boolean;
  fatal: boolean;
}

/** 확장이 보내는 건별 결과를 구독한다. 해제 함수를 돌려준다. */
export function onGenResult(handler: (r: GenResultEvent) => void): () => void {
  const listener = (e: Event) => handler((e as CustomEvent<GenResultEvent>).detail);
  window.addEventListener('doctorvoice-gen-result', listener);
  return () => window.removeEventListener('doctorvoice-gen-result', listener);
}

// ============================================================
// 결과 후처리
// ============================================================
/**
 * 생성된 글을 "저장된 글"(/dashboard/saved)에 넣는다.
 *
 * 저장된 글은 백엔드가 아니라 localStorage 'saved-posts' 배열이다.
 * 백엔드 POST /posts 는 original_content 를 받아 AI 생성을 태우는 경로라
 * '이미 완성된 제목+본문'을 넣을 수 없다 — 그래서 화면이 실제로 읽는 곳에 직접 쓴다.
 *
 * 읽는 쪽(saved-posts-manager, editor)은 suggested_titles[0] / generated_content 를
 * 우선 보므로 그 형태로 넣어야 이후 저장·편집에서 형식이 어긋나지 않는다.
 */
const SAVED_KEY = 'saved-posts';

export interface SavedPostLike {
  id: string;
  savedAt: string;
  suggested_titles: string[];
  generated_content: string;
  seo_keywords: string[];
  original_content: string;
}

export function appendSavedPosts(
  entries: { keyword: string; title: string; content: string }[],
): number {
  if (!entries.length) return 0;
  let list: SavedPostLike[] = [];
  try {
    const raw = localStorage.getItem(SAVED_KEY);
    list = raw ? (JSON.parse(raw) as SavedPostLike[]) : [];
    if (!Array.isArray(list)) list = [];
  } catch {
    list = [];
  }

  const stamp = Date.now();
  const fresh: SavedPostLike[] = entries.map((e, i) => ({
    // Date.now() 만 쓰면 같은 밀리초에 여러 건이 들어올 때 id 가 겹친다
    id: `post-${stamp}-${i}-${Math.random().toString(36).slice(2, 7)}`,
    savedAt: new Date().toISOString(),
    suggested_titles: [e.title],
    generated_content: e.content,
    // 준비함이 tags 로 그대로 쓴다. 키워드를 넣어두면 해시태그가 자동으로 잡힌다.
    seo_keywords: e.keyword ? [e.keyword] : [],
    original_content: '',
  }));

  // 최신이 위로 오도록 앞에 붙인다(create 페이지와 동일한 동작)
  const next = [...fresh, ...list];
  try {
    localStorage.setItem(SAVED_KEY, JSON.stringify(next));
  } catch {
    // 글이 수백 건 쌓이면 localStorage 5MB 한도에 걸릴 수 있다.
    // 저장 실패를 성공으로 보고하면 글이 조용히 사라지므로 반드시 알린다.
    throw new Error('저장 공간이 부족합니다. 저장된 글에서 오래된 글을 정리해 주세요.');
  }
  // 같은 탭의 '저장된 글' 화면이 즉시 갱신되도록 신호를 보낸다.
  // (storage 이벤트는 '다른 탭'에서만 발생하므로 같은 탭용 커스텀 이벤트가 필요하다)
  try {
    window.dispatchEvent(new Event('saved-posts-changed'));
  } catch {
    /* SSR 등 window 없음 */
  }
  return fresh.length;
}

// ============================================================
// 모바일 가독성 정리
// ============================================================
// 네이버 블로그 방문자의 대부분은 모바일이다. AI 가 뱉는 통짜 문단(한 문단에
// 대여섯 문장)은 모바일에서 10줄이 넘는 글덩어리가 되어 그냥 안 읽힌다.
// 규칙: 한 줄 = 한 문장, 두 문장마다 빈 줄. 긴 문장은 쉼표에서 한 번 더 끊는다.
const SENTENCES_PER_GROUP = 2;
const MOBILE_LINE_MAX = 60; // 모바일 한 화면 폭 ≈ 25~30자 → 두 줄 정도가 상한

/** 소제목·목록처럼 '문장이 아닌' 줄은 손대지 않고 그대로 한 줄로 둔다.
 *  길이만으로 판단하면 안 된다 — 짧은 문장까지 소제목 취급해 한 문장씩 흩어지고,
 *  이미 정리된 글을 한 번 더 돌렸을 때 결과가 달라진다(멱등성 깨짐). */
function isStructuralLine(line: string): boolean {
  if (/^([-•·*]|\d+[.)]|[①-⑳])\s/.test(line)) return true; // 목록·번호 항목
  if (/[.,!?…]$/.test(line)) return false; // 문장/절 부호로 끝나면 본문이다(쉼표=이미 나눈 줄)
  return line.length <= 45;
}

function splitSentences(line: string): string[] {
  // 문장부호 '뒤에 공백이 올 때'만 끊는다 → '2.5억' 같은 소수점은 안전하다.
  return line
    .split(/(?<=[.!?…])\s+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/** 너무 긴 문장은 '가운데 근처(30~70%)' 쉼표에서 나눈다.
 *  아무 쉼표에서나 끊으면 짧은 토막 한 줄 + 여전히 긴 한 줄이 나와 오히려 나빠진다.
 *  마땅한 자리가 없으면 문장을 그대로 둔다(원문 훼손 금지). */
function splitLongSentence(s: string): string[] {
  const n = s.length;
  if (n <= MOBILE_LINE_MAX) return [s];
  const mid = n / 2;
  let cut = -1;
  for (let i = 0; i < n; i++) {
    if (s[i] !== ',') continue;
    if (i < n * 0.3 || i > n * 0.7) continue;
    if (cut < 0 || Math.abs(i - mid) < Math.abs(cut - mid)) cut = i;
  }
  if (cut < 0) return [s];
  return [s.slice(0, cut + 1).trim(), ...splitLongSentence(s.slice(cut + 1).trim())];
}

/** 본문을 모바일에서 읽히는 형태로 재배치한다. 원문 단어는 하나도 바꾸지 않는다. */
export function reflowForMobile(body: string): string {
  const src = (body || '').replace(/\r\n/g, '\n').trim();
  if (!src) return '';
  const out: string[] = []; // 이 단위들 사이에 빈 줄이 들어간다
  let buf: string[] = []; // 아직 묶이지 않은 문장

  const flush = () => {
    while (buf.length) out.push(buf.splice(0, SENTENCES_PER_GROUP).join('\n'));
  };

  for (const para of src.split(/\n{2,}/)) {
    for (const rawLine of para.split('\n')) {
      const line = rawLine.trim();
      if (!line) continue;
      if (isStructuralLine(line)) {
        flush(); // 소제목 앞에서 묶음을 끊는다
        out.push(line);
        continue;
      }
      for (const s of splitSentences(line)) buf.push(...splitLongSentence(s));
    }
    flush(); // 원문 단락 경계는 그대로 살린다
  }
  flush();
  return out.join('\n\n');
}

/** 첫 줄을 제목, 나머지를 본문으로 나눈다. 저장된 글 형식과 맞춘다. */
export function splitTitleBody(text: string): { title: string; content: string } {
  const lines = (text || '').split('\n');
  let i = 0;
  while (i < lines.length && !lines[i].trim()) i++;
  const rawTitle = (lines[i] || '').trim();
  // 혹시 마크다운 제목이나 "제목:" 접두가 붙어 오면 벗겨낸다
  const title = rawTitle.replace(/^#+\s*/, '').replace(/^제목\s*[:：]\s*/, '').trim();
  const content = lines.slice(i + 1).join('\n').trim();
  return { title, content: reflowForMobile(content || rawTitle) };
}
