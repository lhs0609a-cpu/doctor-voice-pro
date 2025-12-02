/**
 * Frontend Logging & Monitoring Service
 * 프론트엔드 이벤트, 에러, 성능 추적
 */

export enum LogLevel {
  DEBUG = 'DEBUG',
  INFO = 'INFO',
  WARNING = 'WARNING',
  ERROR = 'ERROR',
}

export enum EventType {
  PAGE_VIEW = 'page_view',
  USER_ACTION = 'user_action',
  API_CALL = 'api_call',
  API_ERROR = 'api_error',
  FORM_SUBMIT = 'form_submit',
  FILE_UPLOAD = 'file_upload',
  ERROR = 'error',
  PERFORMANCE = 'performance',
}

interface LogEntry {
  timestamp: string
  level: LogLevel
  event_type: EventType
  message: string
  data?: any
  user_id?: string
  session_id?: string
}

class FrontendLogger {
  private logs: LogEntry[] = []
  private sessionId: string
  private maxLogs = 1000

  constructor() {
    this.sessionId = this.generateSessionId()
    this.initErrorHandlers()
    this.initPerformanceMonitoring()
  }

  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  private initErrorHandlers() {
    // Global error handler
    if (typeof window !== 'undefined') {
      window.addEventListener('error', (event) => {
        this.logError(event.error, {
          message: event.message,
          filename: event.filename,
          lineno: event.lineno,
          colno: event.colno,
        })
      })

      // Unhandled promise rejection
      window.addEventListener('unhandledrejection', (event) => {
        this.logError(new Error(`Unhandled Promise Rejection: ${event.reason}`), {
          reason: event.reason,
        })
      })
    }
  }

  private initPerformanceMonitoring() {
    if (typeof window !== 'undefined' && 'PerformanceObserver' in window) {
      // Monitor page load performance
      window.addEventListener('load', () => {
        setTimeout(() => {
          const perfData = window.performance.getEntriesByType('navigation')[0] as any
          if (perfData) {
            this.logPerformance('page_load', {
              loadTime: perfData.loadEventEnd - perfData.fetchStart,
              domContentLoaded: perfData.domContentLoadedEventEnd - perfData.fetchStart,
              firstPaint: this.getFirstPaint(),
            })
          }
        }, 0)
      })
    }
  }

  private getFirstPaint(): number | null {
    if (typeof window !== 'undefined' && 'PerformanceObserver' in window) {
      const paintEntries = window.performance.getEntriesByType('paint')
      const firstPaint = paintEntries.find((entry) => entry.name === 'first-paint')
      return firstPaint ? firstPaint.startTime : null
    }
    return null
  }

  private log(
    level: LogLevel,
    event_type: EventType,
    message: string,
    data?: any,
    user_id?: string
  ) {
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      event_type,
      message,
      data,
      user_id,
      session_id: this.sessionId,
    }

    this.logs.push(entry)

    // Keep only recent logs
    if (this.logs.length > this.maxLogs) {
      this.logs = this.logs.slice(-this.maxLogs)
    }

    // Console output
    const consoleMethod = level === LogLevel.ERROR ? 'error' : level === LogLevel.WARNING ? 'warn' : 'log'
    console[consoleMethod](`[${level}] ${event_type}:`, message, data || '')

    // Send to backend if error or warning
    if (level === LogLevel.ERROR || level === LogLevel.WARNING) {
      this.sendToBackend(entry)
    }
  }

  private async sendToBackend(entry: LogEntry) {
    try {
      // In production, send logs to backend
      // await fetch('/api/v1/logs', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify(entry),
      // })
    } catch (error) {
      console.error('Failed to send log to backend:', error)
    }
  }

  // Public methods
  logPageView(path: string, user_id?: string) {
    this.log(LogLevel.INFO, EventType.PAGE_VIEW, `Page view: ${path}`, { path }, user_id)
  }

  logUserAction(action: string, details?: any, user_id?: string) {
    this.log(LogLevel.INFO, EventType.USER_ACTION, `User action: ${action}`, details, user_id)
  }

  logApiCall(method: string, endpoint: string, duration?: number) {
    this.log(LogLevel.INFO, EventType.API_CALL, `API ${method} ${endpoint}`, {
      method,
      endpoint,
      duration,
    })
  }

  logApiError(method: string, endpoint: string, error: any, status?: number) {
    this.log(LogLevel.ERROR, EventType.API_ERROR, `API Error: ${method} ${endpoint}`, {
      method,
      endpoint,
      error: error.message || error,
      status,
    })
  }

  logFormSubmit(formName: string, success: boolean, user_id?: string) {
    const level = success ? LogLevel.INFO : LogLevel.WARNING
    this.log(level, EventType.FORM_SUBMIT, `Form ${formName} ${success ? 'submitted' : 'failed'}`, {
      formName,
      success,
    }, user_id)
  }

  logFileUpload(fileName: string, size: number, success: boolean, user_id?: string) {
    const level = success ? LogLevel.INFO : LogLevel.ERROR
    this.log(level, EventType.FILE_UPLOAD, `File upload: ${fileName}`, {
      fileName,
      size,
      success,
    }, user_id)
  }

  logError(error: Error, context?: any, user_id?: string) {
    this.log(LogLevel.ERROR, EventType.ERROR, error.message, {
      name: error.name,
      stack: error.stack,
      context,
    }, user_id)
  }

  logPerformance(metric: string, data: any) {
    this.log(LogLevel.INFO, EventType.PERFORMANCE, `Performance: ${metric}`, data)
  }

  // Get all logs
  getLogs(filter?: { level?: LogLevel; event_type?: EventType }) {
    if (!filter) return this.logs

    return this.logs.filter((log) => {
      if (filter.level && log.level !== filter.level) return false
      if (filter.event_type && log.event_type !== filter.event_type) return false
      return true
    })
  }

  // Get metrics
  getMetrics() {
    const errors = this.logs.filter((log) => log.level === LogLevel.ERROR)
    const apiCalls = this.logs.filter((log) => log.event_type === EventType.API_CALL)

    return {
      total_logs: this.logs.length,
      total_errors: errors.length,
      total_api_calls: apiCalls.length,
      recent_errors: errors.slice(-10),
      session_id: this.sessionId,
    }
  }

  // Clear logs
  clearLogs() {
    this.logs = []
  }
}

// Singleton export
export const logger = new FrontendLogger()
