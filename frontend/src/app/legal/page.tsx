'use client'

import { useState } from 'react'
import Link from 'next/link'
import {
  ChevronDown, ChevronUp, Shield, FileText, Lock, AlertTriangle, Scale, Users,
  Copyright, CreditCard, Gavel, Globe, UserX, Server, Ban, RefreshCw, Smartphone
} from 'lucide-react'

type SectionKey = 'terms' | 'disclaimer' | 'privacy' | 'medical' | 'content' | 'platform' |
                  'copyright' | 'ecommerce' | 'defamation' | 'account' | 'thirdparty' | 'international' | 'dispute'

export default function LegalPage() {
  const [expandedSection, setExpandedSection] = useState<SectionKey | null>('terms')

  const toggleSection = (section: SectionKey) => {
    setExpandedSection(expandedSection === section ? null : section)
  }

  const sections = [
    { id: 'terms' as SectionKey, title: '서비스 이용약관', icon: <FileText className="w-5 h-5" />, color: 'blue' },
    { id: 'disclaimer' as SectionKey, title: '면책조항', icon: <Shield className="w-5 h-5" />, color: 'red' },
    { id: 'privacy' as SectionKey, title: '개인정보처리방침', icon: <Lock className="w-5 h-5" />, color: 'green' },
    { id: 'medical' as SectionKey, title: '의료정보 관련 고지', icon: <AlertTriangle className="w-5 h-5" />, color: 'orange' },
    { id: 'content' as SectionKey, title: 'AI 생성 콘텐츠 정책', icon: <Scale className="w-5 h-5" />, color: 'purple' },
    { id: 'platform' as SectionKey, title: '외부 플랫폼 이용 안내', icon: <Users className="w-5 h-5" />, color: 'teal' },
    { id: 'copyright' as SectionKey, title: '저작권 및 지적재산권', icon: <Copyright className="w-5 h-5" />, color: 'indigo' },
    { id: 'ecommerce' as SectionKey, title: '전자상거래 및 환불 정책', icon: <CreditCard className="w-5 h-5" />, color: 'emerald' },
    { id: 'defamation' as SectionKey, title: '명예훼손 및 불법콘텐츠', icon: <Ban className="w-5 h-5" />, color: 'rose' },
    { id: 'account' as SectionKey, title: '계정 및 보안 정책', icon: <UserX className="w-5 h-5" />, color: 'amber' },
    { id: 'thirdparty' as SectionKey, title: '제3자 서비스 및 API', icon: <Server className="w-5 h-5" />, color: 'cyan' },
    { id: 'international' as SectionKey, title: '국제 이용 및 규제', icon: <Globe className="w-5 h-5" />, color: 'violet' },
    { id: 'dispute' as SectionKey, title: '분쟁 해결 및 관할', icon: <Gavel className="w-5 h-5" />, color: 'slate' },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 헤더 */}
      <div className="bg-white border-b">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">법적 고지 및 이용약관</h1>
              <p className="text-sm text-gray-600 mt-1">닥터보이스 프로 서비스 이용에 관한 법적 사항</p>
            </div>
            <Link href="/dashboard" className="text-blue-600 hover:underline text-sm">
              대시보드로 돌아가기
            </Link>
          </div>
        </div>
      </div>

      {/* 중요 안내 배너 */}
      <div className="bg-red-50 border-b border-red-200">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <h2 className="font-semibold text-red-800">중요 법적 고지</h2>
              <p className="text-sm text-red-700 mt-1">
                본 서비스를 이용함으로써 귀하는 아래의 모든 약관 및 정책에 <strong>법적 구속력 있는 동의</strong>를 하는 것입니다.
                서비스 이용 전 모든 내용을 주의 깊게 읽어주시기 바랍니다.
              </p>
              <div className="mt-2 p-3 bg-red-100 rounded-lg">
                <p className="text-sm text-red-800 font-bold">
                  핵심 고지: 본 서비스에서 생성된 콘텐츠의 사용, 게시, 배포에 대한 모든 민형사상 법적 책임은
                  전적으로 이용자에게 있습니다. 회사는 이용자의 콘텐츠 사용으로 인한 어떠한 법적 결과에 대해서도
                  책임을 지지 않습니다.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 메인 콘텐츠 */}
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto space-y-4">
          {sections.map((section) => (
            <div key={section.id} className="bg-white rounded-lg shadow-sm border overflow-hidden">
              <button
                onClick={() => toggleSection(section.id)}
                className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg bg-${section.color}-100 text-${section.color}-600`}>
                    {section.icon}
                  </div>
                  <span className="font-semibold text-gray-800">{section.title}</span>
                </div>
                {expandedSection === section.id ? (
                  <ChevronUp className="w-5 h-5 text-gray-500" />
                ) : (
                  <ChevronDown className="w-5 h-5 text-gray-500" />
                )}
              </button>

              {expandedSection === section.id && (
                <div className="px-6 pb-6 border-t">
                  {section.id === 'terms' && <TermsContent />}
                  {section.id === 'disclaimer' && <DisclaimerContent />}
                  {section.id === 'privacy' && <PrivacyContent />}
                  {section.id === 'medical' && <MedicalContent />}
                  {section.id === 'content' && <ContentPolicyContent />}
                  {section.id === 'platform' && <PlatformContent />}
                  {section.id === 'copyright' && <CopyrightContent />}
                  {section.id === 'ecommerce' && <EcommerceContent />}
                  {section.id === 'defamation' && <DefamationContent />}
                  {section.id === 'account' && <AccountContent />}
                  {section.id === 'thirdparty' && <ThirdPartyContent />}
                  {section.id === 'international' && <InternationalContent />}
                  {section.id === 'dispute' && <DisputeContent />}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* 최종 동의 안내 */}
        <div className="max-w-4xl mx-auto mt-8 space-y-4">
          <div className="p-6 bg-yellow-50 border border-yellow-300 rounded-lg">
            <h3 className="font-bold text-yellow-800 mb-3">법적 구속력 있는 동의</h3>
            <p className="text-sm text-yellow-700 mb-4">
              본 서비스에 가입하고 이용함으로써 귀하는 다음 사항에 <strong>법적 구속력 있는 동의</strong>를 한 것입니다:
            </p>
            <ul className="text-sm text-yellow-800 space-y-2">
              <li>1. 위에 명시된 모든 이용약관, 면책조항, 정책의 전체 내용</li>
              <li>2. AI 생성 콘텐츠 사용에 대한 전적인 법적 책임 부담</li>
              <li>3. 손해배상 책임 제한 및 면책 조항</li>
              <li>4. 분쟁 발생 시 대한민국 법률 적용 및 서울중앙지방법원 관할 동의</li>
              <li>5. 집단소송 포기 및 개별 분쟁 해결 동의</li>
              <li>6. 회사의 면책 및 보상(Indemnification) 의무</li>
            </ul>
          </div>

          <div className="p-6 bg-gray-100 rounded-lg border">
            <h3 className="font-bold text-gray-800 mb-3">약관 변경 및 통지</h3>
            <p className="text-sm text-gray-600 mb-4">
              회사는 법령 변경, 서비스 개선, 정책 변경 등의 사유로 본 약관을 변경할 수 있습니다.
              변경된 약관은 서비스 내 공지사항 게시 또는 이메일 통지로 고지되며,
              공지 후 7일 이내에 거부 의사를 표시하지 않으면 변경된 약관에 동의한 것으로 간주됩니다.
            </p>
            <div className="text-xs text-gray-500 space-y-1">
              <p>최초 시행일: 2024년 12월 16일</p>
              <p>최종 수정일: 2024년 12월 16일</p>
              <p>버전: 1.0</p>
            </div>
          </div>
        </div>
      </div>

      {/* 푸터 */}
      <footer className="bg-white border-t mt-12">
        <div className="container mx-auto px-4 py-6">
          <div className="text-center text-sm text-gray-500">
            <p>&copy; 2024 플라톤마케팅. All rights reserved.</p>
            <p className="mt-1">
              법률 문의: <a href="mailto:legal@platonmarketing.com" className="text-blue-600 hover:underline">legal@platonmarketing.com</a>
            </p>
            <p className="mt-1 text-xs text-gray-400">
              본 약관의 해석 및 적용은 대한민국 법률에 따릅니다.
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}

// 서비스 이용약관
function TermsContent() {
  return (
    <div className="prose prose-sm max-w-none pt-4 text-gray-700">
      <h3 className="text-lg font-bold text-gray-900 mb-4">제1조 (목적)</h3>
      <p>
        본 약관은 플라톤마케팅(이하 "회사")이 제공하는 닥터보이스 프로 서비스(이하 "서비스")의
        이용조건 및 절차, 회사와 이용자의 권리, 의무, 책임사항 및 기타 필요한 사항을 규정함을 목적으로 합니다.
      </p>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">제2조 (정의)</h3>
      <ol className="list-decimal pl-5 space-y-2">
        <li>"서비스"란 회사가 제공하는 AI 기반 콘텐츠 생성 및 마케팅 지원 도구를 의미합니다.</li>
        <li>"이용자"란 본 약관에 따라 서비스를 이용하는 회원 및 비회원을 의미합니다.</li>
        <li>"회원"이란 회사와 서비스 이용계약을 체결하고 계정을 부여받은 자를 의미합니다.</li>
        <li>"AI 생성 콘텐츠"란 인공지능 기술을 활용하여 자동으로 생성된 텍스트, 이미지, 영상 등 모든 형태의 결과물을 의미합니다.</li>
        <li>"계정"이란 서비스 이용을 위해 이용자가 생성한 고유한 식별 정보(이메일, 비밀번호 등)를 의미합니다.</li>
        <li>"유료서비스"란 회사가 유료로 제공하는 서비스 및 상품을 의미합니다.</li>
        <li>"크레딧"이란 서비스 내에서 사용되는 가상의 결제 단위를 의미합니다.</li>
      </ol>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">제3조 (약관의 효력 및 변경)</h3>
      <ol className="list-decimal pl-5 space-y-2">
        <li>본 약관은 서비스 화면에 게시하거나 기타의 방법으로 이용자에게 공지함으로써 효력을 발생합니다.</li>
        <li>회사는 관련 법령을 위배하지 않는 범위에서 본 약관을 변경할 수 있습니다.</li>
        <li>약관을 변경할 경우 변경 내용과 적용일자를 명시하여 적용일 7일 전에 공지합니다.
            다만, 이용자에게 불리한 변경의 경우 30일 전에 공지합니다.</li>
        <li>이용자가 변경된 약관의 적용일 이후에도 서비스를 계속 이용하는 경우 약관 변경에 동의한 것으로 봅니다.</li>
        <li>변경된 약관에 동의하지 않는 이용자는 서비스 이용을 중단하고 탈퇴할 수 있습니다.</li>
      </ol>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">제4조 (이용계약의 체결)</h3>
      <ol className="list-decimal pl-5 space-y-2">
        <li>이용계약은 이용자가 약관의 내용에 동의한 후 이용신청을 하고, 회사가 이를 승낙함으로써 체결됩니다.</li>
        <li>회사는 다음 각 호에 해당하는 신청에 대해서는 승낙하지 않을 수 있습니다:
          <ul className="list-disc pl-5 mt-2 space-y-1">
            <li>실명이 아니거나 타인의 명의를 이용한 경우</li>
            <li>허위의 정보를 기재하거나, 회사가 요구하는 내용을 기재하지 않은 경우</li>
            <li>만 14세 미만인 경우</li>
            <li>이전에 회원 자격을 상실한 적이 있는 경우</li>
            <li>기타 회사가 정한 이용신청 요건을 충족하지 못한 경우</li>
          </ul>
        </li>
      </ol>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">제5조 (서비스의 내용)</h3>
      <p>회사가 제공하는 서비스는 다음과 같습니다:</p>
      <ol className="list-decimal pl-5 space-y-2">
        <li>AI 기반 블로그 글 생성 및 편집 도구</li>
        <li>AI 기반 이미지 생성 도구</li>
        <li>SNS 콘텐츠 변환 및 최적화 도구</li>
        <li>콘텐츠 발행 지원 도구 (네이버 블로그, SNS 등)</li>
        <li>의료법 검사 도구</li>
        <li>키워드 분석 및 SEO 도구</li>
        <li>기타 회사가 정하는 서비스</li>
      </ol>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">제6조 (이용자의 의무)</h3>
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 my-4">
        <p className="font-bold text-red-800 mb-2">이용자는 다음 각 호의 행위를 하여서는 안 됩니다:</p>
        <ol className="list-decimal pl-5 space-y-2 text-red-700">
          <li>타인의 정보를 도용하거나 허위 정보를 등록하는 행위</li>
          <li>서비스를 이용하여 법령 또는 공서양속에 위반되는 콘텐츠를 생성, 게시, 유포하는 행위</li>
          <li>AI 생성 콘텐츠를 실제 사람이 작성한 것처럼 허위 표시하는 행위</li>
          <li>가짜 리뷰, 허위 후기, 조작된 평가를 생성하거나 게시하는 행위</li>
          <li>타인의 명예를 훼손하거나 권리를 침해하는 콘텐츠를 생성하는 행위</li>
          <li>의료법, 소비자기본법, 표시광고법, 저작권법 등 관련 법령을 위반하는 콘텐츠를 생성하는 행위</li>
          <li>서비스의 안정적 운영을 방해하는 행위 (과도한 요청, 봇 사용 등)</li>
          <li>회사의 사전 승인 없이 서비스를 이용한 영업 활동 또는 재판매</li>
          <li>서비스를 역공학, 디컴파일, 분해하거나 소스코드를 추출하는 행위</li>
          <li>계정을 타인에게 양도, 판매, 대여하는 행위</li>
          <li>회사의 지적재산권을 침해하는 행위</li>
          <li>기타 관련 법령에 위반되거나 선량한 풍속 기타 사회질서에 반하는 행위</li>
        </ol>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">제7조 (콘텐츠 사용에 대한 책임)</h3>
      <div className="bg-red-100 border-2 border-red-400 rounded-lg p-4 my-4">
        <p className="font-bold text-red-900 mb-2 text-lg">핵심 책임 조항</p>
        <ol className="list-decimal pl-5 space-y-3 text-red-800">
          <li>
            <strong>서비스를 통해 생성된 모든 콘텐츠의 검토, 수정, 사용, 게시, 배포에 대한
            모든 민형사상 법적 책임은 전적으로 이용자에게 있습니다.</strong>
          </li>
          <li>
            이용자는 생성된 콘텐츠를 사용하기 전 해당 콘텐츠가 관련 법령(의료법, 표시광고법,
            저작권법, 부정경쟁방지법, 정보통신망법 등)을 준수하는지 <strong>직접 확인할 의무</strong>가 있습니다.
          </li>
          <li>
            회사는 이용자가 생성한 콘텐츠의 적법성, 정확성, 완전성, 진실성을 <strong>보증하지 않습니다</strong>.
          </li>
          <li>
            콘텐츠 사용으로 인해 발생하는 <strong>모든 손해, 손실, 비용, 법적 책임</strong>(제3자의 청구,
            소송, 과태료, 벌금, 형사처벌 포함)은 이용자가 전적으로 부담합니다.
          </li>
          <li>
            이용자는 콘텐츠 사용으로 인해 회사에 발생하는 모든 손해, 비용, 청구에 대해
            회사를 <strong>면책하고 보상(Indemnify)</strong>할 의무가 있습니다.
          </li>
        </ol>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">제8조 (서비스 이용 제한 및 계약 해지)</h3>
      <ol className="list-decimal pl-5 space-y-2">
        <li>회사는 다음 각 호에 해당하는 경우 사전 통지 없이 서비스 이용을 제한하거나 계약을 해지할 수 있습니다:
          <ul className="list-disc pl-5 mt-2 space-y-1">
            <li>본 약관을 위반한 경우</li>
            <li>불법적인 목적으로 서비스를 이용한 경우</li>
            <li>타인의 권리를 침해하는 콘텐츠를 생성한 경우</li>
            <li>서비스 운영을 방해한 경우</li>
            <li>결제 대금을 미납한 경우</li>
            <li>기타 회사가 정한 이용조건을 위반한 경우</li>
          </ul>
        </li>
        <li>이용 제한 또는 계약 해지 시 이용자의 데이터는 삭제될 수 있으며, 회사는 이에 대해 책임지지 않습니다.</li>
        <li>위반 행위로 인한 이용 제한 시 기 결제한 금액은 환불되지 않습니다.</li>
      </ol>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">제9조 (서비스의 변경 및 중단)</h3>
      <ol className="list-decimal pl-5 space-y-2">
        <li>회사는 운영상, 기술상의 필요에 따라 서비스의 전부 또는 일부를 변경할 수 있습니다.</li>
        <li>회사는 다음 각 호의 경우 서비스 제공을 일시적으로 중단할 수 있습니다:
          <ul className="list-disc pl-5 mt-2 space-y-1">
            <li>시스템 정기 점검, 서버 증설 및 교체, 네트워크 불안정 등의 시스템 운영상 필요한 경우</li>
            <li>정전, 서비스 설비 장애, 서비스 이용 폭주 등으로 정상적인 서비스 제공이 불가능한 경우</li>
            <li>천재지변, 국가비상사태, 전쟁, 테러, 폭동, 전염병 등 불가항력적 사유가 발생한 경우</li>
            <li>제3자 API 서비스(OpenAI, Anthropic, Google 등)의 장애 또는 정책 변경이 있는 경우</li>
          </ul>
        </li>
        <li>회사는 사업 종료 등의 사유로 서비스를 종료할 수 있으며, 이 경우 30일 전에 공지합니다.</li>
      </ol>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">제10조 (손해배상의 제한)</h3>
      <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4 my-4">
        <ol className="list-decimal pl-5 space-y-2 text-yellow-800">
          <li>회사는 <strong>무료 서비스</strong> 이용과 관련하여 이용자에게 발생한 어떠한 손해에 대해서도 책임을 지지 않습니다.</li>
          <li><strong>유료 서비스</strong>의 경우에도 회사의 고의 또는 중대한 과실이 없는 한 손해배상 책임이 제한됩니다.</li>
          <li>회사의 손해배상 책임이 인정되는 경우에도 그 범위는 <strong>이용자가 지불한 최근 1개월 서비스 이용료를 초과하지 않습니다</strong>.</li>
          <li>회사는 <strong>간접적, 우연적, 특별, 결과적, 징벌적 손해</strong>에 대해서는 책임지지 않습니다.</li>
          <li>회사는 이용자가 서비스를 통해 기대하는 <strong>매출, 이익, 수익의 손실</strong>에 대해 책임지지 않습니다.</li>
          <li>이용자가 본 약관을 위반하여 회사에 손해를 끼친 경우, 이용자는 회사에 발생한 <strong>모든 손해, 비용, 법률 비용</strong>을 배상해야 합니다.</li>
        </ol>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">제11조 (면책조항)</h3>
      <ol className="list-decimal pl-5 space-y-2">
        <li>회사는 AI 생성 콘텐츠의 정확성, 신뢰성, 적법성, 완전성, 적시성을 보증하지 않습니다.</li>
        <li>회사는 이용자 간 또는 이용자와 제3자 간의 분쟁에 개입하지 않으며, 이로 인한 손해를 배상하지 않습니다.</li>
        <li>회사는 이용자의 귀책사유로 인한 서비스 이용 장애에 대해 책임을 지지 않습니다.</li>
        <li>회사는 제3자가 제공하는 서비스(AI API, 결제 시스템, 외부 플랫폼 등)의 장애에 대해 책임지지 않습니다.</li>
        <li>회사는 이용자가 서비스를 이용하여 발생시킨 법률 위반에 대해 어떠한 책임도 지지 않습니다.</li>
      </ol>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">제12조 (보상 및 면책 의무)</h3>
      <div className="bg-gray-100 p-4 rounded-lg">
        <p className="font-bold text-gray-800 mb-2">이용자의 보상(Indemnification) 의무</p>
        <p className="text-gray-700">
          이용자는 다음으로 인해 회사에 발생하는 모든 청구, 손해, 손실, 비용(합리적인 법률 비용 포함)에 대해
          회사를 면책하고 보상할 것에 동의합니다:
        </p>
        <ul className="list-disc pl-5 mt-2 space-y-1 text-gray-700">
          <li>이용자의 서비스 이용</li>
          <li>이용자가 생성, 게시, 배포한 콘텐츠</li>
          <li>이용자의 약관 위반</li>
          <li>이용자의 법률 위반</li>
          <li>이용자의 제3자 권리 침해</li>
        </ul>
      </div>
    </div>
  )
}

// 면책조항
function DisclaimerContent() {
  return (
    <div className="prose prose-sm max-w-none pt-4 text-gray-700">
      <div className="bg-red-100 border-2 border-red-400 rounded-lg p-4 mb-6">
        <h3 className="text-lg font-bold text-red-800 mb-2">핵심 면책사항</h3>
        <p className="text-red-700 font-semibold">
          본 서비스는 AI 기반 콘텐츠 생성 "도구"를 제공할 뿐이며, 생성된 콘텐츠의 사용 결과에 대해
          <strong>어떠한 법적 책임도 지지 않습니다</strong>. 모든 콘텐츠의 검토, 수정, 게시 결정 및 그에 따른
          민형사상 법적 책임은 <strong>전적으로 이용자에게</strong> 있습니다.
        </p>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4">1. AI 생성 콘텐츠 관련 면책</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li><strong>정확성 미보증:</strong> AI가 생성한 콘텐츠는 사실과 다르거나, 오류를 포함하거나, 오래된 정보일 수 있습니다. 회사는 콘텐츠의 정확성, 완전성, 신뢰성, 적시성을 보증하지 않습니다.</li>
        <li><strong>적법성 미보증:</strong> 생성된 콘텐츠가 관련 법령(의료법, 저작권법, 표시광고법, 부정경쟁방지법 등)을 준수하는지 여부는 이용자가 직접 확인해야 합니다.</li>
        <li><strong>환각(Hallucination):</strong> AI는 실제로 존재하지 않는 정보를 사실처럼 생성할 수 있습니다(환각 현상). 이로 인한 문제는 이용자 책임입니다.</li>
        <li><strong>편향성:</strong> AI 생성 콘텐츠는 학습 데이터의 편향을 반영할 수 있습니다. 이로 인한 문제는 이용자 책임입니다.</li>
        <li><strong>사용 전 검토 의무:</strong> 이용자는 콘텐츠를 게시하거나 배포하기 전에 반드시 내용을 검토하고 필요시 전문가(변호사, 의사 등)의 자문을 받아야 합니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">2. 외부 플랫폼 이용 관련 면책</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li><strong>약관 준수 책임:</strong> 네이버, 인스타그램, 페이스북 등 외부 플랫폼에 콘텐츠를 게시하는 경우, 해당 플랫폼의 이용약관 준수는 이용자의 전적인 책임입니다.</li>
        <li><strong>계정 제재:</strong> 외부 플랫폼에서 콘텐츠 게시로 인해 발생하는 계정 정지, 저품질 판정, 제재, 손해 등에 대해 회사는 일체의 책임을 지지 않습니다.</li>
        <li><strong>API/정책 변경:</strong> 외부 플랫폼의 API 정책, 이용약관, 알고리즘 변경으로 인한 서비스 장애 또는 결과 변동에 대해 회사는 책임지지 않습니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">3. 마케팅 콘텐츠 관련 면책</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li><strong>광고 규정 준수:</strong> 마케팅 목적의 콘텐츠는 표시광고법, 의료법, 전자상거래법 등 관련 광고법을 준수해야 하며, 이에 대한 책임은 전적으로 이용자에게 있습니다.</li>
        <li><strong>과장/허위 광고:</strong> 서비스에서 생성된 콘텐츠가 과장되거나 허위일 수 있습니다. 이를 그대로 사용하여 발생하는 문제(과태료, 형사처벌 등)는 이용자 책임입니다.</li>
        <li><strong>비교/비방 광고:</strong> 타 업체, 제품, 서비스를 비교하거나 비방하는 콘텐츠로 인한 법적 분쟁은 이용자가 전적으로 책임집니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">4. 리뷰/후기 관련 면책</h3>
      <div className="bg-yellow-50 border-2 border-yellow-400 rounded-lg p-4 my-4">
        <p className="font-bold text-yellow-800 mb-2">중대한 법적 경고</p>
        <ul className="list-disc pl-5 space-y-2 text-yellow-800">
          <li>AI로 생성된 가상의 리뷰나 후기를 <strong>실제 고객 후기인 것처럼 게시하는 행위</strong>는 소비자기본법 제73조(과태료), 전자상거래법 제21조(허위·과장 광고), 부정경쟁방지법 제2조 제1호 차목(허위사실 유포) 위반에 해당할 수 있습니다.</li>
          <li>위반 시 <strong>5천만원 이하의 과태료</strong> 또는 <strong>2년 이하의 징역 또는 5천만원 이하의 벌금</strong>에 처해질 수 있습니다.</li>
          <li>리뷰 생성 기능은 <strong>참고용 초안 작성 목적</strong>으로만 제공됩니다. 이를 허위 후기로 사용하여 발생하는 모든 법적 책임은 이용자에게 있습니다.</li>
          <li>보상을 조건으로 한 리뷰 유도, 최소 별점 요구, 긍정 리뷰 강요는 <strong>리뷰 조작</strong>에 해당하며, 이에 대한 책임은 이용자에게 있습니다.</li>
        </ul>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">5. 손해배상 책임의 제한</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>회사는 서비스 이용과 관련하여 이용자에게 발생한 <strong>직접적, 간접적, 우연적, 특별, 결과적, 징벌적 손해</strong>에 대해 책임지지 않습니다.</li>
        <li>회사의 손해배상 책임이 인정되는 경우에도 그 범위는 <strong>이용자가 지불한 최근 1개월 서비스 이용료</strong>를 초과하지 않습니다.</li>
        <li>회사는 <strong>일실이익, 매출 손실, 사업 기회 손실, 데이터 손실</strong> 등에 대해 책임지지 않습니다.</li>
        <li>제3자가 이용자에게 제기하는 소송, 청구, 손해에 대해 회사는 책임지지 않으며, 이용자는 회사를 면책시켜야 합니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">6. 서비스 보증의 부인 (Disclaimer of Warranties)</h3>
      <div className="bg-gray-100 p-4 rounded-lg my-4">
        <p className="text-gray-800">
          본 서비스는 <strong>"있는 그대로(AS IS)"</strong> 및 <strong>"이용 가능한 상태로(AS AVAILABLE)"</strong> 제공됩니다.
          회사는 서비스에 대해 <strong>상품성, 특정 목적에의 적합성, 권리 비침해, 정확성, 신뢰성</strong> 등을 포함한
          명시적 또는 묵시적 어떠한 보증도 하지 않습니다.
        </p>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">7. 제3자 서비스 면책</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>회사는 제3자 API(OpenAI, Anthropic, Google, 네이버, Meta 등)의 성능, 가용성, 정확성, 정책에 대해 책임지지 않습니다.</li>
        <li>제3자 서비스의 변경, 중단, 종료로 인한 서비스 영향에 대해 회사는 책임지지 않습니다.</li>
        <li>결제 서비스(토스페이먼츠 등) 이용 중 발생하는 문제에 대해 회사는 책임지지 않습니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">8. 면책 동의</h3>
      <div className="bg-red-50 border border-red-300 rounded-lg p-4">
        <p className="font-bold text-red-800">
          본 서비스를 이용함으로써 이용자는 위의 모든 면책조항을 읽고 이해했으며,
          이에 <strong>법적 구속력 있게 동의</strong>한 것으로 간주됩니다.
          동의하지 않는 경우 서비스 이용을 즉시 중단하고 탈퇴해야 합니다.
        </p>
      </div>
    </div>
  )
}

// 개인정보처리방침
function PrivacyContent() {
  return (
    <div className="prose prose-sm max-w-none pt-4 text-gray-700">
      <h3 className="text-lg font-bold text-gray-900 mb-4">1. 개인정보의 수집 및 이용 목적</h3>
      <table className="w-full border-collapse border border-gray-300 my-4">
        <thead>
          <tr className="bg-gray-100">
            <th className="border border-gray-300 px-4 py-2 text-left">수집 목적</th>
            <th className="border border-gray-300 px-4 py-2 text-left">수집 항목</th>
            <th className="border border-gray-300 px-4 py-2 text-left">보유 기간</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td className="border border-gray-300 px-4 py-2">회원 가입 및 관리</td>
            <td className="border border-gray-300 px-4 py-2">이메일, 비밀번호, 이름</td>
            <td className="border border-gray-300 px-4 py-2">탈퇴 시까지</td>
          </tr>
          <tr>
            <td className="border border-gray-300 px-4 py-2">서비스 제공</td>
            <td className="border border-gray-300 px-4 py-2">병원명, 전문과목, 연락처</td>
            <td className="border border-gray-300 px-4 py-2">탈퇴 시까지</td>
          </tr>
          <tr>
            <td className="border border-gray-300 px-4 py-2">결제 처리</td>
            <td className="border border-gray-300 px-4 py-2">결제 정보, 거래 기록</td>
            <td className="border border-gray-300 px-4 py-2">5년 (전자상거래법)</td>
          </tr>
          <tr>
            <td className="border border-gray-300 px-4 py-2">서비스 이용 기록</td>
            <td className="border border-gray-300 px-4 py-2">IP, 접속 로그, 이용 기록</td>
            <td className="border border-gray-300 px-4 py-2">3개월~1년</td>
          </tr>
          <tr>
            <td className="border border-gray-300 px-4 py-2">마케팅 (동의 시)</td>
            <td className="border border-gray-300 px-4 py-2">이메일, 연락처</td>
            <td className="border border-gray-300 px-4 py-2">동의 철회 시까지</td>
          </tr>
        </tbody>
      </table>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">2. 개인정보의 제3자 제공</h3>
      <p>회사는 원칙적으로 이용자의 개인정보를 외부에 제공하지 않습니다. 다만, 다음의 경우에는 예외로 합니다:</p>
      <ul className="list-disc pl-5 space-y-2">
        <li>이용자가 사전에 동의한 경우</li>
        <li>법령의 규정에 의거하거나, 수사 목적으로 법령에 정해진 절차와 방법에 따라 수사기관의 요구가 있는 경우</li>
        <li>통계작성, 학술연구, 시장조사를 위해 특정 개인을 식별할 수 없는 형태로 제공하는 경우</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">3. 개인정보의 처리 위탁</h3>
      <table className="w-full border-collapse border border-gray-300 my-4">
        <thead>
          <tr className="bg-gray-100">
            <th className="border border-gray-300 px-4 py-2 text-left">수탁업체</th>
            <th className="border border-gray-300 px-4 py-2 text-left">위탁 업무</th>
            <th className="border border-gray-300 px-4 py-2 text-left">보유 기간</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td className="border border-gray-300 px-4 py-2">토스페이먼츠</td>
            <td className="border border-gray-300 px-4 py-2">결제 처리</td>
            <td className="border border-gray-300 px-4 py-2">위탁계약 종료 시</td>
          </tr>
          <tr>
            <td className="border border-gray-300 px-4 py-2">Amazon Web Services</td>
            <td className="border border-gray-300 px-4 py-2">데이터 저장 및 처리</td>
            <td className="border border-gray-300 px-4 py-2">위탁계약 종료 시</td>
          </tr>
          <tr>
            <td className="border border-gray-300 px-4 py-2">OpenAI / Anthropic / Google</td>
            <td className="border border-gray-300 px-4 py-2">AI 콘텐츠 생성</td>
            <td className="border border-gray-300 px-4 py-2">API 호출 시</td>
          </tr>
        </tbody>
      </table>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">4. 개인정보의 국외 이전</h3>
      <div className="bg-blue-50 border border-blue-300 rounded-lg p-4 my-4">
        <p className="text-blue-800">
          본 서비스는 AI 콘텐츠 생성을 위해 해외 서버(미국 등)에 위치한 AI 서비스 제공업체의 API를 이용합니다.
          이 과정에서 이용자가 입력한 정보(키워드, 주제 등)가 해외로 전송될 수 있습니다.
        </p>
        <ul className="list-disc pl-5 mt-2 space-y-1 text-blue-700">
          <li>이전 국가: 미국</li>
          <li>이전 항목: 콘텐츠 생성을 위한 입력 정보</li>
          <li>이전 목적: AI 콘텐츠 생성</li>
          <li>수탁업체: OpenAI, Anthropic, Google</li>
        </ul>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">5. 이용자의 권리</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>개인정보 열람 요구권</li>
        <li>개인정보 정정·삭제 요구권</li>
        <li>개인정보 처리 정지 요구권</li>
        <li>개인정보 이동권</li>
        <li>동의 철회권</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">6. 개인정보 자동 수집 장치</h3>
      <p>회사는 쿠키(Cookie)를 사용합니다. 쿠키는 웹사이트 운영에 이용되는 서버가 이용자의 브라우저에 보내는
        아주 작은 텍스트 파일로, 이용자의 컴퓨터 하드디스크에 저장됩니다.</p>
      <ul className="list-disc pl-5 space-y-2 mt-2">
        <li>쿠키 사용 목적: 로그인 상태 유지, 서비스 이용 분석</li>
        <li>쿠키 설정 거부 방법: 브라우저 설정에서 쿠키 차단 가능</li>
        <li>쿠키 거부 시 서비스 이용에 제한이 있을 수 있습니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">7. 개인정보보호 책임자</h3>
      <div className="bg-gray-100 p-4 rounded-lg">
        <p>성명: [담당자명]</p>
        <p>직책: 개인정보보호 책임자</p>
        <p>이메일: privacy@platonmarketing.com</p>
        <p className="mt-2 text-sm text-gray-500">
          기타 개인정보 침해 신고·상담: 개인정보침해신고센터 (privacy.kisa.or.kr / 국번없이 118)
        </p>
      </div>
    </div>
  )
}

// 의료정보 관련 고지
function MedicalContent() {
  return (
    <div className="prose prose-sm max-w-none pt-4 text-gray-700">
      <div className="bg-orange-100 border-2 border-orange-400 rounded-lg p-4 mb-6">
        <h3 className="text-lg font-bold text-orange-800 mb-2">의료법 관련 중요 고지</h3>
        <p className="text-orange-700">
          본 서비스에서 생성되는 의료 관련 콘텐츠는 <strong>의료 조언이 아니며</strong>,
          의료법에서 정한 의료행위에 해당하지 않습니다. 모든 의료 관련 결정은
          반드시 자격을 갖춘 의료 전문가와 상담 후 이루어져야 합니다.
        </p>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4">1. 의료 콘텐츠의 법적 성격</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>본 서비스에서 제공하는 의료 관련 정보는 <strong>일반적인 건강 정보</strong>로만 제공됩니다.</li>
        <li>AI 생성 콘텐츠는 <strong>진단, 치료, 처방의 대체가 될 수 없습니다</strong>.</li>
        <li>본 서비스는 <strong>의료기기법상 의료기기가 아닙니다</strong>.</li>
        <li>개인의 건강 상태에 따라 적용 여부가 달라질 수 있으므로 반드시 전문의와 상담하시기 바랍니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">2. 의료광고 관련 법적 요구사항</h3>
      <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4 my-4">
        <p className="font-bold text-yellow-800 mb-2">의료법 제56조 (의료광고의 금지 등)</p>
        <p className="text-yellow-800 text-sm">의료인, 의료기관이 의료광고를 하는 경우 다음 사항을 준수해야 합니다:</p>
        <ul className="list-disc pl-5 space-y-1 text-yellow-800 text-sm mt-2">
          <li>거짓, 과장된 내용의 광고 금지</li>
          <li>다른 의료기관과의 비교 광고 금지</li>
          <li>환자 치료 경험담 광고 금지</li>
          <li>수술 장면 등 환자 불안감 조성 광고 금지</li>
          <li>의료인의 기능, 진료 방법에 관한 광고 시 심의 필요</li>
          <li>신문, 방송 등을 통한 광고 시 사전 심의 필요</li>
        </ul>
        <p className="mt-3 text-yellow-900 font-bold">위반 시: 1년 이하의 징역 또는 1천만원 이하의 벌금</p>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">3. 의료법 제27조 (무면허 의료행위 금지)</h3>
      <div className="bg-red-50 border border-red-300 rounded-lg p-4 my-4">
        <p className="text-red-800">
          의료인이 아닌 자가 의료행위를 하는 것은 <strong>5년 이하의 징역 또는 5천만원 이하의 벌금</strong>에
          해당합니다. AI가 생성한 의료 정보를 통해 진단, 처방, 치료 조언을 하는 것은 무면허 의료행위로
          해석될 수 있습니다.
        </p>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">4. 금지되는 표현 예시</h3>
      <div className="bg-red-50 border border-red-300 rounded-lg p-4 my-4">
        <p className="font-bold text-red-800 mb-2">다음 표현은 의료광고에서 금지됩니다:</p>
        <ul className="list-disc pl-5 space-y-1 text-red-700">
          <li>"100% 완치", "반드시 효과가 있다", "부작용 없다"</li>
          <li>"국내 최초", "세계 유일", "최고의 기술", "최신 기술"</li>
          <li>"OO 환자 치료 성공", "OO 환자 경험담" (환자 추천글)</li>
          <li>"OO 병원보다 저렴", "가장 싼 가격" (비교 광고)</li>
          <li>수술 전후 사진 (심의 없이)</li>
          <li>"연예인 OO도 방문한 병원", 유명인 추천</li>
          <li>"의료진 00명 보유" (과장된 인력 표시)</li>
          <li>특정 약품명, 의료기기명 언급 (허가받지 않은 경우)</li>
        </ul>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">5. 이용자의 의무</h3>
      <ol className="list-decimal pl-5 space-y-2">
        <li><strong>의료광고 심의:</strong> 의료 관련 콘텐츠를 광고 목적으로 사용하는 경우, 대한의사협회 등 관련 기관의 광고 심의를 받아야 합니다.</li>
        <li><strong>금지 표현 확인:</strong> 의료법에서 금지하는 표현이 포함되지 않았는지 반드시 확인해야 합니다.</li>
        <li><strong>면허 정보 표시:</strong> 의료광고에는 의료기관명, 소재지, 전화번호, 의료인의 성명·면허 종류를 명시해야 합니다.</li>
        <li><strong>전문의 검토:</strong> 의료 정보의 정확성을 위해 반드시 해당 분야 전문의의 검토를 받을 것을 권장합니다.</li>
      </ol>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">6. 면책사항</h3>
      <div className="bg-gray-100 p-4 rounded-lg">
        <p>
          본 서비스는 콘텐츠 생성 도구만을 제공하며, 생성된 의료 관련 콘텐츠의 의료법 준수 여부에
          대한 책임은 <strong>전적으로 이용자에게</strong> 있습니다. 의료법 위반으로 인한 행정처분, 과태료,
          형사처벌 등 모든 법적 책임은 이용자가 부담합니다.
        </p>
      </div>
    </div>
  )
}

// AI 생성 콘텐츠 정책
function ContentPolicyContent() {
  return (
    <div className="prose prose-sm max-w-none pt-4 text-gray-700">
      <h3 className="text-lg font-bold text-gray-900 mb-4">1. AI 생성 콘텐츠의 특성 및 한계</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li><strong>자동 생성:</strong> 본 서비스의 콘텐츠는 인공지능(AI) 기술을 활용하여 자동으로 생성됩니다.</li>
        <li><strong>제한적 정확성:</strong> AI가 생성한 콘텐츠는 부정확하거나, 오래된 정보를 포함하거나, 완전히 허구일 수 있습니다.</li>
        <li><strong>환각(Hallucination):</strong> AI는 실제로 존재하지 않는 사실, 인물, 사건을 사실처럼 생성할 수 있습니다.</li>
        <li><strong>편향성:</strong> AI 모델은 학습 데이터에 포함된 편향을 반영할 수 있습니다.</li>
        <li><strong>저작권 불확실성:</strong> AI 생성 콘텐츠의 저작권 귀속에 대해서는 현행 법률상 명확하지 않은 부분이 있습니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">2. AI 생성 콘텐츠 표시 의무</h3>
      <div className="bg-blue-50 border border-blue-300 rounded-lg p-4 my-4">
        <p className="text-blue-800 font-bold">이용자는 AI 생성 콘텐츠를 외부에 게시할 때 다음 사항을 준수해야 합니다:</p>
        <ul className="list-disc pl-5 space-y-1 text-blue-700 mt-2">
          <li>AI 생성 콘텐츠임을 명시적으로 표시 (예: "이 글은 AI의 도움을 받아 작성되었습니다")</li>
          <li>실제 경험에 기반하지 않은 콘텐츠임을 고지</li>
          <li>마케팅 목적의 콘텐츠인 경우 "광고" 표시</li>
          <li>의료 정보의 경우 "의료 조언이 아님" 표시</li>
        </ul>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">3. 금지되는 콘텐츠</h3>
      <div className="bg-red-50 border border-red-300 rounded-lg p-4 my-4">
        <p className="font-bold text-red-800 mb-2">다음과 같은 콘텐츠 생성 및 사용은 금지됩니다:</p>
        <ul className="list-disc pl-5 space-y-1 text-red-700">
          <li>타인의 명예를 훼손하거나 모욕하는 콘텐츠</li>
          <li>허위사실을 유포하는 콘텐츠</li>
          <li>음란하거나 성인 콘텐츠</li>
          <li>폭력을 조장하거나 범죄를 유도하는 콘텐츠</li>
          <li>타인의 저작권, 상표권 등 지적재산권을 침해하는 콘텐츠</li>
          <li>개인정보를 무단으로 수집하거나 유포하는 콘텐츠</li>
          <li>특정 개인, 단체, 기업을 비방하는 콘텐츠</li>
          <li>사기, 피싱, 스팸 등 범죄에 이용되는 콘텐츠</li>
          <li>가짜 리뷰, 허위 후기, 조작된 평가</li>
          <li>딥페이크 또는 타인을 사칭하는 콘텐츠</li>
          <li>혐오, 차별, 괴롭힘을 조장하는 콘텐츠</li>
          <li>아동 착취 또는 학대 관련 콘텐츠</li>
        </ul>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">4. 콘텐츠 소유권</h3>
      <ol className="list-decimal pl-5 space-y-2">
        <li>이용자가 입력한 정보(키워드, 주제 등)의 소유권은 이용자에게 있습니다.</li>
        <li>AI가 생성한 콘텐츠에 대해 회사는 별도의 권리를 주장하지 않습니다.</li>
        <li>다만, AI 생성 콘텐츠의 저작권 보호 여부는 현행법상 불명확하며, 제3자의 저작권을 침해할 수 있습니다.</li>
        <li>이용자는 생성된 콘텐츠 사용으로 인한 저작권 분쟁에 대해 전적인 책임을 집니다.</li>
      </ol>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">5. 콘텐츠 모니터링</h3>
      <p>
        회사는 서비스 운영 및 법적 요구사항 준수를 위해 생성된 콘텐츠를 모니터링할 수 있습니다.
        불법적이거나 약관을 위반하는 콘텐츠가 발견될 경우, 회사는 해당 콘텐츠 삭제 및
        서비스 이용 제한 조치를 취할 수 있으며, 필요시 관계 기관에 신고할 수 있습니다.
      </p>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">6. 이용자 책임</h3>
      <div className="bg-red-50 border border-red-300 rounded-lg p-4 my-4">
        <ul className="list-disc pl-5 space-y-2 text-red-700">
          <li><strong>검토 의무:</strong> 이용자는 생성된 콘텐츠를 게시하기 전 반드시 내용을 검토해야 합니다.</li>
          <li><strong>사실 확인:</strong> 이용자는 콘텐츠에 포함된 사실관계를 직접 확인해야 합니다.</li>
          <li><strong>법적 검토:</strong> 콘텐츠가 관련 법령을 준수하는지 확인할 책임은 이용자에게 있습니다.</li>
          <li><strong>전문가 자문:</strong> 필요시 변호사, 의사 등 전문가의 자문을 받아야 합니다.</li>
          <li><strong>손해 배상:</strong> 콘텐츠 사용으로 인해 발생하는 모든 손해를 배상할 책임이 있습니다.</li>
        </ul>
      </div>
    </div>
  )
}

// 외부 플랫폼 이용 안내
function PlatformContent() {
  return (
    <div className="prose prose-sm max-w-none pt-4 text-gray-700">
      <h3 className="text-lg font-bold text-gray-900 mb-4">1. 외부 플랫폼 연동 서비스</h3>
      <p>본 서비스는 다음 외부 플랫폼과의 연동 기능을 제공합니다:</p>
      <ul className="list-disc pl-5 space-y-2">
        <li>네이버 블로그</li>
        <li>Instagram</li>
        <li>Facebook</li>
        <li>기타 회사가 추가로 지원하는 플랫폼</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">2. 플랫폼 약관 준수 의무</h3>
      <div className="bg-yellow-50 border-2 border-yellow-400 rounded-lg p-4 my-4">
        <p className="font-bold text-yellow-800 mb-2">중요 법적 고지</p>
        <p className="text-yellow-700">
          각 외부 플랫폼은 자체적인 이용약관 및 커뮤니티 가이드라인을 운영하고 있습니다.
          <strong>이용자는 해당 플랫폼의 약관을 준수해야 할 법적 의무가 있으며</strong>,
          약관 위반으로 인한 모든 법적 책임 및 결과는 전적으로 이용자에게 있습니다.
        </p>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">3. 네이버 플랫폼 이용 시 주의사항</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li><strong>자동화 제한:</strong> 네이버는 자동화된 콘텐츠 생성 및 대량 게시를 제한합니다. 위반 시 계정이 정지될 수 있습니다.</li>
        <li><strong>스팸 정책:</strong> 동일하거나 유사한 콘텐츠의 반복 게시는 스팸으로 분류되어 저품질 판정을 받을 수 있습니다.</li>
        <li><strong>광고성 콘텐츠:</strong> 상업적 목적의 콘텐츠는 네이버 광고 정책을 준수해야 합니다.</li>
        <li><strong>계정 제재:</strong> 약관 위반 시 블로그 저품질, 검색 제외, 계정 정지 등의 제재를 받을 수 있습니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">4. Meta 플랫폼 (Instagram/Facebook) 이용 시 주의사항</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li><strong>커뮤니티 가이드라인:</strong> Meta의 커뮤니티 표준을 준수해야 합니다.</li>
        <li><strong>자동화 정책:</strong> Meta는 자동화된 콘텐츠 게시에 대해 엄격한 정책을 시행합니다.</li>
        <li><strong>광고 표시:</strong> 광고성 콘텐츠는 "Paid partnership" 또는 "#광고" 태그를 포함해야 합니다.</li>
        <li><strong>API 이용약관:</strong> Meta API 이용약관을 준수해야 하며, 위반 시 API 접근이 제한될 수 있습니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">5. 계정 연동 시 주의사항</h3>
      <ol className="list-decimal pl-5 space-y-2">
        <li>외부 플랫폼 계정 연동 시 OAuth 등 표준 인증 방식을 사용합니다.</li>
        <li>이용자는 자신의 계정 정보를 안전하게 관리할 책임이 있습니다.</li>
        <li>회사는 이용자의 외부 플랫폼 계정 비밀번호를 저장하지 않습니다.</li>
        <li>계정 연동으로 인한 보안 사고에 대해 회사는 책임지지 않습니다.</li>
      </ol>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">6. 면책사항</h3>
      <div className="bg-gray-100 p-4 rounded-lg">
        <ul className="list-disc pl-5 space-y-2">
          <li>외부 플랫폼의 정책 변경, 서비스 장애, API 변경 등으로 인한 서비스 중단에 대해 회사는 책임지지 않습니다.</li>
          <li>이용자의 외부 플랫폼 약관 위반으로 인한 계정 정지, 콘텐츠 삭제, 저품질 판정, 검색 제외 등에 대해 회사는 일체의 책임을 지지 않습니다.</li>
          <li>외부 플랫폼과의 분쟁은 해당 플랫폼과 이용자 간에 직접 해결해야 합니다.</li>
        </ul>
      </div>
    </div>
  )
}

// 저작권 및 지적재산권
function CopyrightContent() {
  return (
    <div className="prose prose-sm max-w-none pt-4 text-gray-700">
      <h3 className="text-lg font-bold text-gray-900 mb-4">1. 회사의 지적재산권</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>서비스의 소프트웨어, 디자인, 로고, 상표, 콘텐츠 등 모든 지적재산권은 회사에 귀속됩니다.</li>
        <li>이용자는 회사의 사전 서면 동의 없이 이를 복제, 수정, 배포, 판매할 수 없습니다.</li>
        <li>서비스를 역공학, 디컴파일, 분해하거나 소스코드를 추출하는 행위는 금지됩니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">2. AI 생성 콘텐츠의 저작권</h3>
      <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4 my-4">
        <p className="font-bold text-yellow-800 mb-2">저작권 관련 주의사항</p>
        <ul className="list-disc pl-5 space-y-2 text-yellow-800">
          <li>AI 생성 콘텐츠의 저작권 보호 여부는 현행 저작권법상 명확하지 않습니다.</li>
          <li>AI가 학습한 데이터에 포함된 저작물의 저작권 문제가 발생할 수 있습니다.</li>
          <li>AI 생성 콘텐츠가 기존 저작물과 유사할 경우 저작권 침해 분쟁이 발생할 수 있습니다.</li>
          <li>이러한 저작권 관련 분쟁에 대한 책임은 전적으로 이용자에게 있습니다.</li>
        </ul>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">3. 이용자 입력 정보의 저작권</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>이용자가 서비스에 입력한 정보(키워드, 주제, 텍스트 등)의 저작권은 이용자에게 있습니다.</li>
        <li>이용자는 회사에 해당 정보를 서비스 제공 목적으로 사용할 수 있는 비독점적 라이선스를 부여합니다.</li>
        <li>이용자는 입력 정보가 제3자의 저작권을 침해하지 않음을 보증합니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">4. 저작권 침해 신고</h3>
      <p>
        본 서비스에서 생성된 콘텐츠가 귀하의 저작권을 침해한다고 생각되는 경우,
        legal@platonmarketing.com으로 다음 정보와 함께 연락해 주시기 바랍니다:
      </p>
      <ul className="list-disc pl-5 space-y-2 mt-2">
        <li>저작권 소유자 또는 대리인의 서명</li>
        <li>침해된 저작물의 설명</li>
        <li>침해 콘텐츠의 위치</li>
        <li>연락처 정보</li>
        <li>선의의 신고임을 확인하는 진술</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">5. 상표권</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>"닥터보이스 프로", "플라톤마케팅" 및 관련 로고는 회사의 상표입니다.</li>
        <li>이용자는 회사의 사전 서면 동의 없이 이를 사용할 수 없습니다.</li>
        <li>이용자가 생성한 콘텐츠에 제3자의 상표를 무단 사용하여 발생하는 분쟁은 이용자 책임입니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">6. 부정경쟁방지법 관련</h3>
      <div className="bg-red-50 border border-red-300 rounded-lg p-4 my-4">
        <p className="font-bold text-red-800 mb-2">금지 행위</p>
        <ul className="list-disc pl-5 space-y-1 text-red-700">
          <li>타인의 상품 또는 영업과 혼동을 일으키는 콘텐츠 생성</li>
          <li>타인의 성명, 상호, 표지를 무단 사용하는 콘텐츠 생성</li>
          <li>타인의 영업비밀을 침해하는 콘텐츠 생성</li>
          <li>타인의 아이디어를 부정하게 취득하여 사용하는 행위</li>
          <li>경쟁사에 대한 허위 사실 유포</li>
        </ul>
        <p className="mt-3 text-red-900">위반 시: 부정경쟁방지법에 따른 민형사상 책임</p>
      </div>
    </div>
  )
}

// 전자상거래 및 환불 정책
function EcommerceContent() {
  return (
    <div className="prose prose-sm max-w-none pt-4 text-gray-700">
      <h3 className="text-lg font-bold text-gray-900 mb-4">1. 결제 및 요금</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>유료 서비스의 요금은 서비스 화면에 표시된 가격을 기준으로 합니다.</li>
        <li>모든 가격은 부가가치세(VAT)가 포함된 금액입니다.</li>
        <li>회사는 요금을 변경할 수 있으며, 변경 시 사전에 공지합니다.</li>
        <li>결제 수단: 신용카드, 체크카드, 계좌이체, 가상계좌 등</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">2. 구독 서비스</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>구독 서비스는 월간 또는 연간 단위로 자동 갱신됩니다.</li>
        <li>자동 갱신을 원하지 않는 경우, 갱신일 24시간 전까지 해지해야 합니다.</li>
        <li>구독 기간 중 요금제 변경 시, 변경된 요금제는 다음 결제일부터 적용됩니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">3. 청약 철회 및 환불</h3>
      <div className="bg-blue-50 border border-blue-300 rounded-lg p-4 my-4">
        <p className="font-bold text-blue-800 mb-2">전자상거래법에 따른 청약 철회</p>
        <ul className="list-disc pl-5 space-y-2 text-blue-800">
          <li>이용자는 구매일로부터 <strong>7일 이내</strong>에 청약 철회를 요청할 수 있습니다.</li>
          <li>단, 다음의 경우 청약 철회가 제한됩니다:
            <ul className="list-disc pl-5 mt-1">
              <li>서비스를 이용하여 콘텐츠를 생성한 경우</li>
              <li>크레딧을 사용한 경우</li>
              <li>디지털 콘텐츠의 제공이 시작된 경우 (단, 사전에 이에 대한 동의를 받은 경우)</li>
            </ul>
          </li>
        </ul>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">4. 환불 정책</h3>
      <table className="w-full border-collapse border border-gray-300 my-4">
        <thead>
          <tr className="bg-gray-100">
            <th className="border border-gray-300 px-4 py-2 text-left">구분</th>
            <th className="border border-gray-300 px-4 py-2 text-left">환불 조건</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td className="border border-gray-300 px-4 py-2">서비스 미사용</td>
            <td className="border border-gray-300 px-4 py-2">결제 후 7일 이내, 서비스 미사용 시 전액 환불</td>
          </tr>
          <tr>
            <td className="border border-gray-300 px-4 py-2">서비스 사용</td>
            <td className="border border-gray-300 px-4 py-2">사용 기간/크레딧에 비례하여 환불 (수수료 10% 공제)</td>
          </tr>
          <tr>
            <td className="border border-gray-300 px-4 py-2">7일 경과</td>
            <td className="border border-gray-300 px-4 py-2">환불 불가 (단, 서비스 장애 등 회사 귀책 사유 시 예외)</td>
          </tr>
          <tr>
            <td className="border border-gray-300 px-4 py-2">약관 위반으로 인한 해지</td>
            <td className="border border-gray-300 px-4 py-2">환불 불가</td>
          </tr>
        </tbody>
      </table>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">5. 크레딧 정책</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>크레딧은 구매 후 1년간 유효합니다.</li>
        <li>사용하지 않은 크레딧은 유효기간 경과 후 소멸됩니다.</li>
        <li>크레딧은 타인에게 양도, 판매할 수 없습니다.</li>
        <li>크레딧 환불은 미사용 크레딧에 한해 수수료 10%를 공제 후 가능합니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">6. 세금계산서 및 영수증</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>세금계산서는 결제 완료 후 요청 시 발행됩니다.</li>
        <li>현금영수증은 결제 시 요청할 수 있습니다.</li>
        <li>세금계산서 발행 요청: billing@platonmarketing.com</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">7. 사업자 정보</h3>
      <div className="bg-gray-100 p-4 rounded-lg">
        <p>상호: 플라톤마케팅</p>
        <p>대표자: [대표자명]</p>
        <p>사업자등록번호: [사업자번호]</p>
        <p>통신판매업신고번호: [신고번호]</p>
        <p>주소: [사업장 주소]</p>
        <p>고객센터: support@platonmarketing.com</p>
      </div>
    </div>
  )
}

// 명예훼손 및 불법콘텐츠
function DefamationContent() {
  return (
    <div className="prose prose-sm max-w-none pt-4 text-gray-700">
      <h3 className="text-lg font-bold text-gray-900 mb-4">1. 명예훼손 관련 법적 책임</h3>
      <div className="bg-red-50 border border-red-300 rounded-lg p-4 my-4">
        <p className="font-bold text-red-800 mb-2">형법 및 정보통신망법</p>
        <ul className="list-disc pl-5 space-y-2 text-red-700">
          <li><strong>형법 제307조 (명예훼손):</strong> 공연히 사실 또는 허위의 사실을 적시하여 타인의 명예를 훼손한 자는 2년 이하의 징역 또는 500만원 이하의 벌금</li>
          <li><strong>형법 제311조 (모욕):</strong> 공연히 사람을 모욕한 자는 1년 이하의 징역 또는 200만원 이하의 벌금</li>
          <li><strong>정보통신망법 제70조:</strong> 정보통신망을 통해 명예를 훼손한 자는 3년 이하의 징역 또는 3천만원 이하의 벌금</li>
          <li>AI 생성 콘텐츠를 이용한 명예훼손도 동일하게 처벌됩니다.</li>
        </ul>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">2. 허위사실 유포</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>AI가 생성한 허위 사실을 사실인 것처럼 유포하는 행위는 명예훼손죄에 해당합니다.</li>
        <li>특히 AI의 "환각(Hallucination)" 현상으로 생성된 허위 정보 유포 시 이용자가 책임집니다.</li>
        <li>기업, 단체에 대한 허위사실 유포는 업무방해죄, 신용훼손죄에도 해당할 수 있습니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">3. 개인정보 침해</h3>
      <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4 my-4">
        <p className="font-bold text-yellow-800 mb-2">개인정보보호법 위반</p>
        <ul className="list-disc pl-5 space-y-2 text-yellow-800">
          <li>타인의 개인정보를 무단으로 수집, 이용, 유출하는 콘텐츠 생성 금지</li>
          <li>타인의 동의 없이 성명, 연락처, 주소 등을 포함한 콘텐츠 생성 금지</li>
          <li>위반 시: 5년 이하의 징역 또는 5천만원 이하의 벌금</li>
        </ul>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">4. 업무방해 및 위계</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li><strong>형법 제314조 (업무방해):</strong> 허위 사실을 유포하여 타인의 업무를 방해한 자는 5년 이하의 징역 또는 1,500만원 이하의 벌금</li>
        <li>AI 생성 가짜 리뷰로 경쟁사 업무를 방해하는 행위 포함</li>
        <li>위계에 의한 업무방해도 동일하게 처벌</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">5. 사기 및 기망</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li><strong>형법 제347조 (사기):</strong> 사람을 기망하여 재물을 편취한 자는 10년 이하의 징역 또는 2천만원 이하의 벌금</li>
        <li>AI 생성 허위 콘텐츠를 이용한 사기 행위 포함</li>
        <li>가짜 리뷰를 통한 소비자 기만도 사기에 해당할 수 있음</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">6. 신고 및 대응</h3>
      <div className="bg-gray-100 p-4 rounded-lg">
        <p className="font-bold text-gray-800 mb-2">불법 콘텐츠 신고</p>
        <p className="text-gray-700">
          본 서비스에서 생성된 콘텐츠로 인해 권리를 침해당한 경우, 다음으로 신고해 주시기 바랍니다:
        </p>
        <ul className="list-disc pl-5 mt-2 space-y-1 text-gray-700">
          <li>이메일: legal@platonmarketing.com</li>
          <li>필요 정보: 침해 사실, 증거 자료, 연락처, 본인 확인 정보</li>
        </ul>
        <p className="mt-2 text-gray-600 text-sm">
          회사는 신고 접수 후 24시간 이내에 임시 조치를 취하고,
          법률에 따라 필요한 경우 관계 기관에 협조합니다.
        </p>
      </div>
    </div>
  )
}

// 계정 및 보안 정책
function AccountContent() {
  return (
    <div className="prose prose-sm max-w-none pt-4 text-gray-700">
      <h3 className="text-lg font-bold text-gray-900 mb-4">1. 계정 생성 및 관리</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>만 14세 이상만 서비스에 가입할 수 있습니다.</li>
        <li>실명과 정확한 정보로 가입해야 합니다.</li>
        <li>하나의 이메일 주소로 하나의 계정만 생성할 수 있습니다.</li>
        <li>계정 정보의 정확성 유지는 이용자의 책임입니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">2. 계정 보안</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>이용자는 자신의 계정과 비밀번호를 안전하게 관리할 책임이 있습니다.</li>
        <li>계정 정보가 유출된 경우 즉시 회사에 통보해야 합니다.</li>
        <li>계정 도용이나 무단 사용으로 인한 손해는 이용자가 책임집니다.</li>
        <li>회사는 2단계 인증 등 추가 보안 수단을 제공할 수 있습니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">3. 금지되는 계정 행위</h3>
      <div className="bg-red-50 border border-red-300 rounded-lg p-4 my-4">
        <ul className="list-disc pl-5 space-y-2 text-red-700">
          <li>계정을 타인에게 양도, 판매, 대여하는 행위</li>
          <li>타인의 계정을 무단으로 사용하는 행위</li>
          <li>여러 개의 계정을 부정하게 생성하는 행위</li>
          <li>계정 정보를 허위로 등록하는 행위</li>
          <li>자동화 도구를 이용한 계정 생성</li>
        </ul>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">4. 계정 정지 및 해지</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>약관 위반 시 사전 통지 없이 계정이 정지될 수 있습니다.</li>
        <li>정지된 계정의 데이터는 복구되지 않을 수 있습니다.</li>
        <li>이용자는 언제든지 계정을 해지(탈퇴)할 수 있습니다.</li>
        <li>탈퇴 시 개인정보는 관련 법령에 따라 일정 기간 보관 후 파기됩니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">5. 휴면 계정</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>12개월 이상 로그인하지 않은 계정은 휴면 계정으로 전환됩니다.</li>
        <li>휴면 계정의 개인정보는 분리 보관됩니다.</li>
        <li>휴면 계정은 본인 인증 후 복구할 수 있습니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">6. 데이터 백업</h3>
      <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4 my-4">
        <p className="font-bold text-yellow-800 mb-2">중요 안내</p>
        <p className="text-yellow-700">
          회사는 이용자의 데이터를 백업하기 위해 합리적인 노력을 기울이지만,
          <strong>데이터의 보존을 보증하지 않습니다</strong>.
          이용자는 중요한 콘텐츠를 자체적으로 백업할 것을 권장합니다.
        </p>
      </div>
    </div>
  )
}

// 제3자 서비스 및 API
function ThirdPartyContent() {
  return (
    <div className="prose prose-sm max-w-none pt-4 text-gray-700">
      <h3 className="text-lg font-bold text-gray-900 mb-4">1. 제3자 AI 서비스</h3>
      <p>본 서비스는 다음 제3자 AI 서비스를 이용합니다:</p>
      <table className="w-full border-collapse border border-gray-300 my-4">
        <thead>
          <tr className="bg-gray-100">
            <th className="border border-gray-300 px-4 py-2 text-left">서비스</th>
            <th className="border border-gray-300 px-4 py-2 text-left">제공사</th>
            <th className="border border-gray-300 px-4 py-2 text-left">용도</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td className="border border-gray-300 px-4 py-2">GPT API</td>
            <td className="border border-gray-300 px-4 py-2">OpenAI (미국)</td>
            <td className="border border-gray-300 px-4 py-2">텍스트 생성</td>
          </tr>
          <tr>
            <td className="border border-gray-300 px-4 py-2">Claude API</td>
            <td className="border border-gray-300 px-4 py-2">Anthropic (미국)</td>
            <td className="border border-gray-300 px-4 py-2">텍스트 생성</td>
          </tr>
          <tr>
            <td className="border border-gray-300 px-4 py-2">Gemini API</td>
            <td className="border border-gray-300 px-4 py-2">Google (미국)</td>
            <td className="border border-gray-300 px-4 py-2">텍스트 생성</td>
          </tr>
        </tbody>
      </table>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">2. 제3자 서비스 이용약관</h3>
      <div className="bg-blue-50 border border-blue-300 rounded-lg p-4 my-4">
        <p className="text-blue-800">
          이용자는 본 서비스 이용 시 제3자 서비스의 이용약관에도 동의한 것으로 간주됩니다:
        </p>
        <ul className="list-disc pl-5 mt-2 space-y-1 text-blue-700">
          <li>OpenAI Terms of Use: https://openai.com/policies/terms-of-use</li>
          <li>Anthropic Acceptable Use Policy: https://www.anthropic.com/legal/aup</li>
          <li>Google AI Terms of Service: https://ai.google.dev/terms</li>
        </ul>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">3. 제3자 서비스 관련 면책</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>회사는 제3자 AI 서비스의 성능, 정확성, 가용성에 대해 책임지지 않습니다.</li>
        <li>제3자 서비스의 약관 변경, 가격 변경, 서비스 중단에 대해 회사는 책임지지 않습니다.</li>
        <li>제3자 서비스의 장애로 인한 서비스 중단에 대해 회사는 책임지지 않습니다.</li>
        <li>이용자의 입력 정보가 제3자 서비스로 전송되며, 이에 대한 책임은 이용자에게 있습니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">4. 결제 서비스</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>결제 처리: 토스페이먼츠</li>
        <li>결제 과정에서의 오류, 분쟁은 해당 결제 서비스 제공자의 약관에 따릅니다.</li>
        <li>결제 정보는 회사가 직접 저장하지 않으며, 결제 서비스 제공자가 관리합니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">5. 외부 링크</h3>
      <p>
        서비스 내에 포함된 외부 웹사이트 링크는 정보 제공 목적으로만 제공됩니다.
        회사는 외부 웹사이트의 콘텐츠, 정확성, 적법성에 대해 책임지지 않습니다.
      </p>
    </div>
  )
}

// 국제 이용 및 규제
function InternationalContent() {
  return (
    <div className="prose prose-sm max-w-none pt-4 text-gray-700">
      <h3 className="text-lg font-bold text-gray-900 mb-4">1. 서비스 제공 지역</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>본 서비스는 대한민국에서 운영됩니다.</li>
        <li>대한민국 외의 지역에서의 서비스 이용은 해당 지역의 법률을 준수해야 합니다.</li>
        <li>일부 지역에서는 서비스 이용이 제한될 수 있습니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">2. 준거법</h3>
      <div className="bg-blue-50 border border-blue-300 rounded-lg p-4 my-4">
        <p className="text-blue-800">
          본 약관의 해석 및 적용, 서비스 이용과 관련된 모든 분쟁은
          <strong>대한민국 법률</strong>에 따라 규율됩니다.
          이용자가 다른 국가에서 서비스를 이용하더라도 대한민국 법률이 적용됩니다.
        </p>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">3. 수출 규제</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>본 서비스는 대한민국 및 미국의 수출 규제법의 적용을 받을 수 있습니다.</li>
        <li>이용자는 서비스를 수출 제한 국가에서 이용하거나, 금지된 목적으로 사용해서는 안 됩니다.</li>
        <li>수출 규제 위반으로 인한 법적 책임은 이용자에게 있습니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">4. 데이터의 국외 이전</h3>
      <ul className="list-disc pl-5 space-y-2">
        <li>서비스 이용 시 입력한 정보는 AI 처리를 위해 미국 등 해외로 전송될 수 있습니다.</li>
        <li>해당 국가의 데이터 보호 수준이 대한민국과 다를 수 있습니다.</li>
        <li>서비스 이용은 이러한 데이터 이전에 대한 동의로 간주됩니다.</li>
      </ul>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">5. GDPR 관련 (EU 이용자)</h3>
      <div className="bg-gray-100 p-4 rounded-lg">
        <p className="text-gray-700">
          EU 거주자의 경우 GDPR(일반개인정보보호규정)에 따른 추가적인 권리가 있을 수 있습니다.
          관련 문의는 privacy@platonmarketing.com으로 연락해 주시기 바랍니다.
        </p>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">6. 언어</h3>
      <p>
        본 약관의 공식 언어는 한국어입니다. 다른 언어로 번역된 약관과 한국어 약관 간에
        불일치가 있는 경우, 한국어 약관이 우선합니다.
      </p>
    </div>
  )
}

// 분쟁 해결 및 관할
function DisputeContent() {
  return (
    <div className="prose prose-sm max-w-none pt-4 text-gray-700">
      <h3 className="text-lg font-bold text-gray-900 mb-4">1. 준거법</h3>
      <p>
        본 약관의 해석 및 적용, 회사와 이용자 간의 분쟁에 대해서는
        <strong>대한민국 법률</strong>이 적용됩니다.
      </p>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">2. 관할 법원</h3>
      <div className="bg-blue-50 border border-blue-300 rounded-lg p-4 my-4">
        <p className="text-blue-800">
          서비스 이용과 관련하여 회사와 이용자 간에 발생한 분쟁에 대해서는
          <strong>서울중앙지방법원</strong>을 전속적 합의관할 법원으로 합니다.
        </p>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">3. 집단소송 포기</h3>
      <div className="bg-red-50 border-2 border-red-400 rounded-lg p-4 my-4">
        <p className="font-bold text-red-800 mb-2">중요한 법적 권리 포기</p>
        <p className="text-red-700">
          이용자는 본 서비스 이용과 관련된 모든 분쟁을 <strong>개별적으로만</strong> 해결하는 것에 동의합니다.
          이용자는 집단소송, 대표소송, 또는 다른 이용자와 함께하는 어떠한 형태의
          집단적 법적 절차에도 참여하지 않을 것에 동의합니다.
        </p>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">4. 분쟁 해결 절차</h3>
      <ol className="list-decimal pl-5 space-y-2">
        <li><strong>고객 서비스:</strong> 먼저 support@platonmarketing.com으로 문의하여 문제 해결을 시도합니다.</li>
        <li><strong>내부 분쟁 해결:</strong> 고객 서비스로 해결되지 않는 경우, 회사의 분쟁 해결 담당자에게 서면으로 분쟁을 제기합니다.</li>
        <li><strong>조정:</strong> 내부 절차로 해결되지 않는 경우, 한국인터넷진흥원(KISA) 또는 한국소비자원의 분쟁 조정을 신청할 수 있습니다.</li>
        <li><strong>소송:</strong> 조정이 성립하지 않는 경우, 서울중앙지방법원에 소송을 제기할 수 있습니다.</li>
      </ol>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">5. 소멸시효</h3>
      <p>
        이용자는 청구의 원인이 발생한 날로부터 <strong>1년 이내</strong>에
        회사에 대한 모든 청구를 제기해야 합니다.
        이 기간이 경과한 후에는 청구가 영구적으로 금지됩니다.
      </p>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">6. 분쟁 해결 기관</h3>
      <div className="bg-gray-100 p-4 rounded-lg">
        <ul className="list-disc pl-5 space-y-2">
          <li>한국인터넷진흥원(KISA): 국번없이 118</li>
          <li>한국소비자원: 국번없이 1372</li>
          <li>개인정보침해신고센터: privacy.kisa.or.kr</li>
          <li>대한상사중재원: www.kcab.or.kr</li>
        </ul>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">7. 권리의 비포기</h3>
      <p>
        회사가 본 약관의 특정 조항을 집행하지 않더라도, 이는 해당 조항 또는
        다른 조항을 집행할 권리를 포기한 것으로 해석되지 않습니다.
      </p>

      <h3 className="text-lg font-bold text-gray-900 mb-4 mt-6">8. 분리가능성</h3>
      <p>
        본 약관의 일부 조항이 무효하거나 집행 불가능한 것으로 판명되더라도,
        나머지 조항은 완전한 효력을 유지합니다.
      </p>
    </div>
  )
}
