'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { DevBanner } from '@/components/app-shell/dev-banner'
import { Sidebar } from '@/components/app-shell/sidebar'
import { Topbar } from '@/components/app-shell/topbar'
import { useAuthStore } from '@/store/auth'
import OnboardingModal from '@/components/onboarding/OnboardingModal'
import TutorialGuide from '@/components/tutorial/TutorialGuide'
import { GenerationSaver } from '@/components/generation-saver'

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { user, hydrated, hydrate } = useAuthStore()
  const [showOnboarding, setShowOnboarding] = useState(false)
  const [showTutorial, setShowTutorial] = useState(false)

  // 새로고침 직후에는 스토어가 비어 있으므로, 저장된 세션을 먼저 읽고 나서 판단한다
  useEffect(() => {
    if (!hydrated) hydrate()
  }, [hydrated, hydrate])

  useEffect(() => {
    if (!hydrated) return
    if (!user) {
      router.push('/login')
      return
    }
    const onboardingCompleted = localStorage.getItem('onboarding_completed')
    const tutorialCompleted = localStorage.getItem('tutorial_completed')
    if (!onboardingCompleted) setShowOnboarding(true)
    else if (!tutorialCompleted) setShowTutorial(true)
  }, [user, hydrated, router])

  const handleOnboardingComplete = () => {
    setShowOnboarding(false)
    if (!localStorage.getItem('tutorial_completed')) setShowTutorial(true)
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-background">
      <GenerationSaver />
      <div className="fixed inset-y-0 left-0 z-20 hidden lg:block">
        <Sidebar />
      </div>
      <div className="flex min-w-0 flex-1 flex-col lg:pl-[236px]">
        <Topbar />
        <main className="mx-auto w-full max-w-[1200px] flex-1 px-4 py-6 md:px-6 lg:px-8 lg:py-8">
          <DevBanner />
          {children}
        </main>
      </div>

      {showOnboarding && (
        <OnboardingModal
          userName={user?.name ?? undefined}
          onComplete={handleOnboardingComplete}
          onClose={() => {
            localStorage.setItem('onboarding_completed', 'true')
            setShowOnboarding(false)
          }}
        />
      )}
      {showTutorial && <TutorialGuide onComplete={() => setShowTutorial(false)} onClose={() => setShowTutorial(false)} />}
    </div>
  )
}
