/**
 * IndexedDB 유틸리티
 * 이미지 저장 및 관리를 위한 IndexedDB 래퍼
 */

const DB_NAME = 'doctorvoice-db'
const DB_VERSION = 1
const STORE_NAME = 'images'

export interface ImageRecord {
  id: string
  postId: string
  file: Blob
  thumbnail: string // Base64 썸네일 (미리보기용)
  position?: number // 문단 위치 (선택사항)
  uploadedAt: number
}

/**
 * IndexedDB 초기화
 */
export const initDB = (): Promise<IDBDatabase> => {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onerror = () => {
      reject(new Error('IndexedDB를 열 수 없습니다.'))
    }

    request.onsuccess = () => {
      resolve(request.result)
    }

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result

      // images store 생성
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' })
        store.createIndex('postId', 'postId', { unique: false })
        store.createIndex('uploadedAt', 'uploadedAt', { unique: false })
      }
    }
  })
}

/**
 * 이미지 저장
 */
export const saveImage = async (
  postId: string,
  file: File
): Promise<string> => {
  const db = await initDB()

  // 고유 ID 생성
  const imageId = `img-${postId}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

  // 썸네일 생성 (작은 크기로 압축)
  const thumbnail = await createThumbnail(file, 200)

  const imageRecord: ImageRecord = {
    id: imageId,
    postId,
    file,
    thumbnail,
    uploadedAt: Date.now(),
  }

  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite')
    const store = transaction.objectStore(STORE_NAME)
    const request = store.add(imageRecord)

    request.onsuccess = () => {
      resolve(imageId)
    }

    request.onerror = () => {
      reject(new Error('이미지 저장에 실패했습니다.'))
    }
  })
}

/**
 * 글 ID로 이미지 목록 조회
 */
export const getImagesByPostId = async (
  postId: string
): Promise<ImageRecord[]> => {
  const db = await initDB()

  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readonly')
    const store = transaction.objectStore(STORE_NAME)
    const index = store.index('postId')
    const request = index.getAll(postId)

    request.onsuccess = () => {
      resolve(request.result)
    }

    request.onerror = () => {
      reject(new Error('이미지 조회에 실패했습니다.'))
    }
  })
}

/**
 * 이미지 삭제
 */
export const deleteImage = async (imageId: string): Promise<void> => {
  const db = await initDB()

  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite')
    const store = transaction.objectStore(STORE_NAME)
    const request = store.delete(imageId)

    request.onsuccess = () => {
      resolve()
    }

    request.onerror = () => {
      reject(new Error('이미지 삭제에 실패했습니다.'))
    }
  })
}

/**
 * 글 ID로 모든 이미지 삭제
 */
export const deleteImagesByPostId = async (postId: string): Promise<void> => {
  const images = await getImagesByPostId(postId)
  const db = await initDB()

  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite')
    const store = transaction.objectStore(STORE_NAME)

    let completed = 0
    let hasError = false

    for (const image of images) {
      const request = store.delete(image.id)

      request.onsuccess = () => {
        completed++
        if (completed === images.length && !hasError) {
          resolve()
        }
      }

      request.onerror = () => {
        hasError = true
        reject(new Error('이미지 삭제에 실패했습니다.'))
      }
    }

    // 이미지가 없으면 즉시 완료
    if (images.length === 0) {
      resolve()
    }
  })
}

/**
 * 이미지 Blob 조회
 */
export const getImageBlob = async (imageId: string): Promise<Blob | null> => {
  const db = await initDB()

  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readonly')
    const store = transaction.objectStore(STORE_NAME)
    const request = store.get(imageId)

    request.onsuccess = () => {
      const result = request.result as ImageRecord | undefined
      resolve(result ? result.file : null)
    }

    request.onerror = () => {
      reject(new Error('이미지 조회에 실패했습니다.'))
    }
  })
}

/**
 * 이미지 위치 업데이트
 */
export const updateImagePosition = async (
  imageId: string,
  position: number
): Promise<void> => {
  const db = await initDB()

  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite')
    const store = transaction.objectStore(STORE_NAME)
    const getRequest = store.get(imageId)

    getRequest.onsuccess = () => {
      const imageRecord = getRequest.result as ImageRecord

      if (!imageRecord) {
        reject(new Error('이미지를 찾을 수 없습니다.'))
        return
      }

      imageRecord.position = position

      const updateRequest = store.put(imageRecord)

      updateRequest.onsuccess = () => {
        resolve()
      }

      updateRequest.onerror = () => {
        reject(new Error('이미지 위치 업데이트에 실패했습니다.'))
      }
    }

    getRequest.onerror = () => {
      reject(new Error('이미지 조회에 실패했습니다.'))
    }
  })
}

/**
 * 썸네일 생성 (내부 헬퍼 함수)
 */
const createThumbnail = (
  file: File,
  maxWidth: number
): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()

    reader.onload = (e) => {
      const img = new Image()

      img.onload = () => {
        const canvas = document.createElement('canvas')
        const ctx = canvas.getContext('2d')

        if (!ctx) {
          reject(new Error('Canvas context를 생성할 수 없습니다.'))
          return
        }

        // 비율 유지하며 크기 조정
        const ratio = maxWidth / img.width
        canvas.width = maxWidth
        canvas.height = img.height * ratio

        ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

        // Base64로 변환
        resolve(canvas.toDataURL('image/jpeg', 0.7))
      }

      img.onerror = () => {
        reject(new Error('이미지 로드에 실패했습니다.'))
      }

      img.src = e.target?.result as string
    }

    reader.onerror = () => {
      reject(new Error('파일 읽기에 실패했습니다.'))
    }

    reader.readAsDataURL(file)
  })
}

/**
 * IndexedDB 지원 여부 확인
 */
export const isIndexedDBSupported = (): boolean => {
  return 'indexedDB' in window
}
