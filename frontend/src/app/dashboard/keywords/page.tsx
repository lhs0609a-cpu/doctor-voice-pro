import { KeywordBatchManager } from '@/components/keyword-batch/keyword-batch-manager';
import { PageHeader } from '@/components/app-shell/page-header';

export const metadata = {
  title: '키워드 대량 생성 | 닥터보이스 프로',
};

export default function KeywordBatchPage() {
  return (
    <div>
      <PageHeader
        title="키워드 대량 생성"
        description="키워드 엑셀을 올리면 Gemini 가 키워드마다 새 대화로 글을 씁니다. 앞 글의 영향을 받지 않습니다."
      />
      <KeywordBatchManager />
    </div>
  );
}
