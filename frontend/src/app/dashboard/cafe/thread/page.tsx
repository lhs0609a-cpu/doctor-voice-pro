'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { PageHeader } from '@/components/app-shell/page-header'
import { CafeThreadPanel } from '@/components/cafe/cafe-thread-panel'
import { campaignAPI, type Client } from '@/lib/campaign-api'
import { errMsg } from '@/components/campaign/common'

export default function Page() {
  const [clients, setClients] = useState<Client[]>([])

  useEffect(() => {
    let alive = true
    campaignAPI.listClients()
      .then((rows) => { if (alive) setClients(rows) })
      .catch((e) => { if (alive) toast.error('병원 목록을 불러오지 못했습니다', { description: errMsg(e) }) })
    return () => { alive = false }
  }, [])

  return (
    <div className="space-y-6">
      <PageHeader
        title="카페 질문글 세트"
        description="질문글 1개와 댓글 여러 개를 한 번에 만듭니다. 병원 이름은 정한 한 댓글에서만 말합니다."
      />
      <CafeThreadPanel clients={clients} />
    </div>
  )
}
