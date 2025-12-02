import { useEffect, useRef, useCallback } from 'react'
import { debounce } from 'lodash'

interface AutoSaveOptions {
  key: string
  data: any
  onSave?: (data: any) => void
  delay?: number
  enabled?: boolean
}

export function useAutoSave({
  key,
  data,
  onSave,
  delay = 3000,
  enabled = true,
}: AutoSaveOptions) {
  const lastSavedRef = useRef<Date | null>(null)
  const dataRef = useRef(data)

  // Update ref when data changes
  useEffect(() => {
    dataRef.current = data
  }, [data])

  // Debounced save function
  const debouncedSave = useCallback(
    debounce((saveData: any) => {
      if (!enabled) return

      try {
        // Save to localStorage
        localStorage.setItem(key, JSON.stringify(saveData))
        lastSavedRef.current = new Date()

        // Call optional callback
        if (onSave) {
          onSave(saveData)
        }
      } catch (error) {
        console.error('Auto-save failed:', error)
      }
    }, delay),
    [key, onSave, delay, enabled]
  )

  // Auto-save when data changes
  useEffect(() => {
    if (enabled && data) {
      debouncedSave(data)
    }

    // Cleanup
    return () => {
      debouncedSave.cancel()
    }
  }, [data, enabled, debouncedSave])

  // Load saved data
  const loadSaved = useCallback(() => {
    try {
      const saved = localStorage.getItem(key)
      if (saved) {
        return JSON.parse(saved)
      }
    } catch (error) {
      console.error('Failed to load saved data:', error)
    }
    return null
  }, [key])

  // Clear saved data
  const clearSaved = useCallback(() => {
    try {
      localStorage.removeItem(key)
      lastSavedRef.current = null
    } catch (error) {
      console.error('Failed to clear saved data:', error)
    }
  }, [key])

  // Manual save
  const saveNow = useCallback(() => {
    debouncedSave.cancel()
    const currentData = dataRef.current
    if (currentData) {
      localStorage.setItem(key, JSON.stringify(currentData))
      lastSavedRef.current = new Date()
      if (onSave) {
        onSave(currentData)
      }
    }
  }, [key, onSave, debouncedSave])

  return {
    lastSaved: lastSavedRef.current,
    loadSaved,
    clearSaved,
    saveNow,
  }
}
