// 예약 준비함의 무거운 payload(사진 base64)를 IndexedDB 에 보관한다.
//
// localStorage 는 한도가 약 5MB 인데 글 한 건이 사진 10장 기준 4~5MB(base64 는 원본 대비 +33%)라
// 두 건만 담아도 QuotaExceededError 가 났다 — 담긴 것처럼 보이지만 새로고침하면 전부 사라졌다.
// 또한 사진을 React state 에 그대로 들고 있으면 100건 = 400MB+ 라 탭이 메모리로 죽는다.
// → 준비함 목록(제목/예약시각 등 수십 바이트)만 localStorage + state 에 두고,
//   사진은 여기에 넣어뒀다가 확장이 그 글을 처리하기 직전에 한 건씩 꺼낸다.

const DB_NAME = 'doctorvoice'
const DB_VERSION = 1
const STORE = 'prepared-payloads'

export interface PreparedPayload {
  images: string[]
  fixedImage?: string
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') { reject(new Error('IndexedDB 미지원')); return }
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE)
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error || new Error('IndexedDB 열기 실패'))
  })
}

async function run<T>(mode: IDBTransactionMode, exec: (s: IDBObjectStore) => IDBRequest): Promise<T> {
  const db = await openDB()
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction(STORE, mode)
      const req = exec(tx.objectStore(STORE))
      req.onsuccess = () => resolve(req.result as T)
      req.onerror = () => reject(req.error || new Error('IndexedDB 오류'))
    })
  } finally {
    db.close()
  }
}

/**
 * 이 오리진의 저장소를 '지속(persistent)'으로 승격 요청한다.
 * 기본값은 best-effort 라, 100건 준비함(약 400~500MB)은 디스크가 빠듯해지면
 * 크롬이 예고 없이 통째로 비운다 — 담아두고 며칠 뒤 발행하는 패턴에서 특히 위험하다.
 * 이미 승인됐거나 브라우저가 미지원이면 조용히 넘어간다(요청 자체는 실패해도 무해).
 */
export async function requestPersistentStorage(): Promise<boolean> {
  try {
    if (!navigator.storage?.persist) return false
    if (await navigator.storage.persisted()) return true
    return await navigator.storage.persist()
  } catch {
    return false
  }
}

/** 남은 저장 여유(바이트). 알 수 없으면 null. */
export async function storageHeadroom(): Promise<number | null> {
  try {
    if (!navigator.storage?.estimate) return null
    const { quota, usage } = await navigator.storage.estimate()
    if (typeof quota !== 'number' || typeof usage !== 'number') return null
    return quota - usage
  } catch {
    return null
  }
}

export const preparedStore = {
  /** 사진 payload 저장. 실패하면 throw — 담기 자체를 실패시켜야 한다(조용히 삼키면 발행 때 빈 글이 나간다). */
  put(id: string, payload: PreparedPayload): Promise<void> {
    return run<void>('readwrite', (s) => s.put(payload, id)).then(() => undefined)
  },

  /**
   * 발행 직전 한 건만 꺼낸다. 항목이 정말 없으면 null, '읽기에 실패'하면 throw.
   *
   * 예전엔 .catch(() => null) 로 모든 오류를 삼켰다. 그러면 DB 열기 실패·트랜잭션 중단·
   * 스토리지 축출이 "사진 없음"과 구분되지 않아, 사진이 잠깐 안 읽힌 것뿐인데도
   * 글이 사진 없이 예약 등록되고 성공으로 보고돼 원본까지 지워졌다. 구분해서 올려보낸다.
   */
  get(id: string): Promise<PreparedPayload | null> {
    return run<PreparedPayload | undefined>('readonly', (s) => s.get(id)).then((v) => v || null)
  },

  /** 발행 성공/삭제 시 정리. 실패해도 무시(다음 prune 이 치운다). */
  remove(id: string): Promise<void> {
    return run<void>('readwrite', (s) => s.delete(id)).then(() => undefined).catch(() => undefined)
  },

  keys(): Promise<string[]> {
    return run<IDBValidKey[]>('readonly', (s) => s.getAllKeys())
      .then((ks) => ks.map(String))
      .catch(() => [])
  },

  /** 준비함 목록에 없는 고아 payload 를 지운다(발행 도중 탭이 닫힌 경우 등). */
  async prune(validIds: string[]): Promise<void> {
    const keep = new Set(validIds)
    const all = await preparedStore.keys()
    await Promise.all(all.filter((k) => !keep.has(k)).map((k) => preparedStore.remove(k)))
  },
}
