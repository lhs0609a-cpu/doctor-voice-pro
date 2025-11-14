'use client'

export default function DebugPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL

  return (
    <div className="min-h-screen p-8 bg-gray-50">
      <div className="max-w-2xl mx-auto bg-white p-6 rounded-lg shadow">
        <h1 className="text-2xl font-bold mb-4">Debug Information</h1>

        <div className="space-y-4">
          <div>
            <h2 className="font-semibold text-gray-700">Environment Variable:</h2>
            <pre className="mt-2 p-4 bg-gray-100 rounded">
              NEXT_PUBLIC_API_URL = {apiUrl || 'NOT SET'}
            </pre>
          </div>

          <div>
            <h2 className="font-semibold text-gray-700">Backend URL Test:</h2>
            <button
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
              className="mt-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              Test Connection
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
