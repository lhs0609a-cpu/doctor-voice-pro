'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from 'react'
import { ExternalLink, Loader2 } from 'lucide-react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { VERDICT_LABEL, campaignAPI, type Keyword, type SerpPost, type SerpSummary } from '@/lib/campaign-api'
import { EmptyNote, Pill, TABLE_CLS, errMsg, fmt, fmtDateTime } from './common'

const BLOG_TYPE_LABEL: Record<string, string> = {
  hospital: '병원', influencer: '인플루언서', daily: '일상', personal: '개인', brand: '브랜드', unknown: '기타',
}

export function KeywordSerpDialog({ campaignId, keyword, onClose }: { campaignId: string; keyword: Keyword | null; onClose: () => void }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [posts, setPosts] = useState<SerpPost[]>([])
  const [summary, setSummary] = useState<SerpSummary | null>(null)
  const [meta, setMeta] = useState<{ fetched_at?: string; verdict?: string; verdict_reason?: string }>({})

  useEffect(() => {
    if (!keyword) return
    let alive = true
    setLoading(true); setError(null); setPosts([]); setSummary(null); setMeta({})
    campaignAPI.keywordSerp(campaignId, keyword.id)
      .then((r) => {
        if (!alive) return
        setPosts(r.posts || [])
        setSummary(r.summary || null)
        setMeta({ fetched_at: r.fetched_at, verdict: r.verdict, verdict_reason: r.verdict_reason })
        if (r.error) setError(r.error)
      })
      .catch((err) => { if (alive) setError(errMsg(err)) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [campaignId, keyword])

  const v = VERDICT_LABEL[meta.verdict || keyword?.verdict || 'unknown'] || VERDICT_LABEL.unknown

  return (
    <Dialog open={!!keyword} onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {keyword?.keyword}
            <Pill tone={v.tone}>{v.label}</Pill>
          </DialogTitle>
          <DialogDescription>
            네이버 통합검색에 노출된 블로그 글을 분석한 결과입니다.
            {meta.fetched_at ? ` (${fmtDateTime(meta.fetched_at)} 기준)` : ''}
          </DialogDescription>
        </DialogHeader>

        {(meta.verdict_reason || keyword?.verdict_reason) && (
          <p className="rounded-lg bg-muted/60 p-3 text-sm">{meta.verdict_reason || keyword?.verdict_reason}</p>
        )}

        {summary && (
          <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
            <Stat label="노출 글" value={fmt(summary.exposed_count)} />
            <Stat label="병원 글" value={`${fmt(summary.hospital_count)}${summary.hospital_ratio != null ? ` (${Math.round(summary.hospital_ratio * 100)}%)` : ''}`} />
            <Stat label="인플루언서" value={fmt(summary.influencer_count)} />
            <Stat label="일상 블로그" value={fmt(summary.daily_count)} />
            <Stat label="권장 글자수" value={summary.recommended_chars ? `${fmt(summary.recommended_chars)}자` : '-'} sub={summary.avg_chars ? `평균 ${fmt(summary.avg_chars)}` : undefined} />
            <Stat label="권장 사진" value={summary.recommended_image_count != null ? `${fmt(summary.recommended_image_count)}장` : '-'} sub={summary.avg_image_count != null ? `평균 ${summary.avg_image_count.toFixed(1)}` : undefined} />
            <Stat label="권장 키워드 수" value={summary.recommended_kw_count != null ? `${fmt(summary.recommended_kw_count)}회` : '-'} sub={summary.avg_kw_count != null ? `평균 ${summary.avg_kw_count.toFixed(1)}` : undefined} />
            <Stat label="평균 소제목" value={summary.avg_headings != null ? summary.avg_headings.toFixed(1) : '-'} />
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> 분석 결과 불러오는 중...</div>
        ) : error && posts.length === 0 ? (
          <div className="rounded-lg bg-warning-soft p-3 text-sm text-warning">{error}</div>
        ) : posts.length === 0 ? (
          <EmptyNote>아직 분석 전입니다. 목록에서 이 키워드를 선택하고 <b>선택 키워드 통검 분석</b>을 눌러 주세요.</EmptyNote>
        ) : (
          <div className="overflow-x-auto">
            <Table className={TABLE_CLS}>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">#</TableHead>
                  <TableHead>제목</TableHead>
                  <TableHead>블로그</TableHead>
                  <TableHead className="text-right">키워드</TableHead>
                  <TableHead className="text-right">사진</TableHead>
                  <TableHead className="text-right">글자</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {posts.map((p, i) => (
                  <TableRow key={`${p.url}-${i}`}>
                    <TableCell className="tabular-nums text-muted-foreground">{p.position ?? i + 1}</TableCell>
                    <TableCell className="max-w-[320px]">
                      <a href={p.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-start gap-1 hover:underline">
                        <span className="line-clamp-2">{p.title}</span>
                        <ExternalLink className="mt-1 h-3 w-3 shrink-0 text-muted-foreground" />
                      </a>
                      {p.is_ad && <Pill tone="warn" className="mt-1">광고</Pill>}
                    </TableCell>
                    <TableCell>
                      <div className="text-xs">{p.blog_name || p.blog_id}</div>
                      <Pill tone={p.blog_type === 'hospital' ? 'info' : p.blog_type === 'influencer' ? 'warn' : 'muted'}>
                        {BLOG_TYPE_LABEL[p.blog_type] || p.blog_type}
                      </Pill>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{p.kw_count ?? '-'}</TableCell>
                    <TableCell className="text-right tabular-nums">{p.image_count ?? '-'}</TableCell>
                    <TableCell className="text-right tabular-nums">{p.chars != null ? fmt(p.chars) : '-'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg bg-muted/60 p-2.5">
      <div className="text-[12px] font-medium text-muted-foreground">{label}</div>
      <div className="font-semibold tabular-nums">{value}</div>
      {sub && <div className="text-[11px] tabular-nums text-muted-foreground">{sub}</div>}
    </div>
  )
}
