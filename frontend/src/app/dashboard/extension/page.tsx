// 크롬 확장 프로그램은 PC 실행기로 대체됐다. 예전 링크·북마크를 위해 안내 페이지로 보낸다.
import { redirect } from 'next/navigation'

export default function ExtensionPage() {
  redirect('/dashboard/launcher')
}
