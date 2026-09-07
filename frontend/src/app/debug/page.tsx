'use client'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PageHeader } from '@/components/app-shell/page-header'

export default function DebugPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-2xl space-y-6 px-4 py-8">
        <PageHeader title="Debug Information" description="환경 변수와 백엔드 연결 상태를 확인합니다." />

        <Card>
          <CardHeader>
            <CardTitle>Environment Variable</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto rounded-lg bg-muted p-4 text-xs tabular-nums">
              NEXT_PUBLIC_API_URL = {apiUrl || 'NOT SET'}
            </pre>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Backend URL Test</CardTitle>
          </CardHeader>
          <CardContent>
            <Button
              onClick={async () => {
                const url = apiUrl || 'http://localhost:8000'
                try {
                  const response = await fetch(`${url}/health`)
                  const data = await response.json()
                  alert(`Success! ${JSON.stringify(data, null, 2)}`)
                } catch (error: any) {
                  alert(`Error: ${error.message}`)
                }
              }}
            >
              Test Connection
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
