/**
 * 이미지 처리 유틸리티
 * Base64 변환, 압축, 위치 계산 등 이미지 관련 공통 로직
 */

/**
 * 이미지 압축
 * 1MB 이상의 이미지를 자동으로 압축합니다.
 */
export const compressImage = async (
  file: File,
  maxWidth = 1200,
  quality = 0.8
): Promise<string> => {
  return new Promise((resolve, reject) => {
    // 1MB 미만이면 압축하지 않고 바로 변환
    if (file.size < 1024 * 1024) {
      fileToBase64(file).then(resolve).catch(reject)
      return
    }

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

        // 너비 제한
        let width = img.width
        let height = img.height

        if (width > maxWidth) {
          height = (height * maxWidth) / width
          width = maxWidth
        }

        canvas.width = width
        canvas.height = height

        // 이미지 그리기
        ctx.drawImage(img, 0, 0, width, height)

        // Base64로 변환 (JPEG, quality 0.8)
        resolve(canvas.toDataURL('image/jpeg', quality))
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
 * File 객체를 Base64로 변환
 */
export const fileToBase64 = async (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()

    reader.onload = () => {
      resolve(reader.result as string)
    }

    reader.onerror = () => {
      reject(new Error('파일 읽기에 실패했습니다.'))
    }

    reader.readAsDataURL(file)
  })
}

/**
 * Blob 객체를 Base64로 변환
 */
export const blobToBase64 = async (blob: Blob): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()

    reader.onload = () => {
      resolve(reader.result as string)
    }

    reader.onerror = () => {
      reject(new Error('Blob 읽기에 실패했습니다.'))
    }

    reader.readAsDataURL(blob)
  })
}

/**
 * 이미지 배치 위치 계산
 *
 * @param paragraphCount 문단 수
 * @param imageCount 이미지 수
 * @param strategy 배치 전략 ('between': 문단 사이, 'even': 균등 분포)
 * @returns 이미지를 삽입할 문단 인덱스 배열
 */
export const calculateImagePositions = (
  paragraphCount: number,
  imageCount: number,
  strategy: 'between' | 'even' = 'between'
): number[] => {
  if (imageCount === 0 || paragraphCount === 0) {
    return []
  }

  if (strategy === 'between') {
    // 문단 사이 배치: 2-3 문단마다 이미지 삽입
    const interval = Math.max(2, Math.floor(paragraphCount / (imageCount + 1)))
    const positions: number[] = []

    for (let i = 0; i < imageCount; i++) {
      const position = (i + 1) * interval
      if (position < paragraphCount) {
        positions.push(position)
      }
    }

    return positions
  } else {
    // 균등 분포: 전체 문단에 이미지를 균등하게 배치
    const interval = Math.max(1, Math.floor(paragraphCount / imageCount))
    const positions: number[] = []

    for (let i = 0; i < imageCount; i++) {
      const position = Math.min(i * interval, paragraphCount - 1)
      positions.push(position)
    }

    return positions
  }
}

/**
 * Base64 이미지 데이터의 용량 계산 (바이트)
 */
export const getBase64Size = (base64: string): number => {
  // Base64 문자열에서 데이터 부분만 추출
  const base64Data = base64.split(',')[1] || base64

  // Base64는 4글자당 3바이트
  const padding = (base64Data.match(/=/g) || []).length
  return (base64Data.length * 3) / 4 - padding
}

/**
 * Base64 이미지 데이터의 용량을 사람이 읽기 쉬운 형식으로 변환
 */
export const formatBase64Size = (base64: string): string => {
  const bytes = getBase64Size(base64)

  if (bytes < 1024) {
    return `${bytes} B`
  } else if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(2)} KB`
  } else {
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
  }
}

/**
 * 여러 이미지를 동시에 Base64로 변환 (진행률 콜백 포함)
 */
export const convertImagesToBase64 = async (
  files: File[],
  onProgress?: (current: number, total: number) => void,
  compress = true
): Promise<string[]> => {
  const results: string[] = []

  for (let i = 0; i < files.length; i++) {
    const file = files[i]

    if (compress) {
      results.push(await compressImage(file))
    } else {
      results.push(await fileToBase64(file))
    }

    if (onProgress) {
      onProgress(i + 1, files.length)
    }
  }

  return results
}

/**
 * 이미지 URL에서 Blob 가져오기
 */
export const urlToBlob = async (url: string): Promise<Blob> => {
  const response = await fetch(url)
  return await response.blob()
}

/**
 * 이미지 파일 타입 검증
 */
export const isValidImageFile = (file: File): boolean => {
  const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
  return validTypes.includes(file.type)
}

/**
 * 이미지 파일 크기 검증 (기본 10MB 제한)
 */
export const isValidImageSize = (file: File, maxSizeMB = 10): boolean => {
  const maxSizeBytes = maxSizeMB * 1024 * 1024
  return file.size <= maxSizeBytes
}

/**
 * 이미지 파일 배열 검증
 */
export const validateImageFiles = (
  files: File[],
  maxSizeMB = 10
): { valid: File[]; invalid: { file: File; reason: string }[] } => {
  const valid: File[] = []
  const invalid: { file: File; reason: string }[] = []

  for (const file of files) {
    if (!isValidImageFile(file)) {
      invalid.push({ file, reason: '지원하지 않는 파일 형식입니다.' })
    } else if (!isValidImageSize(file, maxSizeMB)) {
      invalid.push({ file, reason: `파일 크기가 ${maxSizeMB}MB를 초과합니다.` })
    } else {
      valid.push(file)
    }
  }

  return { valid, invalid }
}
