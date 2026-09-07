import { toast } from 'sonner'

/** 확장 설치 안내 페이지 경로. 여기 한 곳에서만 바꾸면 된다. */
export const EXTENSION_GUIDE_PATH = '/dashboard/extension'

/**
 * 확장 프로그램이 연결되지 않았을 때 띄우는 토스트.
 *
 * 예전에는 "설치 후 페이지를 새로고침하세요" 라고만 알려주고 끝이라
 * 어디서 어떻게 설치하는지 알 방법이 없었다. 바로 설치 화면으로 보낸다.
 */
export function toastExtensionMissing(message?: string) {
  toast.error(message || '확장 프로그램이 연결되지 않았습니다', {
    description: '글 자동작성과 자동발행은 크롬 확장 프로그램이 있어야 동작합니다.',
    duration: 10000,
    action: {
      label: '설치하기',
      onClick: () => {
        window.location.href = EXTENSION_GUIDE_PATH
      },
    },
  })
}
