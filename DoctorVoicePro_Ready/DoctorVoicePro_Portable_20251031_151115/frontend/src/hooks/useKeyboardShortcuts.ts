import { useEffect } from 'react'

interface ShortcutConfig {
  key: string
  ctrl?: boolean
  shift?: boolean
  alt?: boolean
  handler: (event: KeyboardEvent) => void
  description?: string
}

export function useKeyboardShortcuts(shortcuts: ShortcutConfig[]) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      for (const shortcut of shortcuts) {
        const ctrlMatch = shortcut.ctrl === undefined || shortcut.ctrl === (event.ctrlKey || event.metaKey)
        const shiftMatch = shortcut.shift === undefined || shortcut.shift === event.shiftKey
        const altMatch = shortcut.alt === undefined || shortcut.alt === event.altKey
        const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase()

        if (ctrlMatch && shiftMatch && altMatch && keyMatch) {
          event.preventDefault()
          shortcut.handler(event)
          return
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [shortcuts])
}

// Shortcut help modal hook
export function useShortcutHelp() {
  const shortcuts = [
    { keys: 'Ctrl + S', description: '현재 내용 저장' },
    { keys: 'Ctrl + Enter', description: '포스팅 생성/발행' },
    { keys: 'Ctrl + /', description: '단축키 도움말' },
    { keys: 'Ctrl + K', description: '검색' },
    { keys: 'Esc', description: '모달 닫기' },
  ]

  return shortcuts
}
