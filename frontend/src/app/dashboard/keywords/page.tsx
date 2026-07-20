import { KeywordBatchManager } from '@/components/keyword-batch/keyword-batch-manager';

export const metadata = {
  title: '키워드 대량 생성 | 닥터보이스 프로',
};

export default function KeywordBatchPage() {
  return (
    <div className="container mx-auto max-w-5xl py-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">키워드 대량 생성</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          키워드 엑셀을 올리면 Gemini 가 키워드마다 글을 씁니다. 글 한 편마다 새 대화로
          시작하므로 앞 글의 영향을 받지 않습니다.
        </p>
      </div>
      <KeywordBatchManager />
    </div>
  );
}
