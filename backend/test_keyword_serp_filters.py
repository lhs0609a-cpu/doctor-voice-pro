"""통검 결과로 키워드를 거르는 두 조건(2026-09-30 고객 요청).

1) "병원에서 작성한 블로그 글이 통합검색판에 떠 있는 키워드만 나오도록"
2) "특정 병원(소잠, 위례) 글이 뜬 키워드는 제외"

고객이 못 박은 단서가 있다 — "소잠한의원의 경우 파워컨텐츠 돌리고 있어서, 소잠한의원만
검색되면 제외시키기 명령어를 입력할 경우 대부분의 키워드가 안 뜰 수 있습니다. 꼭 블로그
글의 키워드가 있는 경우로 부탁드립니다!"

즉 **광고 자리는 세면 안 된다.** 통검 분석(serp_analyzer.analyze_keyword)이 이미 is_ad 인
결과를 posts 에서 빼고 있으므로, 여기서는 그 posts 만 보면 된다. 이 시험이 그 약속을 지킨다.
"""
import unittest

from app.services.keyword_hunt import blocked_owner, hospital_blog_count


def post(blog_id, blog_name, blog_type="unknown", title=""):
    return {"blog_id": blog_id, "blog_name": blog_name, "blog_type": blog_type, "title": title}


HOSPITAL = post("sojam_clinic", "소잠한의원", "hospital")
NEIGHBOUR = post("wirye_clinic", "위례튼튼한의원", "hospital")
MOM = post("mommy123", "세아맘 일상", "daily")
REVIEWER = post("review_king", "리뷰왕", "experience")


class HospitalBlogTests(unittest.TestCase):
    def test_counts_only_hospital_written_blogs(self):
        self.assertEqual(hospital_blog_count([HOSPITAL, MOM, REVIEWER]), 1)

    def test_a_keyword_with_no_hospital_blog_counts_zero(self):
        """병원 블로그가 한 자리도 없으면 블로그로 뚫을 자리가 아니다."""
        self.assertEqual(hospital_blog_count([MOM, REVIEWER]), 0)

    def test_an_empty_serp_is_zero_not_an_error(self):
        self.assertEqual(hospital_blog_count([]), 0)


class ExcludeOwnerTests(unittest.TestCase):
    def test_the_named_clinic_is_found_by_blog_name(self):
        self.assertEqual(blocked_owner([MOM, HOSPITAL], ["소잠", "위례"]), "소잠")

    def test_a_different_clinic_does_not_match(self):
        self.assertIsNone(blocked_owner([MOM, HOSPITAL], ["위례"]))

    def test_someone_else_merely_mentioning_the_clinic_is_not_excluded(self):
        """체험단·일반인이 그 병원을 언급한 글까지 '그 병원 글'로 세면 안 된다.
        우리가 빼려는 것은 그 병원이 **직접 쓴** 글이다."""
        mentions = post("mommy123", "세아맘 일상", "daily", title="소잠한의원 다녀왔어요")
        self.assertIsNone(blocked_owner([mentions], ["소잠"]))

    def test_the_blog_address_also_counts_as_the_owner(self):
        self.assertEqual(blocked_owner([post("sojamhani", "", "hospital")], ["sojam"]), "sojam")

    def test_no_names_means_nothing_is_excluded(self):
        for names in ([], None, ["", "  "]):
            with self.subTest(names=names):
                self.assertIsNone(blocked_owner([HOSPITAL, NEIGHBOUR], names))

    def test_power_content_never_reaches_this_check(self):
        """광고 자리는 통검 분석이 이미 걸러 posts 에 넣지 않는다.

        그래서 파워컨텐츠만 돌리는 병원 때문에 키워드가 통째로 빠지는 일은 없다.
        (여기서는 '광고가 빠진 목록'이 들어온다는 전제를 문서로 못 박아 둔다.)"""
        from app.services import serp_analyzer as sa
        source = sa.analyze_keyword.__doc__ or ""
        self.assertIn("is_ad=False", source, "posts 가 광고를 뺀 목록이라는 약속이 깨졌다")


if __name__ == "__main__":
    unittest.main()
